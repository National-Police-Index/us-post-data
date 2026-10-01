# vim: set ts=4 sts=0 sw=4 si fenc=utf-8 et:
# vim: set fdm=marker fmr={{{,}}} fdl=0 foldcolumn=4:
# Authors:     TS
# Maintainers: TS
# Copyright:   2026, HRDAG, GPL v2 or later
# =========================================

"""Clean the MN POST 2026 public officer-and-agency dataset.

Input (``data/input/``):

- ``Officer-with-Agency-Data-Public-Only-2026-08-04_Muckrock_request.xlsx``

Raw layout (sheet ``Officer-with-Agency-Data-Public``):

- Header on row 1: ``B=License Number↑``, ``D=Last Name``, ``E=First
  Name``, ``F=Law Enforcement Agency``, ``G=Status``, ``H=Start Date``,
  ``I=Date Terminated``.  Columns A, C and J are empty.
- One block per officer: the license number sits on the block's first
  row; the officer's other stints repeat the name/agency/status/dates
  but leave the license blank (forward-filled below).
- A ``Subtotal / Count / N`` row closes each block and a final
  ``Total / Count`` row closes the sheet; both are dropped.
- ``Status`` is ``Active`` or ``Terminated``; a blank ``Date Terminated``
  means still employed.
- The source puts suffixes in the last-name column (``Ryan Ii``,
  ``Walls Jr.``) — they are split off into ``suffix``.
"""

# {{{ imports

import argparse
import os
import re

import pandas as pd

# }}}
# {{{ constants

SOURCE_FILE = (
    "Officer-with-Agency-Data-Public-Only-2026-08-04_Muckrock_request.xlsx"
)
# Positionally take B..I; A, C and J are empty in every data row.
RAW_COLUMNS = [
    "person_nbr",
    "_blank",
    "last_name",
    "first_name",
    "agency_name",
    "employment_status",
    "start_date",
    "end_date",
]

OUTPUT_COLUMNS = [
    "person_nbr",
    "full_name",
    "first_name",
    "last_name",
    "suffix",
    "agency_name",
    "employment_status",
    "start_date",
    "end_date",
    "state",
]

# Summary rows closing each officer block / the sheet.
SUMMARY = {"Subtotal", "Total"}

# A leading suffix attached to the last name ("Ryan Ii", "Walls Jr.",
# "Hankee, Jr.", "Robinson- Jr"). Separator may be space, comma or hyphen.
SUFFIX_RE = re.compile(
    r"^(.+?)[,\s-]+(jr|sr|i{1,3}|iv|v|vi{0,3}|ix?)\s*\.?$", re.IGNORECASE
)
SUFFIX_CANON = {"jr": "Jr", "sr": "Sr"}

AGENCY_ABBREVIATIONS = [
    (r"\bDept\.?", "Department"),
    (r"\bCo\.?", "County"),
    (r"\bDPS\b", "Department Of Public Safety"),
]


# }}}
# {{{ helpers


def safe_date(val):
    """Return YYYY-MM-DD or '' for missing / unparseable dates."""
    s = str(val).strip()
    if not s or s in ("nan", "NaT", "None", "1/1/0001", "0000-00-00"):
        return ""
    ts = pd.to_datetime(s, errors="coerce")
    return "" if pd.isna(ts) else ts.strftime("%Y-%m-%d")


def split_suffix(last_name):
    """Split a trailing suffix off the last name ('Ryan Ii' -> Ryan / II)."""
    s = str(last_name).strip()
    m = SUFFIX_RE.match(s)
    if not m:
        return s, ""
    base, suffix = m.group(1).strip(), m.group(2)
    canon = SUFFIX_CANON.get(suffix.lower(), suffix.upper())
    return base, canon


def clean_agency_name(name):
    s = re.sub(r"\s+", " ", str(name)).strip()
    for pattern, repl in AGENCY_ABBREVIATIONS:
        s = re.sub(pattern, repl, s, flags=re.IGNORECASE)
    return s


def parse_suffixes(df):
    parts = df["last_name"].apply(split_suffix)
    df["last_name"] = parts.str[0]
    df["suffix"] = parts.str[1]
    return df


# }}}
# {{{ pipeline steps


