from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


FILE_NAMES = {
    "remote": "occupations_workathome.csv",
    "tasks": "Task Statements.xlsx",
    "dwas": "Tasks to DWAs.xlsx",
    "abilities": "Abilities.xlsx",
    "essential_skills": "Essential Skills.xlsx",
    "transferable_skills": "Transferable Skills.xlsx",
    "software_skills": "Software Skills.xlsx",
}

REMOTE_ALIASES = [
    "teleworkable",
    "workfromhome",
    "work_at_home",
    "workathome",
    "remote",
    "remote_work",
    "wfh",
    "homebased",
]

POSITIVE_TEXT_VALUES = {
    "1",
    "true",
    "t",
    "yes",
    "y",
    "remote",
    "teleworkable",
    "workfromhome",
    "work at home feasible",
    "work-from-home feasible",
}

NEGATIVE_TEXT_VALUES = {
    "0",
    "false",
    "f",
    "no",
    "n",
    "not remote",
    "nonremote",
    "non-remote",
}

def parse_args() -> argparse.Namespace:
    base_dir = Path(r"E:\Remote work")
    parser = argparse.ArgumentParser(
        description="Build an occupation-task-DWA-skill dataset for remote-feasible occupations."
    )
    parser.add_argument("--input-dir", type=Path, default=base_dir)
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=base_dir / "remote_occupations_tasks_dwas_skills.csv",
    )
    return parser.parse_args()


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


NORMALIZED_REMOTE_ALIASES = {normalize_label(alias) for alias in REMOTE_ALIASES}
NORMALIZED_POSITIVE_TEXT_VALUES = {normalize_label(value) for value in POSITIVE_TEXT_VALUES}
NORMALIZED_NEGATIVE_TEXT_VALUES = {normalize_label(value) for value in NEGATIVE_TEXT_VALUES}


def normalize_code_value(value: object) -> str | None:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def make_key(value: object) -> str | None:
    text = normalize_code_value(value)
    if text is None:
        return None
    key = re.sub(r"[^A-Z0-9]+", "", text.upper())
    return key or None


def clean_text(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text or text.lower() == "nan":
        return None
    return text


def make_text_key(value: object) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    return re.sub(r"[^A-Z0-9]+", "", text.upper()) or None


def format_value(value: object) -> str | None:
    if pd.isna(value):
        return None
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return clean_text(value)


def find_column(df: pd.DataFrame, aliases: Iterable[str], *, required: bool = True) -> str | None:
    alias_set = {normalize_label(alias) for alias in aliases}
    normalized = {column: normalize_label(column) for column in df.columns}

    for column, norm in normalized.items():
        if norm in alias_set:
            return column

    for alias in alias_set:
        for column, norm in normalized.items():
            if alias and alias in norm:
                return column

    if required:
        raise KeyError(f"Could not find a matching column for aliases: {list(aliases)}")
    return None


def ensure_occupation_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, str, str | None]:
    occupation_col = find_column(
        df,
        [
            "O*NET-SOC Code",
            "onetsoccode",
            "onetsoc_code",
            "soc_code",
            "occupation_code",
            "code",
        ],
    )
    title_col = find_column(df, ["title", "occupation_title", "job_title"], required=False)
    prepared = df.copy()
    prepared["occupation_code"] = prepared[occupation_col].map(normalize_code_value)
    prepared["occupation_key"] = prepared[occupation_col].map(make_key)
    if title_col:
        prepared["occupation_title_source"] = prepared[title_col].map(clean_text)
    else:
        prepared["occupation_title_source"] = pd.NA
    return prepared, occupation_col, title_col


def infer_remote_indicator_column(df: pd.DataFrame) -> str:
    normalized = {column: normalize_label(column) for column in df.columns}
    candidates = [
        column
        for column, norm in normalized.items()
        if any(alias in norm for alias in REMOTE_ALIASES)
    ]
    if not candidates:
        raise KeyError("Could not infer the remote-work indicator column from the Dingel/Neiman file.")
    candidates.sort(key=lambda col: (normalized[col] not in NORMALIZED_REMOTE_ALIASES, len(col)))
    return candidates[0]


def is_remote_feasible(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) > 0

    text = clean_text(value)
    if text is None:
        return False
    normalized = normalize_label(text)
    if normalized in NORMALIZED_POSITIVE_TEXT_VALUES:
        return True
    if normalized in NORMALIZED_NEGATIVE_TEXT_VALUES:
        return False
    return any(token in normalized for token in ("telework", "remote", "workfromhome"))


