from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import EXPOSURE_INDEX_COLUMNS, MODEL_ARTIFACTS_DIR, ML_LAG_YEARS, PROCESSED_DATA_DIR
from .data_download import cache_dataframe

try:
    import torch
    from torch import nn
except Exception:  # pragma: no cover - optional dependency fallback
    torch = None
    nn = None


ML_PREDICTIONS_PATH = PROCESSED_DATA_DIR / "ml_predictions.parquet"
ML_METRICS_PATH = PROCESSED_DATA_DIR / "ml_model_metrics.parquet"

# Observed state GFR has stayed within roughly 20-70 births per 1,000 women aged 15-44. recursive_forecast
# feeds each year's prediction back in as next year's lag/rolling features, so a single year of a model
# extrapolating outside its training domain can compound into a runaway forecast decades out. Clamping each
# step to a generous-but-finite band keeps that feedback loop from diverging to numerical nonsense while still
# leaving room for scenarios to land meaningfully above or below the historical range.
RECURSIVE_FORECAST_FLOOR = 5.0
RECURSIVE_FORECAST_CEILING = 150.0


@dataclass
class ModelBundle:
    model_name: str
    model_type: str
    model: object
    feature_columns: list[str]
    categorical_columns: list[str]
    numeric_columns: list[str]
    metadata: dict


class TemporalFertilityMLP(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 64):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs).squeeze(-1)


