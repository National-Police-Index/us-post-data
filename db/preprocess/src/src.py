import argparse
import datetime
import gzip
import os

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
        else:
            print(
                f"Column '{col}' not found. Skipping transformation for this column."
            )
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
        # Split the text into words
        words = text.split()
        # Process each word
        processed_words = []
        for word in words:
            # Special handling for Sheriff's
            if word.lower() == "sheriff's":
                processed_words.append("Sheriff's")
            # Special handling for suffixes and roman numerals
            elif word.upper() in [
                "I",
                "II",
                "III",
                "IV",
                "V",
                "VI",
                "VII",
                "VIII",
                "IX",
                "X",
                "JR",
                "SR",
            ]:
                if word.upper() in ["JR", "SR"]:
                    processed_words.append(word.capitalize())
                else:
                    processed_words.append(word.upper())
            # Special handling for abbreviations like 'PD' for Police Department
            elif word.upper() in ["PD", "SO", "DA", "UC"]:
                processed_words.append(word.upper())
            # General case: capitalize first letter, lowercase the rest
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
        else:
            print(
                f"Column '{col}' not found. Skipping proper casing for this column."
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
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"No df returned. Missing required columns: {', '.join(missing_columns)}"
        )
    else:
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
        if df[col].isnull().any() or (df[col] == "").any():
            print(f"Warning: Column '{col}' contains empty values or NaNs")
    return df


def assign_stint_id(stints: pd.DataFrame) -> pd.DataFrame:
    """Takes multiple contiguous stints for an individual at an agency, and assigns a stint_id
    (assumes `stints` is ordered by start_date)
    """
    if len(stints) > 1:
        return stints
    today = pd.to_datetime(datetime.date.today(), utc=False)
    stints["usable_end_date"] = today
    stints["new_stint"] = (
        stints.start_date - stints.usable_end_date.shift(1, fill_value=today)
    ) > pd.to_timedelta(1, "days")
    stints["stint_id"] = np.cumsum(stints.new_stint)
    stints.drop(["new_stint", "usable_end_date"], inplace=True, axis=1)
    return stints


def clean_date(date_str: str):
    try:
        year = int(date_str[:4])
        if year < 1800 or year > 2100:  # Adjust the range as needed
            return None
        return date_str
    except ValueError:
        return None


def collapse_contiguous_stints(
    df: pd.DataFrame, by_cols: list = None
) -> pd.DataFrame:
    if not by_cols:
        by_cols = ["person_nbr", "first_name", "last_name", "agency_name"]
    # assume missing end dates are current employment, and use today's date for
    # sorting purposes
    # assert df.start_date.notna().all()
    one_day = pd.to_timedelta(1, "days")
    today = pd.to_datetime(datetime.date.today(), utc=False)
    ancient = pd.to_datetime("1800-01-01", utc=False)
    working = df.sort_values(
        ["person_nbr", "agency_name", "start_date"], inplace=False
    )
    working["start_date"] = working["start_date"].apply(clean_date)
    working["end_date"] = working["end_date"].apply(clean_date)
    working["start_date"] = pd.to_datetime(
        working.start_date, utc=False
    ).fillna(ancient)
    working["end_date"] = pd.to_datetime(working.end_date, utc=False).fillna(
        today
    )
    working.loc[working.start_date < ancient, "start_date"] = ancient
    working.loc[working.end_date > today, "end_date"] = today
    grouped = working.groupby(by_cols)
    working["prv_end"] = grouped["end_date"].shift(1, fill_value=today)
    working["new_stint"] = (working.start_date - working.prv_end) > one_day
    working["stint_id"] = grouped["new_stint"].cumsum()
    collapsible = working.groupby(by_cols + ["stint_id"])
    summaries = {k: lambda x: x.tail(1) for k in df.columns if k not in by_cols}
    summaries["start_date"] = "min"
    summaries["end_date"] = "max"
    out = collapsible.aggregate(summaries).reset_index()
    out["start_date"] = out["start_date"].dt.strftime("%Y-%m-%d")
    out["end_date"] = out["end_date"].dt.strftime("%Y-%m-%d")
    out.loc[out.end_date == today.strftime("%Y-%m-%d"), "end_date"] = None
    out.loc[out.start_date == ancient.strftime("%Y-%m-%d"), "start_date"] = None
    return out.drop(["stint_id"], axis=1, inplace=False)