def aggregate_scale_table(df: pd.DataFrame, output_column: str) -> pd.DataFrame:
    prepared, _, _ = ensure_occupation_columns(df)
    element_col = find_column(prepared, ["element_name", "skill_name", "ability", "name"])
    scale_col = find_column(prepared, ["scale_name", "scale"], required=False)
    value_col = find_column(prepared, ["data_value", "value", "score", "rating"], required=False)

    prepared = prepared.loc[prepared["occupation_key"].notna() & prepared[element_col].notna()].copy()
    prepared["_element"] = prepared[element_col].map(clean_text)
    prepared["_scale"] = prepared[scale_col].map(clean_text) if scale_col else pd.NA
    prepared["_value"] = prepared[value_col].map(format_value) if value_col else pd.NA

    group_cols = ["occupation_key", "occupation_code", "_element"]

    element_summary = prepared[group_cols].drop_duplicates().copy()

    if scale_col and value_col:
        scale_parts = prepared.loc[prepared["_scale"].notna() & prepared["_value"].notna(), group_cols + ["_scale", "_value"]]
        scale_parts = scale_parts.drop_duplicates().sort_values(by=group_cols + ["_scale", "_value"])
        scale_parts["_part"] = scale_parts["_scale"] + "=" + scale_parts["_value"]
        scale_summary = (
            scale_parts.groupby(group_cols, dropna=False, sort=True)["_part"]
            .agg(", ".join)
            .reset_index(name="_scale_summary")
        )
        element_summary = element_summary.merge(scale_summary, on=group_cols, how="left")
        element_summary["_summary"] = element_summary.apply(
            lambda row: (
                f"{row['_element']} ({row['_scale_summary']})"
                if clean_text(row.get("_scale_summary")) is not None
                else row["_element"]
            ),
            axis=1,
        )
    else:
        element_summary["_summary"] = element_summary["_element"]

    return (
        element_summary.groupby(["occupation_key", "occupation_code"], dropna=False, sort=True)["_summary"]
        .apply(lambda values: "; ".join(sorted(dict.fromkeys(v for v in values if v))))
        .reset_index(name=output_column)
    )


