from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LOCATION_AUDIT = ROOT / "data" / "final" / "platform_location_audit.csv"
FINAL_TEMPLATE = ROOT / "data" / "final" / "manual_collection_template_multiplatform.csv"
RAW_TEMPLATE = ROOT / "data" / "raw" / "manual_downloads" / "manual_download_manifest_template.csv"
RAW_MANIFEST = ROOT / "data" / "raw" / "manual_downloads" / "manual_download_manifest.csv"

PILOT_PLATFORMS = {"NCS", "Foundit", "Shine", "Indeed India"}
PILOT_CITIES = {"Bengaluru", "Delhi", "Mumbai", "Kolkata", "Hyderabad"}
PILOT_QUERIES = {"work from home jobs", "remote jobs", "hybrid jobs"}

OUTPUT_COLUMNS = [
    "platform",
    "city",
    "district",
    "state",
    "query",
    "source_url",
    "collection_date",
    "total_postings_count",
    "flexible_postings_count",
    "remote_postings_count",
    "hybrid_postings_count",
    "WFH_postings_count",
    "extraction_method",
    "notes",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-input", default=str(LOCATION_AUDIT))
    parser.add_argument("--final-output", default=str(FINAL_TEMPLATE))
    parser.add_argument("--raw-output", default=str(RAW_TEMPLATE))
    parser.add_argument("--manifest-output", default=str(RAW_MANIFEST))
    args = parser.parse_args()

    audit = pd.read_csv(args.audit_input) if Path(args.audit_input).exists() else pd.DataFrame()
    if audit.empty:
        out = pd.DataFrame(columns=OUTPUT_COLUMNS)
    else:
        audit = audit.loc[
            audit["platform"].isin(PILOT_PLATFORMS)
            & audit["city_or_town_name"].isin(PILOT_CITIES)
            & audit["query"].isin(PILOT_QUERIES)
            & audit["search_location_accepted"].astype(str).ne("excluded")
        ].copy()
        out = (
            audit.rename(
                columns={
                    "city_or_town_name": "city",
                    "district_name": "district",
                    "state_name": "state",
                    "search_url": "source_url",
                }
            )[
                ["platform", "city", "district", "state", "query", "source_url", "notes"]
            ]
            .sort_values(["platform", "city", "query"])
            .reset_index(drop=True)
        )
        out["collection_date"] = ""
        out["total_postings_count"] = ""
        out["flexible_postings_count"] = ""
        out["remote_postings_count"] = ""
        out["hybrid_postings_count"] = ""
        out["WFH_postings_count"] = ""
        out["extraction_method"] = "manual_count_entry"
        out = out[OUTPUT_COLUMNS]

    Path(args.final_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.raw_output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.final_output, index=False)
    out.to_csv(args.raw_output, index=False)

    manifest_path = Path(args.manifest_output)
    if manifest_path.exists():
        existing = pd.read_csv(manifest_path)
        rename_map = {
            "search_url": "source_url",
            "date_downloaded": "collection_date",
            "manual_total_postings_count": "total_postings_count",
            "manual_flexible_postings_count": "flexible_postings_count",
            "manual_remote_postings_count": "remote_postings_count",
            "manual_hybrid_postings_count": "hybrid_postings_count",
            "manual_WFH_postings_count": "WFH_postings_count",
            "collection_mode": "extraction_method",
            "city_raw": "city",
            "district_raw": "district",
            "state_raw": "state",
            "location": "city",
        }
        for old, new in rename_map.items():
            if old in existing.columns and new not in existing.columns:
                existing[new] = existing[old]
        for col in OUTPUT_COLUMNS:
            if col not in existing.columns:
                existing[col] = ""
        key_cols = ["platform", "city", "district", "state", "query"]
        merged = out.merge(existing[OUTPUT_COLUMNS], on=key_cols, how="left", suffixes=("", "_existing"))
        for col in OUTPUT_COLUMNS:
            if col in key_cols:
                continue
            existing_col = f"{col}_existing"
            if existing_col in merged.columns:
                existing_vals = merged[existing_col].fillna("")
                merged[col] = existing_vals.where(existing_vals.astype(str).ne(""), merged[col])
        manifest = merged[OUTPUT_COLUMNS]
    else:
        manifest = out.copy()

    manifest = manifest.copy()
    manifest["extraction_method"] = "manual_count_entry"
    manifest.to_csv(manifest_path, index=False)

    print(f"Wrote {args.final_output}")
    print(f"Wrote {args.raw_output}")
    print(f"Ensured {manifest_path}")


if __name__ == "__main__":
    main()
