"""
Preprocess cleaned state index CSVs for Firebase upload.

Reads from automated_processing/data/output/<STATE>/
Writes compressed .csv.gz to db/data/output/<STATE>/

Handles both employment and discipline index files:
  <state>_index.csv              → <state>-processed.csv.gz
  <state>-discipline_index.csv   → <state>-discipline-processed.csv.gz
"""

import argparse
import datetime
import gzip
import os
import re

import numpy as np
import pandas as pd


def case_cols(df):
    columns_to_transform = [
        "person_nbr",
        "first_name",
        "last_name",
        "agency_name",
        "start_date",
        "end_date",
        "separation_reason",
        "employment_status",
        "employment_change",
        "race",
        "sex",
        "year_of_birth",
        "middle_name",
        "suffix",
    ]
    for col in columns_to_transform:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.lower().str.strip()
    return df


def clean_column_names(df):
    df.columns = (
        df.columns.str.strip().str.lower().str.replace(r"\s+", "", regex=True)
    )
    return df


def clean_dates(df):
    df.loc[:, "start_date"] = df.start_date.astype(str).str.replace(
        r"\.(.+)", "", regex=True
    )
    df.loc[:, "end_date"] = df.end_date.astype(str).str.replace(
        r"\.(.+)", "", regex=True
    )
    df.loc[:, "end_date"] = df.end_date.astype(str).str.replace(
        r"^nan$", "", regex=True
    )
    return df[~(df.start_date.fillna("") == "")].copy()


def clean_agency_names(df):
    df.loc[:, "agency_name"] = (
        df.agency_name.str.lower()
        .str.strip()
        .str.replace(r"office office$", "office", regex=True)
        .str.replace(r"\bso$", "sheriff's office", regex=True)
        .str.replace(r"\bpd$", "police department", regex=True)
    )
    return df


def apply_proper_casing(df):
    def proper_case(text):
        words = text.split()
        processed_words = []
        for word in words:
            if word.lower() == "sheriff's":
                processed_words.append("Sheriff's")
            elif word.upper() in [
                "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                "JR", "SR",
            ]:
                if word.upper() in ["JR", "SR"]:
                    processed_words.append(word.capitalize())
                else:
                    processed_words.append(word.upper())
            elif word.upper() in ["PD", "SO", "DA", "UC"]:
                processed_words.append(word.upper())
            else:
                processed_words.append(word.capitalize())
        return " ".join(processed_words)

    columns_to_transform = [
        "first_name",
        "last_name",
        "middle_name",
        "agency_name",
        "separation_reason",
        "employment_status",
        "employment_change",
        "race",
        "sex",
        "suffix",
    ]
    for col in columns_to_transform:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: proper_case(str(x)) if pd.notna(x) else x
            )
    return df


def check_required_columns(df):
    required_columns = [
        "agency_name",
        "first_name",
        "last_name",
        "start_date",
        "end_date",
    ]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(missing)}"
        )
    return df


def check_empty_values(df):
    required_columns = [
        "agency_name",
        "first_name",
        "last_name",
        "start_date",
        "end_date",
    ]
    for col in required_columns:
        empty = df[col].isnull() | (df[col] == "")
        if empty.any():
            print(
                f"  Warning: '{col}' has {empty.sum()} empty values "
                f"({empty.mean():.1%})"
            )
    return df


def filter_anons(df):
    if "last_name" not in df.columns:
        return df
    return df.loc[
        ~df.last_name.str.lower().str.contains("withheld", na=False)
    ].copy()


def sort_by_uid(df):
    if "person_nbr" in df.columns:
        df = df.sort_values("person_nbr")
    return df


def apply_transformations(df):
    return (
        df.pipe(clean_column_names)
        .pipe(case_cols)
        .pipe(clean_dates)
        .pipe(clean_agency_names)
        .pipe(check_empty_values)
        .pipe(apply_proper_casing)
        .pipe(filter_anons)
        .pipe(check_required_columns)
        .pipe(sort_by_uid)
    )