def time_based_split(df: pd.DataFrame, year_col: str = "year") -> dict[str, pd.DataFrame]:
    years = sorted(pd.to_numeric(df[year_col], errors="coerce").dropna().astype(int).unique().tolist())
    if len(years) < 4:
        raise ValueError("Need at least 4 distinct years for train/validation/test time splits.")
    test_count = max(1, len(years) // 5)
    val_count = max(1, len(years) // 5)
    train_years = years[: len(years) - val_count - test_count]
    val_years = years[len(train_years) : len(train_years) + val_count]
    test_years = years[len(train_years) + val_count :]
    return {
        "train": df[df[year_col].isin(train_years)].copy(),
        "validation": df[df[year_col].isin(val_years)].copy(),
        "test": df[df[year_col].isin(test_years)].copy(),
        "train_years": train_years,
        "validation_years": val_years,
        "test_years": test_years,
    }


def default_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    lagged_exposures = [f"{column}_lag{lag}" for column in EXPOSURE_INDEX_COLUMNS for lag in (1, 2)]
    candidate_numeric = [
        *[column for column in EXPOSURE_INDEX_COLUMNS if column in df.columns],
        *[column for column in lagged_exposures if column in df.columns],
        *[
            column
            for column in [
                "fertility_rate_lag1",
                "fertility_rate_lag2",
                "fertility_rate_rolling3",
                "female_population_15_44",
                "total_population",
                "population_growth_rate",
                "labor_force_participation_rate",
                "female_employment_rate",
                "married_or_partnered_share_state_year",
                "state_history_mean_fertility",
                "state_history_mean_remote_work",
                "state_log_population_baseline",
                "year_index",
                "year_index_sq",
                "post_2020",
                "post_2020_trend",
                "region_id",
            ]
            if column in df.columns
        ],
    ]
    numeric_columns = [
        column
        for column in dict.fromkeys(candidate_numeric)
        if pd.api.types.is_numeric_dtype(df[column]) and df[column].notna().any()
    ]
    categorical_columns = [column for column in ["state_fips", "region"] if column in df.columns]
    feature_columns = numeric_columns + categorical_columns
    return feature_columns, numeric_columns, categorical_columns


def _prepare_training_data(df: pd.DataFrame, target_col: str = "fertility_rate") -> pd.DataFrame:
    out = df.copy()
    out = out[out[target_col].notna()].copy()
    if "state_numeric" not in out.columns:
        out["state_numeric"] = pd.factorize(out["state_fips"])[0]
    return out


def _prediction_frame(
    frame: pd.DataFrame,
    predictions: np.ndarray,
    model_name: str,
    split_name: str,
    actual_col: str = "fertility_rate",
) -> pd.DataFrame:
    out = frame[["state_fips", "state_name", "region", "year"]].copy()
    out["model_name"] = model_name
    out["split"] = split_name
    out["actual_fertility_rate"] = frame.get(actual_col)
    out["predicted_fertility_rate"] = predictions
    return out


def _compute_metric_rows(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    scored = predictions.dropna(subset=["actual_fertility_rate", "predicted_fertility_rate"]).copy()
    if scored.empty:
        return pd.DataFrame()

    def append_metrics(group_df: pd.DataFrame, group_type: str, group_name: str) -> None:
        actual = group_df["actual_fertility_rate"].to_numpy(dtype=float)
        pred = group_df["predicted_fertility_rate"].to_numpy(dtype=float)
        if len(actual) == 0:
            return
        mape = np.nan
        nonzero = actual != 0
        if nonzero.any():
            mape = float(np.mean(np.abs((actual[nonzero] - pred[nonzero]) / actual[nonzero])))
        rows.append(
            {
                "model_name": group_df["model_name"].iloc[0],
                "split": group_df["split"].iloc[0],
                "group_type": group_type,
                "group_name": group_name,
                "rmse": float(np.sqrt(mean_squared_error(actual, pred))),
                "mae": float(mean_absolute_error(actual, pred)),
                "mape": mape,
                "r_squared": float(r2_score(actual, pred)) if len(actual) > 1 else np.nan,
                "n_obs": int(len(group_df)),
            }
        )

    for (model_name, split), group in scored.groupby(["model_name", "split"], sort=False):
        append_metrics(group, "overall", "all")
        for state, state_group in group.groupby("state_fips", sort=False):
            append_metrics(state_group, "state", state)
        for region, region_group in group.groupby("region", sort=False):
            append_metrics(region_group, "region", str(region))
        period = group.assign(period=np.where(group["year"] < 2020, "pre_pandemic", "post_pandemic"))
        for label, period_group in period.groupby("period", sort=False):
            append_metrics(period_group, "period", label)
    return pd.DataFrame(rows)


def baseline_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[["state_fips", "state_name", "region", "year", "fertility_rate", "fertility_rate_lag1", "fertility_rate_lag2"]].copy()
    out["baseline_last_observed"] = out["fertility_rate_lag1"]
    trend_component = out["fertility_rate_lag1"] - out["fertility_rate_lag2"]
    out["baseline_recent_trend"] = out["fertility_rate_lag1"] + trend_component.fillna(0.0)
    return out


def train_statistical_model(train_df: pd.DataFrame, feature_columns: list[str], numeric_columns: list[str], categorical_columns: list[str]) -> ModelBundle:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
        ]
    )
    model = Pipeline(steps=[("preprocessor", preprocessor), ("ridge", Ridge(alpha=1.0))])
    model.fit(train_df[feature_columns], train_df["fertility_rate"])
    return ModelBundle(
        model_name="statistical_ridge",
        model_type="sklearn_pipeline",
        model=model,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        numeric_columns=numeric_columns,
        metadata={"description": "Regularized statistical panel model with state/year features."},
    )


def train_tree_model(train_df: pd.DataFrame, numeric_columns: list[str]) -> ModelBundle:
    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "hist_gbm",
                HistGradientBoostingRegressor(
                    learning_rate=0.06,
                    max_depth=6,
                    max_iter=250,
                    min_samples_leaf=4,
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(train_df[numeric_columns], train_df["fertility_rate"])
    return ModelBundle(
        model_name="tree_gradient_boosting",
        model_type="sklearn_numeric",
        model=model,
        feature_columns=numeric_columns,
        categorical_columns=[],
        numeric_columns=numeric_columns,
        metadata={"description": "Tree-based ML model using histogram gradient boosting."},
    )


def train_neural_network_model(train_df: pd.DataFrame, validation_df: pd.DataFrame, numeric_columns: list[str]) -> ModelBundle:
    if torch is None or nn is None:
        fallback = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("mlp", Ridge(alpha=0.5)),
            ]
        )
        fallback.fit(train_df[numeric_columns], train_df["fertility_rate"])
        return ModelBundle(
            model_name="neural_fallback_mlp",
            model_type="sklearn_numeric",
            model=fallback,
            feature_columns=numeric_columns,
            categorical_columns=[],
            numeric_columns=numeric_columns,
            metadata={"description": "Fallback neural proxy because PyTorch was unavailable."},
        )

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    x_train = scaler.fit_transform(imputer.fit_transform(train_df[numeric_columns]))
    y_train_raw = train_df["fertility_rate"].to_numpy(dtype=np.float32)
    x_val = scaler.transform(imputer.transform(validation_df[numeric_columns]))
    y_val_raw = validation_df["fertility_rate"].to_numpy(dtype=np.float32)

    # The target (general fertility rate, ~20-90) was previously trained unscaled against inputs
    # that are standardized to mean 0 / std 1. That mismatch between the input and target scale
    # made the MSE loss landscape badly conditioned: with Adam's default lr the optimizer
    # overshot and never converged (train R^2 was negative -- worse than predicting the mean).
    # Standardizing the target the same way as the inputs, then inverse-transforming predictions,
    # fixes the fit and removes the main driver of the recursive-forecast ceiling explosion.
    target_mean = float(y_train_raw.mean())
    target_std = float(y_train_raw.std()) or 1.0
    y_train = (y_train_raw - target_mean) / target_std
    y_val = (y_val_raw - target_mean) / target_std

    model = TemporalFertilityMLP(input_dim=x_train.shape[1], hidden_dim=min(64, max(16, x_train.shape[1] * 2)))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.MSELoss()

    train_inputs = torch.tensor(x_train, dtype=torch.float32)
    train_targets = torch.tensor(y_train, dtype=torch.float32)
    val_inputs = torch.tensor(x_val, dtype=torch.float32)
    val_targets = torch.tensor(y_val, dtype=torch.float32)

    best_state = None
    best_val_loss = float("inf")
    for _ in range(80):
        model.train()
        optimizer.zero_grad()
        predictions = model(train_inputs)
        loss = criterion(predictions, train_targets)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_loss = criterion(model(val_inputs), val_targets).item() if len(val_inputs) else loss.item()
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {key: value.detach().clone() for key, value in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    artifact = {
        "torch_model": model,
        "scaler": scaler,
        "imputer": imputer,
        "target_mean": target_mean,
        "target_std": target_std,
    }
    return ModelBundle(
        model_name="temporal_neural_net",
        model_type="torch_numeric",
        model=artifact,
        feature_columns=numeric_columns,
        categorical_columns=[],
        numeric_columns=numeric_columns,
        metadata={"description": "Temporal feed-forward neural network using lagged features."},
    )


def predict_with_bundle(bundle: ModelBundle, frame: pd.DataFrame) -> np.ndarray:
    if frame.empty:
        return np.array([])
    if bundle.model_type == "sklearn_pipeline":
        return bundle.model.predict(frame[bundle.feature_columns])
    if bundle.model_type == "sklearn_numeric":
        return bundle.model.predict(frame[bundle.feature_columns])
    if bundle.model_type == "torch_numeric":
        artifact = bundle.model
        transformed = artifact["scaler"].transform(artifact["imputer"].transform(frame[bundle.feature_columns]))
        inputs = torch.tensor(transformed, dtype=torch.float32)
        artifact["torch_model"].eval()
        with torch.no_grad():
            scaled_prediction = artifact["torch_model"](inputs).cpu().numpy()
        target_mean = float(artifact.get("target_mean", 0.0))
        target_std = float(artifact.get("target_std", 1.0)) or 1.0
        return scaled_prediction * target_std + target_mean
    raise ValueError(f"Unsupported model type: {bundle.model_type}")


def save_model_bundle(bundle: ModelBundle, artifact_dir: str | Path = MODEL_ARTIFACTS_DIR) -> None:
    target_dir = Path(artifact_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = target_dir / f"{bundle.model_name}_metadata.json"
    metadata_path.write_text(json.dumps(bundle.metadata | {"feature_columns": bundle.feature_columns}, indent=2), encoding="utf-8")
    if bundle.model_type in {"sklearn_pipeline", "sklearn_numeric"}:
        joblib.dump(bundle.model, target_dir / f"{bundle.model_name}.joblib")
    elif bundle.model_type == "torch_numeric" and torch is not None:
        artifact = bundle.model
        torch.save(
            {
                "state_dict": artifact["torch_model"].state_dict(),
                "feature_columns": bundle.feature_columns,
                "scaler_mean": artifact["scaler"].mean_.tolist(),
                "scaler_scale": artifact["scaler"].scale_.tolist(),
                "imputer_statistics": artifact["imputer"].statistics_.tolist(),
                "target_mean": artifact.get("target_mean", 0.0),
                "target_std": artifact.get("target_std", 1.0),
            },
            target_dir / f"{bundle.model_name}.pt",
        )


def _future_feature_row(row: pd.Series, history: pd.DataFrame, feature_columns: list[str]) -> dict:
    feature_row: dict[str, object] = {}
    for feature in feature_columns:
        if feature.endswith("_lag1") or feature.endswith("_lag2") or feature.endswith("_lag3"):
            base_feature, lag_suffix = feature.rsplit("_lag", 1)
            lag = int(lag_suffix)
            feature_row[feature] = history[base_feature].iloc[-lag] if len(history) >= lag and base_feature in history.columns else np.nan
        elif feature.endswith("_rolling3"):
            base_feature = feature.replace("_rolling3", "")
            feature_row[feature] = history[base_feature].tail(3).mean() if base_feature in history.columns else np.nan
        elif feature == "year_index":
            feature_row[feature] = row["year"] - history["year"].min()
        elif feature == "year_index_sq":
            year_index = row["year"] - history["year"].min()
            feature_row[feature] = year_index ** 2
        elif feature == "post_2020":
            feature_row[feature] = int(row["year"] >= 2020)
        elif feature == "post_2020_trend":
            feature_row[feature] = max(int(row["year"]) - 2020, 0)
        elif feature == "state_history_mean_fertility":
            feature_row[feature] = history["fertility_rate"].mean()
        elif feature == "state_history_mean_remote_work":
            feature_row[feature] = history["remote_work_exposure_index"].mean() if "remote_work_exposure_index" in history.columns else np.nan
        elif feature == "state_log_population_baseline":
            base_population = history["total_population"].iloc[0] if "total_population" in history.columns else np.nan
            feature_row[feature] = np.log(base_population) if pd.notna(base_population) and base_population > 0 else np.nan
        else:
            feature_row[feature] = row.get(feature, np.nan)
    for field in ["state_fips", "state_name", "region", "year"]:
        if field in row.index:
            feature_row[field] = row[field]
    return feature_row


def recursive_forecast(
    bundle: ModelBundle,
    historical_panel: pd.DataFrame,
    future_covariates: pd.DataFrame,
    scenario_name: str,
) -> pd.DataFrame:
    forecasts = []
    history_map = {
        state_fips: group.sort_values("year").copy()
        for state_fips, group in historical_panel.sort_values(["state_fips", "year"]).groupby("state_fips", sort=False)
    }
    future = future_covariates.sort_values(["year", "state_fips"]).copy()
    last_observed_years = {
        state_fips: int(group["year"].max())
        for state_fips, group in historical_panel.groupby("state_fips", sort=False)
    }
    for year, year_rows in future.groupby("year", sort=True):
        staged_rows = []
        staged_feature_rows = []
        for _, future_row in year_rows.iterrows():
            state_fips = future_row["state_fips"]
            state_history = history_map.get(state_fips)
            if state_history is None or state_history.empty:
                continue
            if int(year) <= last_observed_years.get(state_fips, int(year)):
                continue
            feature_row = _future_feature_row(future_row, state_history, bundle.feature_columns)
            staged_rows.append(future_row.copy())
            staged_feature_rows.append(feature_row)
        if not staged_feature_rows:
            continue
        feature_input = pd.DataFrame(staged_feature_rows)
        predictions = predict_with_bundle(bundle, feature_input)
        for future_row, feature_row, prediction in zip(staged_rows, staged_feature_rows, predictions, strict=False):
            state_fips = future_row["state_fips"]
            clamped_prediction = float(np.clip(float(prediction), RECURSIVE_FORECAST_FLOOR, RECURSIVE_FORECAST_CEILING))
            output_row = future_row.copy()
            for feature in bundle.feature_columns:
                if feature in feature_row:
                    output_row[feature] = feature_row[feature]
            output_row["model_name"] = bundle.model_name
            output_row["predicted_fertility_rate"] = clamped_prediction
            output_row["scenario_name"] = scenario_name
            forecasts.append(output_row)

            appended = future_row.copy()
            appended["fertility_rate"] = clamped_prediction
            history_map[state_fips] = pd.concat([history_map[state_fips], pd.DataFrame([appended])], ignore_index=True, sort=False)
    return pd.DataFrame(forecasts)


def baseline_recursive_forecast(
    historical_panel: pd.DataFrame,
    future_covariates: pd.DataFrame,
    model_name: str,
    scenario_name: str,
) -> pd.DataFrame:
    forecasts = []
    history = historical_panel.sort_values(["state_fips", "year"]).copy()
    for state_fips, future_state in future_covariates.sort_values(["state_fips", "year"]).groupby("state_fips", sort=False):
        state_history = history[history["state_fips"] == state_fips].sort_values("year").copy()
        if state_history.empty:
            continue
        last_observed_year = int(state_history["year"].max())
        last_observed = float(state_history["fertility_rate"].iloc[-1])
        recent_trend = 0.0
        if len(state_history) >= 2:
            recent_trend = float(state_history["fertility_rate"].iloc[-1] - state_history["fertility_rate"].iloc[-2])
        running_prediction = last_observed
        for _, future_row in future_state[future_state["year"] > last_observed_year].iterrows():
            if model_name == "baseline_last_observed":
                prediction = last_observed
            elif model_name == "baseline_recent_trend":
                running_prediction = running_prediction + recent_trend
                prediction = running_prediction
            else:
                raise ValueError(f"Unsupported baseline forecast model: {model_name}")
            output_row = future_row.copy()
            output_row["model_name"] = model_name
            output_row["predicted_fertility_rate"] = prediction
            output_row["scenario_name"] = scenario_name
            forecasts.append(output_row)
    return pd.DataFrame(forecasts)


def train_all_models(
    ml_panel: pd.DataFrame,
    scenario_covariates: pd.DataFrame | None = None,
    predictions_path: str | Path = ML_PREDICTIONS_PATH,
    metrics_path: str | Path = ML_METRICS_PATH,
    artifact_dir: str | Path = MODEL_ARTIFACTS_DIR,
) -> tuple[dict[str, ModelBundle], pd.DataFrame, pd.DataFrame]:
    training_frame = _prepare_training_data(ml_panel)
    splits = time_based_split(training_frame)
    feature_columns, numeric_columns, categorical_columns = default_feature_columns(training_frame)

    predictions = []

    for split_name in ["train", "validation", "test"]:
        baseline_frame = baseline_predictions(splits[split_name])
        predictions.append(_prediction_frame(baseline_frame, baseline_frame["baseline_last_observed"].to_numpy(), "baseline_last_observed", split_name))
        predictions.append(_prediction_frame(baseline_frame, baseline_frame["baseline_recent_trend"].to_numpy(), "baseline_recent_trend", split_name))

    statistical_bundle = train_statistical_model(splits["train"], feature_columns, numeric_columns, categorical_columns)
    tree_bundle = train_tree_model(splits["train"], numeric_columns)
    neural_bundle = train_neural_network_model(splits["train"], splits["validation"], numeric_columns)
    bundles = {
        statistical_bundle.model_name: statistical_bundle,
        tree_bundle.model_name: tree_bundle,
        neural_bundle.model_name: neural_bundle,
    }
    split_metadata = {
        "train_years": splits["train_years"],
        "validation_years": splits["validation_years"],
        "test_years": splits["test_years"],
        "feature_count": len(feature_columns),
        "sequence_length": len(ML_LAG_YEARS),
    }
    for bundle in bundles.values():
        bundle.metadata = split_metadata | bundle.metadata

    for bundle in bundles.values():
        save_model_bundle(bundle, artifact_dir=artifact_dir)
        for split_name in ["train", "validation", "test"]:
            frame = splits[split_name]
            predictions.append(
                _prediction_frame(
                    frame,
                    predict_with_bundle(bundle, frame),
                    bundle.model_name,
                    split_name,
                )
            )

    predictions_df = pd.concat(predictions, ignore_index=True).sort_values(["model_name", "split", "state_fips", "year"])

    if scenario_covariates is not None and not scenario_covariates.empty:
        future_predictions = []
        scenario_names = scenario_covariates["scenario_name"].dropna().unique().tolist() if "scenario_name" in scenario_covariates.columns else ["baseline_continuation"]
        for scenario_name in scenario_names:
            scenario_frame = scenario_covariates if "scenario_name" not in scenario_covariates.columns else scenario_covariates[scenario_covariates["scenario_name"] == scenario_name]
            for baseline_model_name in ["baseline_last_observed", "baseline_recent_trend"]:
                baseline_forecast = baseline_recursive_forecast(
                    training_frame,
                    scenario_frame,
                    model_name=baseline_model_name,
                    scenario_name=scenario_name,
                )
                if baseline_forecast.empty:
                    continue
                baseline_out = baseline_forecast.copy()
                baseline_out["split"] = "forecast"
                baseline_out["actual_fertility_rate"] = np.nan
                predictions_df = pd.concat([predictions_df, baseline_out], ignore_index=True, sort=False)
                future_predictions.append(baseline_out)
            for bundle in bundles.values():
                forecast_df = recursive_forecast(bundle, training_frame, scenario_frame, scenario_name=scenario_name)
                if forecast_df.empty:
                    continue
                future_out = forecast_df.copy()
                future_out["split"] = "forecast"
                future_out["actual_fertility_rate"] = np.nan
                predictions_df = pd.concat([predictions_df, future_out], ignore_index=True, sort=False)
                future_predictions.append(future_out)

    metrics_df = _compute_metric_rows(predictions_df)
    cache_dataframe(predictions_df, Path(predictions_path))
    cache_dataframe(metrics_df, Path(metrics_path))
    return bundles, predictions_df, metrics_df