def load(input_dir):
    """Read the xlsx into a frame, one row per stint, license filled in."""
    df = pd.read_excel(os.path.join(input_dir, SOURCE_FILE), header=0).iloc[
        :, 1:9
    ]
    df.columns = RAW_COLUMNS
    df = df.drop(columns=["_blank"])
    # Drop the summary rows and any junk rows that carry no person data.
    df = df[~df["person_nbr"].isin(SUMMARY)]
    df = df.dropna(subset=["last_name", "first_name", "agency_name"], how="all")
    # License number sits on the first row of each officer block.
    df["person_nbr"] = df["person_nbr"].ffill()
    print(f"  {SOURCE_FILE}: {len(df):,} rows")
    return df


def normalize(df):
    df = df.copy()
    df["person_nbr"] = df["person_nbr"].astype(str).str.strip().str.lower()
    df["full_name"] = ""
    df["first_name"] = df["first_name"].fillna("").astype(str).str.strip()
    df["last_name"] = df["last_name"].fillna("").astype(str).str.strip()
    df["agency_name"] = df["agency_name"].fillna("").apply(clean_agency_name)
    df["employment_status"] = (
        df["employment_status"].fillna("").astype(str).str.strip()
    )
    df["start_date"] = df["start_date"].apply(safe_date)
    df["end_date"] = df["end_date"].apply(safe_date)
    df["state"] = "mn"
    df = parse_suffixes(df)
    df["full_name"] = (
        (
            df["last_name"]
            + ", "
            + df["first_name"]
            + df["suffix"].where(df["suffix"] == "", other=" " + df["suffix"])
        )
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    return df



def resolve_duplicates(df, review_dir):
    """One row per (person, agency, start_date).

    The export lists the same stint more than once with different end
    dates (overlapping employment records in the source). The row with
    the latest end date wins (closed beats open).
    """
    key = ["person_nbr", "agency_name", "start_date"]
    dup_all = df.duplicated(subset=key, keep=False)
    df[dup_all].sort_values(key).to_csv(
        os.path.join(review_dir, "duplicate_rows.csv"), index=False
    )
    open_end = df["end_date"] == ""
    ordered = df.assign(_open=open_end).sort_values(
        key + ["_open", "end_date"], ascending=[True, True, True, False, True]
    )
    kept = ordered.drop_duplicates(subset=key, keep="last").drop(
        columns="_open"
    )
    print(
        f"Duplicates on {key}: {len(df) - len(kept):,} dropped "
        f"({dup_all.sum():,} rows in {df[dup_all].groupby(key).ngroups:,} groups)"
    )
    return kept


# }}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="input")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    review_dir = os.path.join(args.output_dir, "review")
    os.makedirs(review_dir, exist_ok=True)

    print("Loading:")
    df = normalize(load(args.input_dir))

    no_start = df["start_date"] == ""
    print(f"\nRows with empty start_date (dropped): {no_start.sum():,}")
    df = df[~no_start]

    df = resolve_duplicates(df, review_dir)

    # Sanity checks — reported, not silently fixed.
    bad = (df["end_date"] != "") & (df["end_date"] < df["start_date"])
    old = (df["start_date"] != "") & (df["start_date"] <= "1900-01-01")
    suspicious = df[bad | old]
    if len(suspicious):
        suspicious.to_csv(
            os.path.join(review_dir, "suspicious_dates.csv"), index=False
        )
        print(
            f"Rows with end_date < start_date (kept): {bad.sum():,}; "
            f"start_date <= 1900-01-01 (kept): {old.sum():,}"
        )
    for col in ["person_nbr", "first_name", "last_name", "agency_name"]:
        n = (df[col] == "").sum()
        if n:
            print(f"Warning: {col} has {n:,} empty values")

    df = df[OUTPUT_COLUMNS].sort_values(["person_nbr", "start_date"])
    out = os.path.join(args.output_dir, "mn_index.csv")
    df.to_csv(out, index=False)
    print(
        f"\nWrote {len(df):,} rows, {df.person_nbr.nunique():,} officers, "
        f"{df.agency_name.nunique():,} agencies → {out}"
    )


if __name__ == "__main__":
    main()