def process_file(input_path, output_path, state_name, force=False):
    """Preprocess a single index CSV and write a compressed .csv.gz."""
    if os.path.exists(output_path) and not force:
        print(f"  Skipping (already exists): {os.path.basename(output_path)}")
        return "skipped"

    try:
        df = pd.read_csv(input_path, low_memory=False)
        print(f"  Read {len(df):,} rows from {os.path.basename(input_path)}")

        df = apply_transformations(df)

        # Attach state and document_id
        formatted_state = state_name.lower().replace(" ", "-")
        df["state"] = formatted_state
        df["person_nbr"] = df["person_nbr"].astype(str)
        df["document_id"] = df["state"] + "_" + df["person_nbr"]

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with gzip.open(output_path, "wt", encoding="utf-8") as gz_file:
            df.to_csv(gz_file, index=False)

        print(
            f"  Written {len(df):,} rows → {os.path.basename(output_path)}"
        )
        return "success"
    except Exception as e:
        print(f"  Error: {e}")
        return "failed"


def find_index_files(input_dir, state_name):
    """
    Return a list of (input_path, output_filename) tuples for all index CSVs
    found in states/<STATE>/output/.

    Scans for any *_index.csv files rather than predicting names, so it works
    regardless of whether the file uses the abbreviation (ga_index.csv) or the
    full name (georgia_index.csv).

      <stem>_index.csv  →  <stem>-processed.csv.gz
    """
    output_dir = os.path.join(input_dir, state_name, "output")
    if not os.path.isdir(output_dir):
        return []

    found = []
    for fname in sorted(os.listdir(output_dir)):
        if not fname.endswith("_index.csv"):
            continue
        src_path = os.path.join(output_dir, fname)
        # georgia_index.csv            → georgia-processed.csv.gz
        # georgia-discipline_index.csv → georgia-discipline-processed.csv.gz
        stem = fname.replace("_index.csv", "")
        dst_name = f"{stem}-processed.csv.gz"
        found.append((src_path, dst_name))
    return found


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess cleaned state index CSVs for Firebase upload"
    )
    parser.add_argument(
        "--input-dir",
        default="../../states",
        help=(
            "Root states/ directory — expects "
            "states/<STATE>/data/output/<state>_index.csv "
            "(default: ../../states)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="../data/output",
        help="Output directory for processed .csv.gz files (default: ../data/output)",
    )
    parser.add_argument(
        "--states",
        nargs="+",
        help="Process only these states (default: all states found in input-dir)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess even if output already exists",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input_dir):
        raise ValueError(f"Input directory not found: {args.input_dir}")
    os.makedirs(args.output_dir, exist_ok=True)

    # Determine which states to process
    if args.states:
        state_dirs = args.states
    else:
        state_dirs = [
            d
            for d in os.listdir(args.input_dir)
            if os.path.isdir(os.path.join(args.input_dir, d))
        ]

    if not state_dirs:
        print(f"No state directories found in {args.input_dir}")
        return

    print(f"Processing {len(state_dirs)} state(s): {', '.join(state_dirs)}\n")

    results = {"success": [], "skipped": [], "failed": []}

    for state in state_dirs:
        print(f"[{state}]")
        files = find_index_files(args.input_dir, state)

        if not files:
            print(f"  No index CSVs found — skipping")
            results["skipped"].append(state)
            continue

        state_output_dir = os.path.join(args.output_dir, state)

        for input_path, output_name in files:
            output_path = os.path.join(state_output_dir, output_name)
            status = process_file(
                input_path, output_path, state, force=args.force
            )
            if status == "success":
                results["success"].append(f"{state}/{output_name}")
            elif status == "skipped":
                results["skipped"].append(f"{state}/{output_name}")
            else:
                results["failed"].append(f"{state}/{output_name}")
        print()

    print("=" * 50)
    print(f"Done. Success: {len(results['success'])}  "
          f"Skipped: {len(results['skipped'])}  "
          f"Failed: {len(results['failed'])}")
    if results["failed"]:
        print("Failed:")
        for f in results["failed"]:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
