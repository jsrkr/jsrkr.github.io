from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def make_line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    title: str | None = None,
    line_dash: str | None = None,
) -> go.Figure:
    return px.line(df, x=x, y=y, color=color, line_dash=line_dash, title=title)


def make_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    title: str | None = None,
    orientation: str = "v",
) -> go.Figure:
    return px.bar(df, x=x, y=y, color=color, title=title, orientation=orientation)


def make_scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    title: str | None = None,
    hover_data: list[str] | None = None,
) -> go.Figure:
    return px.scatter(df, x=x, y=y, color=color, title=title, hover_data=hover_data)


def make_choropleth(
    df: pd.DataFrame,
    location_col: str,
    value_col: str,
    title: str,
    color_continuous_scale: str = "Tealgrn",
) -> go.Figure:
    return px.choropleth(
        df,
        locations=location_col,
        locationmode="USA-states",
        color=value_col,
        scope="usa",
        title=title,
        color_continuous_scale=color_continuous_scale,
    )


def make_stacked_decomposition(df: pd.DataFrame, x: str, y_cols: list[str], title: str) -> go.Figure:
    figure = go.Figure()
    for col in y_cols:
        if col not in df.columns:
            continue
        figure.add_trace(go.Bar(x=df[x], y=df[col], name=col))
    figure.update_layout(barmode="stack", title=title)
    return figure


def make_uncertainty_fan(df: pd.DataFrame, x: str, mid: str, low: str, high: str, title: str) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=df[x], y=df[high], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    figure.add_trace(
        go.Scatter(
            x=df[x],
            y=df[low],
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(27, 126, 168, 0.18)",
            name="Uncertainty band",
        )
    )
    figure.add_trace(go.Scatter(x=df[x], y=df[mid], name="Projected births"))
    figure.update_layout(title=title)
    return figure


def make_quality_table(df: pd.DataFrame) -> go.Figure:
    return go.Figure(
        data=[
            go.Table(
                header=dict(values=list(df.columns)),
                cells=dict(values=[df[col] for col in df.columns]),
            )
        ]
    )


def make_prediction_vs_actual_plot(
    df: pd.DataFrame,
    actual_col: str = "actual_fertility_rate",
    predicted_col: str = "predicted_fertility_rate",
    title: str | None = None,
) -> go.Figure:
    figure = px.scatter(df, x=actual_col, y=predicted_col, color="model_name", title=title or "Predicted vs actual fertility")
    if not df.empty:
        min_val = min(df[actual_col].min(), df[predicted_col].min())
        max_val = max(df[actual_col].max(), df[predicted_col].max())
        figure.add_trace(
            go.Scatter(
                x=[min_val, max_val],
                y=[min_val, max_val],
                mode="lines",
                name="45-degree line",
                line=dict(color="gray", dash="dash"),
            )
        )
    return figure


def make_importance_chart(
    df: pd.DataFrame,
    x: str = "importance_value",
    y: str = "feature",
    color: str | None = "model_name",
    title: str | None = None,
) -> go.Figure:
    chart = df.sort_values(x, ascending=True)
    return px.bar(chart, x=x, y=y, color=color, orientation="h", title=title or "Feature importance")


def make_temporal_importance_chart(df: pd.DataFrame, title: str | None = None) -> go.Figure:
    temporal = (
        df.groupby("temporal_bucket", as_index=False)["contribution"]
        .apply(lambda series: series.abs().sum())
        .rename(columns={"contribution": "absolute_contribution"})
    )
    return px.bar(temporal, x="temporal_bucket", y="absolute_contribution", title=title or "Temporal importance")