def filter_anons(df: pd.DataFrame) -> pd.DataFrame:
    if "last_name" not in df.columns:
        return df
    return df.loc[~df.last_name.str.lower().str.contains("withheld")].copy()


def sort_by_uid(df):
    if "person_nbr" in df.columns:
        df = df.sort_values("person_nbr")
    return df


def apply_transformations(df, state_name):
    """Apply transformations based on state and available columns"""
    df = (
        df.pipe(case_cols)
        .pipe(clean_column_names)
        .pipe(clean_dates)
        .pipe(clean_agency_names)
        .pipe(check_empty_values)
        .pipe(apply_proper_casing)
        .pipe(filter_anons)
        .pipe(check_required_columns)
        .pipe(sort_by_uid)
    )

    # Only apply collapse_contiguous_stints for California
    if state_name.lower() == "california":
        df = df.pipe(collapse_contiguous_stints)

    return df


def process_state_data(state_name, input_dir, output_dir, force=False):
    """
    Process state data and prepare it for Firestore upload with optimized document IDs
    """
    # Create state-specific output directory
    state_output_dir = os.path.join(output_dir, state_name)
    os.makedirs(state_output_dir, exist_ok=True)

    input_file_path = os.path.join(
        input_dir, state_name, f"{state_name}_index.csv"
    )
    output_file_path = os.path.join(
        state_output_dir, f"{state_name}-processed.csv.gz"
    )

    # Check if output file already exists
    if os.path.exists(output_file_path) and not force:
        print(f"Skipping {state_name} - output file already exists")
        return "skipped"

    try:
        df = pd.read_csv(input_file_path)
        df = apply_transformations(df, state_name)

        # Add state field - using simple string replace
        formatted_state = state_name.lower().replace(" ", "-")
        df["state"] = formatted_state

        # Ensure person_nbr is string and pad with zeros
        df["person_nbr"] = df["person_nbr"].astype(str)

        # Create document_id field
        df["document_id"] = df["state"] + "_" + df["person_nbr"]

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

        with gzip.open(output_file_path, "wt", encoding="utf-8") as gz_file:
            df.to_csv(gz_file, index=False)

        print(f"Successfully processed {state_name}")
        return "success"
    except Exception as e:
        print(f"Error processing {state_name}: {str(e)}")
        return "failed"


def main():
    parser = argparse.ArgumentParser(description="Process state data files")
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Input directory containing state subdirectories",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Output directory for processed files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing of files even if output exists",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input_dir):
        raise ValueError(f"Input directory does not exist: {args.input_dir}")
    os.makedirs(args.output_dir, exist_ok=True)

    successful_states = []
    failed_states = []
    skipped_states = []

    state_dirs = [
        d
        for d in os.listdir(args.input_dir)
        if os.path.isdir(os.path.join(args.input_dir, d))
    ]

    print(f"Found {len(state_dirs)} state directories to process")

    for state in state_dirs:
        result = process_state_data(
            state, args.input_dir, args.output_dir, args.force
        )
        if result == "success":
            successful_states.append(state)
        elif result == "skipped":
            skipped_states.append(state)
        else:  # result == "failed"
            failed_states.append(state)

    print("\nProcessing complete!")
    print(f"Successfully processed: {len(successful_states)} states")
    print(f"Skipped (already processed): {len(skipped_states)} states")
    print(f"Errors encountered: {len(failed_states)} states")

    if skipped_states:
        print("\nStates skipped (use --force to reprocess):")
        for state in skipped_states:
            print(f"  - {state}")

    if failed_states:
        print("\nStates that failed processing:")
        for state in failed_states:
            print(f"  - {state}")


if __name__ == "__main__":
    main()
