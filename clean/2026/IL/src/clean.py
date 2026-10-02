"""Clean the Illinois (ILETSB) employment table into the index schema."""

import os
import re

import pandas as pd


INPUT_PATH = "../data/input/26-327.xlsx"
INPUT_SHEET = "Employment"
OUTPUT_PATH = "../data/output/illinois_index.csv"
DROPPED_HIRE_PATH = "../data/output/review/unusable_hire_date.csv"
DROPPED_END_PATH = "../data/output/review/end_before_start.csv"
DROPPED_BORN_PATH = "../data/output/review/hired_before_born.csv"
BATCH_END_PATH = "../data/output/review/batch_end_date_2010-01-01.csv"

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


def to_iso(series):
    """Excel datetimes to YYYY-MM-DD strings; blanks stay empty."""
    return (
        pd.to_datetime(series, errors="coerce")
        .dt.strftime("%Y-%m-%d")
        .fillna("")
    )


def blank_unknown_birth_years(df):
    """Blank out known unusable birth years, keeping the row."""
    bad = df["year_of_birth"].isin(["1901", "199"])
    print(f"Blanked unknown year_of_birth (kept row): {bad.sum():,}")
    df.loc[bad, "year_of_birth"] = ""
    return df


def unusable_hire_date(df):
    """Rows with an empty or known-unusable hire date."""
    unknown_hire_dates = ["1900-01-01", "1901-01-01", "1902-01-01"]
    return df["start_date"].eq("") | df["start_date"].isin(unknown_hire_dates)


def collapse_contiguous_stints(df):
    """Merge back-to-back stints at the same agency into one row."""
    key = ["person_nbr", "agency_name"]
    still_employed = pd.Timestamp("2262-01-01")

    work = df.copy()
    work["_start"] = pd.to_datetime(work["start_date"])
    work["_end"] = pd.to_datetime(work["end_date"].replace("", None))
    work = work.sort_values(key + ["_start", "_end"])

    # An open end date on a row that is followed by another row at the
    # same agency was never closed; treat it as ending at the next start.
    grouped = work.groupby(key, sort=False)
    work["_eff_end"] = (
        work["_end"].fillna(grouped["_start"].shift(-1)).fillna(still_employed)
    )
    previous_end = grouped["_eff_end"].transform(lambda s: s.cummax().shift(1))
    gap = work["_start"] - previous_end
    work["_stint"] = grouped.cumcount().where(
        previous_end.isna() | gap.gt(pd.Timedelta(days=1))
    )
    work["_stint"] = grouped["_stint"].ffill()

    # The most recent row supplies rank, status and the rest; an empty
    # separation_reason falls back to the latest one present.
    agg = {c: "last" for c in df.columns if c not in key}
    agg["_start"] = "min"
    agg["_eff_end"] = "max"
    agg["separation_reason"] = lambda s: next(
        (v for v in reversed(s.tolist()) if v != ""), ""
    )

    out = work.groupby(key + ["_stint"], sort=False).agg(agg).reset_index()
    out["start_date"] = out["_start"].dt.strftime("%Y-%m-%d")
    out["end_date"] = out["_eff_end"].dt.strftime("%Y-%m-%d")
    out.loc[out["_eff_end"].eq(still_employed), "end_date"] = ""
    print(f"Collapsed contiguous stints: {len(df):,} → {len(out):,} rows")
    return out[df.columns]


def hired_before_born(df):
    """Rows whose hire year is at or before the birth year."""
    hire_year = pd.to_numeric(df["start_date"].str[:4], errors="coerce")
    birth_year = pd.to_numeric(df["year_of_birth"], errors="coerce")
    return birth_year.notna() & hire_year.notna() & hire_year.le(birth_year)


def main():
    raw = pd.read_excel(
        INPUT_PATH,
        sheet_name=INPUT_SHEET,
        keep_default_na=False,
        na_values=[],
    )
    df = raw.rename(columns=COLUMN_MAP)[list(COLUMN_MAP.values())]
    for col in ["start_date", "end_date"]:
        df[col] = to_iso(df[col])
    df = df.apply(lambda col: col.astype(str).str.strip())

    df["person_nbr"] = df["person_nbr"].str.lower()
    df["state"] = "il"

    # Names keep the source's casing — db/preprocess/ owns proper-casing.
    df["full_name"] = (
        (df["last_name"] + ", " + df["first_name"] + " " + df["suffix"])
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.lower()
    )

    df["agency_name"] = df["agency_name"].map(
        lambda v: expand(v, AGENCY_ABBREVIATIONS)
    )
    df["rank"] = df["rank"].map(lambda v: expand(v, RANK_ABBREVIATIONS))

    # Drop rows with no ID, no name or no agency.
    df = df[df["person_nbr"].ne("") & df["last_name"].ne("")]
    df = df[~df["agency_name"].str.lower().isin(NON_AGENCY_VALUES)]

    os.makedirs(os.path.dirname(DROPPED_HIRE_PATH), exist_ok=True)

    unusable = unusable_hire_date(df)
    df[unusable].to_csv(DROPPED_HIRE_PATH, index=False)
    print(
        f"Unusable hire date (dropped): {unusable.sum():,} "
        f"({unusable.sum() / len(df):.1%}) → {DROPPED_HIRE_PATH}"
    )
    df = df[~unusable]

    bad_end = df["end_date"].ne("") & (df["end_date"] < df["start_date"])
    df[bad_end].to_csv(DROPPED_END_PATH, index=False)
    print(
        f"end_date before start_date (dropped): {bad_end.sum():,} "
        f"({bad_end.sum() / len(df):.1%}) → {DROPPED_END_PATH}"
    )
    df = df[~bad_end]

    born = hired_before_born(df)
    df[born].to_csv(DROPPED_BORN_PATH, index=False)
    print(
        f"Hired before born (dropped): {born.sum():,} "
        f"({born.sum() / len(df):.1%}) → {DROPPED_BORN_PATH}"
    )
    df = df[~born]

    df = blank_unknown_birth_years(df.copy())

    df = df.drop_duplicates(
        subset=["person_nbr", "agency_name", "start_date", "end_date"]
    )
    df = collapse_contiguous_stints(df)

    # A batch write, not real separations. Kept, but exported for
    # review; see README.
    batch_end_date = "2010-01-01"
    batch = df["end_date"].eq(batch_end_date)
    df[batch].to_csv(BATCH_END_PATH, index=False)
    print(
        f"Batch end_date {batch_end_date} (kept): {batch.sum():,} "
        f"({batch.sum() / len(df):.1%}) → {BATCH_END_PATH}"
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
            print(f"Warning: {col} has {empty:,} empty ({empty / len(df):.1%})")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df):,} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
