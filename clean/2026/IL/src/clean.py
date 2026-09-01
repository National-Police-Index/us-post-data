"""Clean the Illinois (ILETSB) employment table into the index schema."""

import os
import re

import pandas as pd

INPUT_PATH = "../data/input/Employment-Table 1.csv"
OUTPUT_PATH = "../data/output/illinois_index.csv"

COLUMN_MAP = {
    "PTBID": "person_nbr",
    "LastName": "last_name",
    "FirstName": "first_name",
    "MiddleName": "middle_name",
    "Suffix": "suffix",
    "BirthYear": "year_of_birth",
    "Race": "race",
    "Gender": "sex",
    "Education": "education",
    "Employer": "agency_name",
    "Branch": "type",
    "Status": "employment_status",
    "Rank": "rank",
    "Hired": "start_date",
    "Separated": "end_date",
    "Reason": "separation_reason",
}

AGENCY_ABBREVIATIONS = [
    (r"\bDEPT\b\.?", "DEPARTMENT"),
    (r"\bDEP\b", "DEPARTMENT"),
    (r"\bPD\b", "POLICE DEPARTMENT"),
    (r"\bCO\b\.?", "COUNTY"),
    (r"\bCOMM\.?\s+COLL(EGE)?\b", "COMMUNITY COLLEGE"),
    (r"\bCOLL\b", "COLLEGE"),
    (r"\bCONSERV\b", "CONSERVATION"),
    (r"\bCONV\b", "CONSERVATION"),
    (r"\bDIST\b\.?", "DISTRICT"),
    (r"\bPRES\b", "PRESERVE"),
    (r"\bAUTH\b", "AUTHORITY"),
    (r"\bUNIV\b", "UNIVERSITY"),
    (r"\bOFFC\b\.?", "OFFICE"),
    (r"\bCRT\b", "COURT"),
    (r"\bRAILRD\b", "RAILROAD"),
    (r"\bST\.\s", "SAINT "),
    (r"\bIL\b", "ILLINOIS"),
    (r"\bFIN\b\.?", "FINANCIAL"),
    (r"\bPROFESS\b\.?", "PROFESSIONAL"),
    (r"\bREG\b\.?", "REGULATION"),
    (r"\bVET\b\.?", "VETERANS"),
    (r"\bPUB\b\.?", "PUBLIC"),
    (r"\bCENTR\b\.?", "CENTER"),
]

RANK_ABBREVIATIONS = [
    (r"\bASST\b\.?", "ASSISTANT"),
    (r"\bCORR\b\.?", "CORRECTIONS"),
    (r"\bAGT\b\.?", "AGENT"),
]

NON_AGENCY_VALUES = {"", "unknown", "n/a", "none", "pending"}


def expand(text, rules):
    s = re.sub(r"\s+", " ", str(text)).strip().upper()
    for pattern, replacement in rules:
        s = re.sub(pattern, replacement, s)
    return re.sub(r"\s+", " ", s).strip()


def safe_dates(series):
    """Parse m/d/yy to YYYY-MM-DD, rolling 2-digit years that land in the
    future back a century (the source goes back to the 1960s, so '3/1/65'
    is 1965, not 2065)."""
    dates = pd.to_datetime(
        series.replace("", pd.NA), format="mixed", errors="coerce"
    )
    future = dates > pd.Timestamp.today()
    dates[future] = dates[future] - pd.DateOffset(years=100)
    return dates.dt.strftime("%Y-%m-%d").fillna("")


def main():
    df = pd.read_csv(INPUT_PATH, dtype=str, keep_default_na=False)
    df = df.rename(columns=COLUMN_MAP)[list(COLUMN_MAP.values())]
    df = df.apply(lambda col: col.str.strip())

    df["person_nbr"] = df["person_nbr"].str.lower()
    df["state"] = "il"

    # Names keep the source's casing — db/preprocess/ owns proper-casing.
    df["full_name"] = (
        df["last_name"] + ", " + df["first_name"] + " " + df["suffix"]
    ).str.strip().str.replace(r"\s+", " ", regex=True).str.lower()

    df["agency_name"] = df["agency_name"].map(
        lambda v: expand(v, AGENCY_ABBREVIATIONS)
    )
    df["rank"] = df["rank"].map(lambda v: expand(v, RANK_ABBREVIATIONS))

    df["start_date"] = safe_dates(df["start_date"])
    df["end_date"] = safe_dates(df["end_date"])

    # Drop unusable rows: no ID, no name, no agency, no start date.
    df = df[df["person_nbr"].ne("") & df["last_name"].ne("")]
    df = df[~df["agency_name"].str.lower().isin(NON_AGENCY_VALUES)]
    df = df[df["start_date"].ne("")]
    df = df.drop_duplicates(
        subset=["person_nbr", "agency_name", "start_date", "end_date"]
    )

    required = [
        "person_nbr",
        "first_name",
        "last_name",
        "agency_name",
        "start_date",
        "end_date",
    ]
    missing = [c for c in required if c not in df.columns]
    assert not missing, f"Missing required columns: {missing}"
    assert (df["start_date"] != "").all(), "start_date must not be empty"
    for col in required:
        empty = (df[col] == "").sum()
        if empty:
            print(f"Warning: {col} has {empty:,} empty ({empty/len(df):.1%})")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df):,} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