def aggregate_software_skills(df: pd.DataFrame) -> pd.DataFrame:
    prepared, _, _ = ensure_occupation_columns(df)
    example_col = find_column(prepared, ["workplace_example", "software", "example"], required=False)
    element_col = find_column(prepared, ["element_name", "software_type", "category"], required=False)
    hot_col = find_column(prepared, ["hot_technology", "hottechnology"], required=False)
    demand_col = find_column(prepared, ["in_demand", "indemand"], required=False)

    prepared = prepared.loc[prepared["occupation_key"].notna()].copy()

    def format_software(row: pd.Series) -> str | None:
        example = clean_text(row[example_col]) if example_col else None
        element = clean_text(row[element_col]) if element_col else None
        hot = clean_text(row[hot_col]) if hot_col else None
        demand = clean_text(row[demand_col]) if demand_col else None

        label = example or element
        if label is None:
            return None
        if example and element and example != element:
            label = f"{example} ({element})"

        flags = []
        if hot and hot.upper() == "Y":
            flags.append("hot")
        if demand and demand.upper() == "Y":
            flags.append("in-demand")
        if flags:
            label = f"{label} [{', '.join(flags)}]"
        return label

    prepared["_software"] = prepared.apply(format_software, axis=1)
    prepared = prepared.loc[prepared["_software"].notna()]

    return (
        prepared.groupby(["occupation_key", "occupation_code"], dropna=False, sort=True)["_software"]
        .apply(lambda values: "; ".join(sorted(dict.fromkeys(v for v in values if v))))
        .reset_index(name="software_skills")
    )


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def build_dataset(input_dir: Path, output_csv: Path) -> None:
    paths = {name: input_dir / filename for name, filename in FILE_NAMES.items()}
    missing_files = [str(path) for path in paths.values() if not path.exists()]
    if missing_files:
        raise FileNotFoundError(f"Missing input files: {missing_files}")

    remote_raw = read_table(paths["remote"])
    tasks_raw = read_table(paths["tasks"])
    dwas_raw = read_table(paths["dwas"])
    abilities_raw = read_table(paths["abilities"])
    essential_raw = read_table(paths["essential_skills"])
    transferable_raw = read_table(paths["transferable_skills"])
    software_raw = read_table(paths["software_skills"])

    remote_df, _, _ = ensure_occupation_columns(remote_raw)
    remote_indicator_col = infer_remote_indicator_column(remote_df)
    remote_df["remote_work_indicator"] = remote_df[remote_indicator_col]
    remote_df = remote_df.loc[remote_df["occupation_key"].notna()].copy()
    remote_df["is_remote_feasible"] = remote_df["remote_work_indicator"].map(is_remote_feasible)

    total_occupations = remote_df["occupation_key"].nunique()
    remote_feasible = remote_df.loc[remote_df["is_remote_feasible"]].copy()
    remote_feasible = remote_feasible.drop_duplicates(subset=["occupation_key"]).copy()
    remote_feasible_count = remote_feasible["occupation_key"].nunique()

    tasks_df, _, _ = ensure_occupation_columns(tasks_raw)
    task_id_col = find_column(tasks_df, ["task_id", "taskid"], required=False)
    task_statement_col = find_column(tasks_df, ["task", "task_statement", "statement"])
    task_type_col = find_column(tasks_df, ["task_type", "task_relevance", "relevance"], required=False)

    tasks_df["task_id"] = tasks_df[task_id_col].map(normalize_code_value) if task_id_col else pd.NA
    tasks_df["task_id_key"] = tasks_df["task_id"].map(make_key)
    tasks_df["task_statement"] = tasks_df[task_statement_col].map(clean_text)
    tasks_df["task_statement_key"] = tasks_df["task_statement"].map(make_text_key)
    tasks_df["task_type"] = tasks_df[task_type_col].map(clean_text) if task_type_col else pd.NA

    remote_tasks = remote_feasible.merge(
        tasks_df[
            [
                "occupation_key",
                "occupation_code",
                "occupation_title_source",
                "task_id",
                "task_id_key",
                "task_statement",
                "task_statement_key",
                "task_type",
            ]
        ],
        on="occupation_key",
        how="left",
        suffixes=("_remote", "_task"),
        indicator=True,
    )

    remote_tasks["occupation_code"] = remote_tasks["occupation_code_remote"].combine_first(
        remote_tasks["occupation_code_task"]
    )
    remote_tasks["occupation_title"] = remote_tasks["occupation_title_source_task"].combine_first(
        remote_tasks["occupation_title_source_remote"]
    )
    remote_tasks_unmatched_codes = sorted(
        remote_tasks.loc[remote_tasks["_merge"] == "left_only", "occupation_code"].dropna().unique().tolist()
    )
    task_rows_retained = int(remote_tasks["task_statement"].notna().sum())

    dwas_df, _, _ = ensure_occupation_columns(dwas_raw)
    dwa_task_id_col = find_column(dwas_df, ["task_id", "taskid"], required=False)
    dwa_task_col = find_column(dwas_df, ["task", "task_statement", "statement"], required=False)
    dwa_id_col = find_column(dwas_df, ["dwa_element_id", "dwa_id", "dwaelementid"], required=False)
    dwa_title_col = find_column(
        dwas_df,
        ["dwa_element_name", "dwa_title", "dwa_description", "dwaelementname"],
        required=False,
    )

    dwas_df["task_id"] = dwas_df[dwa_task_id_col].map(normalize_code_value) if dwa_task_id_col else pd.NA
    dwas_df["task_id_key"] = dwas_df["task_id"].map(make_key)
    dwas_df["task_statement"] = dwas_df[dwa_task_col].map(clean_text) if dwa_task_col else pd.NA
    dwas_df["task_statement_key"] = dwas_df["task_statement"].map(make_text_key)
    dwas_df["dwa_id"] = dwas_df[dwa_id_col].map(normalize_code_value) if dwa_id_col else pd.NA
    dwas_df["dwa_title"] = dwas_df[dwa_title_col].map(clean_text) if dwa_title_col else pd.NA

    dwas_merge_columns = [
        "occupation_key",
        "task_id_key",
        "task_statement_key",
        "dwa_id",
        "dwa_title",
    ]
    dwas_joinable = dwas_df[dwas_merge_columns].drop_duplicates()

    remote_tasks_primary = remote_tasks.merge(
        dwas_joinable.drop(columns=["task_statement_key"]),
        on=["occupation_key", "task_id_key"],
        how="left",
    )

    needs_fallback = remote_tasks_primary["dwa_id"].isna() & remote_tasks_primary["task_statement_key"].notna()

    if needs_fallback.any():
        fallback_rows = remote_tasks.loc[needs_fallback].drop(columns=["_merge"])
        fallback_matches = fallback_rows.merge(
            dwas_joinable.drop(columns=["task_id_key"]),
            on=["occupation_key", "task_statement_key"],
            how="left",
        )
        keep_rows = remote_tasks_primary.loc[~needs_fallback].copy()
        merged_with_dwas = pd.concat([keep_rows, fallback_matches], ignore_index=True, sort=False)
    else:
        merged_with_dwas = remote_tasks_primary

    merged_with_dwas["dwa_id"] = merged_with_dwas["dwa_id"].where(merged_with_dwas["dwa_id"].notna(), pd.NA)
    merged_with_dwas["dwa_title"] = merged_with_dwas["dwa_title"].where(
        merged_with_dwas["dwa_title"].notna(), pd.NA
    )

    unmatched_dwa_codes = sorted(
        merged_with_dwas.loc[
            merged_with_dwas["task_statement"].notna() & merged_with_dwas["dwa_id"].isna(), "occupation_code"
        ]
        .dropna()
        .unique()
        .tolist()
    )

    abilities = aggregate_scale_table(abilities_raw, "abilities")
    essential = aggregate_scale_table(essential_raw, "essential_skills")
    transferable = aggregate_scale_table(transferable_raw, "transferable_skills")
    software = aggregate_software_skills(software_raw)

    unmatched_skill_codes = {}
    for label, aggregated_df in [
        ("abilities", abilities),
        ("essential_skills", essential),
        ("transferable_skills", transferable),
        ("software_skills", software),
    ]:
        missing_codes = sorted(
            remote_feasible.loc[
                ~remote_feasible["occupation_key"].isin(aggregated_df["occupation_key"]), "occupation_code"
            ]
            .dropna()
            .unique()
            .tolist()
        )
        unmatched_skill_codes[label] = missing_codes
        merged_with_dwas = merged_with_dwas.merge(
            aggregated_df[["occupation_key", label]],
            on="occupation_key",
            how="left",
        )

    skill_columns = ["abilities", "essential_skills", "transferable_skills", "software_skills"]

    def summarize_missing_skill_columns(row: pd.Series) -> str | None:
        missing = [column for column in skill_columns if pd.isna(row[column])]
        if not missing:
            return None
        return "; ".join(missing)

    merged_with_dwas["missing_skill_columns"] = merged_with_dwas.apply(
        summarize_missing_skill_columns,
        axis=1,
    )
    merged_with_dwas["skill_mismatch_summary"] = merged_with_dwas["missing_skill_columns"].map(
        lambda value: f"Missing occupation-level match in: {value}" if clean_text(value) else None
    )

    final_columns = [
        "occupation_code",
        "occupation_title",
        "remote_work_indicator",
        "task_id",
        "task_statement",
        "task_type",
        "dwa_id",
        "dwa_title",
        "abilities",
        "essential_skills",
        "transferable_skills",
        "software_skills",
        "missing_skill_columns",
        "skill_mismatch_summary",
    ]

    final_df = merged_with_dwas[final_columns].copy()
    final_df = final_df.sort_values(
        by=["occupation_code", "task_id", "task_statement", "dwa_id"],
        na_position="last",
    ).reset_index(drop=True)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(output_csv, index=False)

    def summarize_codes(codes: list[str], limit: int = 15) -> str:
        if not codes:
            return "none"
        if len(codes) <= limit:
            return ", ".join(codes)
        preview = ", ".join(codes[:limit])
        return f"{preview}, ... (+{len(codes) - limit} more)"

    print("Remote occupation-task-DWA-skill dataset summary")
    print(f"Input directory: {input_dir}")
    print(f"Output CSV: {output_csv}")
    print(f"Number of occupations in Dingel and Neiman file: {total_occupations}")
    print(f"Number of occupations classified as remote/work-from-home feasible: {remote_feasible_count}")
    print(f"Number of task statements retained after filtering to remote occupations: {task_rows_retained}")
    print(f"Number of rows in the final occupation-task-DWA-skill dataset: {len(final_df)}")
    print(
        "Unmatched occupation codes when merging remote occupations to task statements: "
        f"{summarize_codes(remote_tasks_unmatched_codes)}"
    )
    print(
        "Occupation codes with task statements but no DWA match: "
        f"{summarize_codes(unmatched_dwa_codes)}"
    )
    for label in ["abilities", "essential_skills", "transferable_skills", "software_skills"]:
        occupations_missing = len(unmatched_skill_codes[label])
        rows_with_tasks = int(
            merged_with_dwas.loc[
                merged_with_dwas[label].isna() & merged_with_dwas["task_statement"].notna()
            ].shape[0]
        )
        rows_with_dwas = int(
            merged_with_dwas.loc[
                merged_with_dwas[label].isna() & merged_with_dwas["dwa_title"].notna()
            ].shape[0]
        )
        print(
            f"Unmatched occupation codes for {label}: "
            f"{summarize_codes(unmatched_skill_codes[label])}"
        )
        print(
            f"Mismatch summary for {label}: occupations missing={occupations_missing}, "
            f"rows with task statements={rows_with_tasks}, rows with DWA descriptions={rows_with_dwas}"
        )


def main() -> None:
    args = parse_args()
    build_dataset(args.input_dir, args.output_csv)


if __name__ == "__main__":
    main()
