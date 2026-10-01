"""Clean the KS POST 2026 release and append it to the prior KS index.

Inputs (``data/input/``):

- ``ks-2024-index.csv`` — the previously cleaned KS index (1979–2024). Its
  rows are carried forward except those with ``start_date >= 2024-11-01``,
  which are superseded by the Nov–Dec 2024 file below.
- ``Nov-Dec 2024 Employment History.xls``
- ``2025 Employment History.xls``
- ``2026 Employment History.xls``
"""

import argparse
import os
import re

import pandas as pd
from nameparser import HumanName
from nameparser.config import CONSTANTS


OLD_INDEX = "ks-2024-index.csv"
NEW_FILES = [
    "Nov-Dec 2024 Employment History.xls",
    "2025 Employment History.xls",
    "2026 Employment History.xls",
]
# Rows in the old index from this date on are re-reported (with updated end
# dates) in the Nov-Dec 2024 file, so they are dropped from the old index.
SUPERSEDE_FROM = "2024-11-01"
# Kansas uses this as "no end date" (currently employed).
OPEN_END_DATE = "1/1/0001"
STATUS_MAP = {"F": "Full-Time", "P": "Part-Time"}

OUTPUT_COLUMNS = [
    "person_nbr",
    "full_name",
    "first_name",
    "middle_name",
    "last_name",
    "suffix",
    "agency_name",
    "rank",
    "employment_status",
    "start_date",
    "end_date",
    "state",
]

TEST_AGENCY_RE = re.compile(r"^test", re.IGNORECASE)
TEST_NAME_RE = re.compile(r"^(test\b|testt+|testm+|mpa mpb)", re.IGNORECASE)

AGENCY_RENAMES = {
    "kscpost": "Kansas Commission on Peace Officers' Standards and Training",
    # Same institution, renamed between exports.
    "kansas city ks comm college campus police": (
        "Kansas City Kansas Community College Police"
    ),
}
AGENCY_ABBREVIATIONS = [
    (r"\bDept\b\.?", "Department"),
    (r"\bUniv\b\.?", "University"),
    (r"\bComm College\b", "Community College"),
    (r"\bComm\b", "Commission"),
    (r"\bCo\b", "County"),
    (r"\bDist Attrny\b", "District Attorney"),
    (r"\bDist\b", "District"),
    (r"\bDiv\b", "Division"),
    (r"\bSec\b", "Security"),
    (r"\bMed\b", "Medical"),
    (r"\bKS\b", "Kansas"),
    (r"\bUSD\s*#?\s*(\d+)", r"Unified School District #\1"),
    (r"\bMTAA\b", "Metropolitan Topeka Airport Authority"),
    (r"\bPD\b", "Police Department"),
]


RANK_CODES = {
    "TRPR": "Trooper",
    "TPPR": "Trooper",
    "PRGR": "Park Ranger",
    "PKMR": "Park Manager",
    "NRO": "Natural Resource Officer",
    "ENF AGT": "Enforcement Agent",
    "AGT": "Agent",
    "SAGT IC": "Special Agent In Charge",
    "INV": "Investigator",
    "INVR": "Investigator",
    "CHF INV": "Chief Investigator",
    "INT CHF": "Interim Chief",
    "ACT CHF": "Acting Chief",
    "ACTCHF": "Acting Chief",
    "DPTY CHF": "Deputy Chief",
    "DPT CHF": "Deputy Chief",
    "DCHF": "Deputy Chief",
    "CDPTY": "Chief Deputy",
    "CHF DPTY": "Chief Deputy",
    "DPT": "Deputy",
    "DTPY": "Deputy",
    "USHF": "Undersheriff",
    "PRL OFF": "Patrol Officer",
    "PRTL OFF": "Patrol Officer",
    "SRO": "School Resource Officer",
    "LT COL": "Lieutenant Colonel",
    "CMDR": "Commander",
    "SUPT": "Superintendent",
    "SUPR": "Supervisor",
    "MNGR": "Manager",
    "LND MGR": "Land Manager",
    "LND MNGR": "Land Manager",
    "ALND MGR": "Assistant Land Manager",
    "DRCT": "Director",
    "DDIR": "Deputy Director",
    "ADIR": "Assistant Director",
    "ASDIR": "Assistant Director",
    "INT DIR": "Interim Director",
    "MSRL": "Marshal",
    "DPTY MRSL": "Deputy Marshal",
    "FMRSL": "Fire Marshal",
    "DPTY FMRSL": "Deputy Fire Marshal",
    "BLF": "Bailiff",
    "CRT BLF": "Court Bailiff",
    "DPTY BLF": "Deputy Bailiff",
    "CRT OFF": "Court Officer",
    "SECO": "Security Officer",
}

# nameparser treats "Marquis" as a title; here it is a first name.
CONSTANTS.titles.remove("marquis")
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}
# Leading particles that belong to the first name ("De Anna", "La Toya").
FIRST_NAME_PARTICLES = {"de", "la", "le", "da"}


def load_new(input_dir):
    """Read the three Employment History xls files into one frame."""
    frames = []
    for fname in NEW_FILES:
        # Title block occupies rows 1-5; data columns are C..K with blank
        # spacer columns in between.
        df = pd.read_excel(
            os.path.join(input_dir, fname), skiprows=5, usecols="C:K"
        ).dropna(axis=1, how="all")
        df.columns = df.columns.str.lower().str.replace(" ", "_")
        df["source_file"] = fname
        frames.append(df)
        print(f"  {fname}: {len(df):,} rows")
    df = pd.concat(frames, ignore_index=True)
    return df.rename(
        columns={
            "cert_id": "person_nbr",
            "officer_name": "full_name",
            "officers_rank": "rank",
            "stop_or_leave_date": "end_date",
            "status": "employment_status",
        }
    )


def load_old(input_dir):
    df = pd.read_csv(os.path.join(input_dir, OLD_INDEX), dtype=str)
    df = df.rename(columns={"status": "employment_status"})
    df["source_file"] = OLD_INDEX
    print(f"  {OLD_INDEX}: {len(df):,} rows")
    return df


def safe_date(val):
    """Return YYYY-MM-DD or '' for missing / sentinel / unparseable dates."""
    s = str(val).strip()
    if not s or s in ("nan", "NaT", "None", OPEN_END_DATE):
        return ""
    ts = pd.to_datetime(s, errors="coerce")
    return "" if pd.isna(ts) else ts.strftime("%Y-%m-%d")


def split_name(full_name):
    """Parse 'First [Middle...] Last [Suffix]' into its parts.

    Uses nameparser (handles particles like 'De La Torre'); falls back to a
    positional split when nameparser cannot find both a first and last name
    (e.g. 'JR McCreery'). A leading particle is kept with the first name
    ('De Anna Jo Balencia' -> first 'De Anna', middle 'Jo').
    """
    hn = HumanName(full_name)
    if hn.first and hn.last:
        first, middle, last, suffix = hn.first, hn.middle, hn.last, hn.suffix
    else:
        tokens = full_name.split()
        suffix = ""
        if len(tokens) >= 3 and tokens[-1].rstrip(".").lower() in SUFFIXES:
            suffix = tokens.pop()
        if len(tokens) == 1:
            return tokens[0], "", "", suffix
        first, middle, last = tokens[0], " ".join(tokens[1:-1]), tokens[-1]
    if first.lower() in FIRST_NAME_PARTICLES and middle:
        head, _, rest = middle.partition(" ")
        first, middle = f"{first} {head}", rest
    return first, middle, last, suffix


def parse_names(df):
    parts = df["full_name"].apply(split_name)
    df["first_name"] = parts.str[0]
    df["middle_name"] = parts.str[1]
    df["last_name"] = parts.str[2]
    df["suffix"] = parts.str[3]
    return df


def clean_agency_name(name):
    s = re.sub(r"\s+", " ", str(name)).strip()
    if s.lower() in AGENCY_RENAMES:
        return AGENCY_RENAMES[s.lower()]
    for pattern, repl in AGENCY_ABBREVIATIONS:
        s = re.sub(pattern, repl, s, flags=re.IGNORECASE)
    if s.lower() in AGENCY_RENAMES:
        return AGENCY_RENAMES[s.lower()]
    return s


def clean_rank(rank):
    s = re.sub(r"\s+", " ", str(rank)).strip()
    if s.upper() in RANK_CODES:
        return RANK_CODES[s.upper()]
    # Remaining codes (all-caps or all-lower, no spelled-out word) are
    # normalized to upper case but not expanded.
    if s and (s.isupper() or s.islower()):
        return s.upper()
    return s


def normalize(df):
    df["person_nbr"] = df["person_nbr"].astype(str).str.strip().str.lower()
    df["full_name"] = (
        df["full_name"]
        .fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    df["agency_name"] = df["agency_name"].fillna("").apply(clean_agency_name)
    df["rank"] = df["rank"].fillna("").apply(clean_rank)
    df["employment_status"] = (
        df["employment_status"].astype(str).str.strip().map(STATUS_MAP)
    ).fillna("")
    df["start_date"] = df["start_date"].apply(safe_date)
    df["end_date"] = df["end_date"].apply(safe_date)
    df["state"] = "ks"
    return parse_names(df)


def drop_test_records(df, review_dir):
    mask = df["agency_name"].str.match(TEST_AGENCY_RE) | df[
        "full_name"
    ].str.match(TEST_NAME_RE)
    df[mask].to_csv(os.path.join(review_dir, "test_rows.csv"), index=False)
    print(f"Test/placeholder rows (dropped): {mask.sum():,}")
    return df[~mask]


def resolve_duplicates(df, review_dir):
    """One row per (person, agency, start_date).

    The old index concatenated overlapping exports, so many stints appear
    twice: once still open and once with the end date that was later
    reported. The row with the latest end date wins (closed beats open);
    the kept row also supplies rank/status.
    """
    key = ["person_nbr", "agency_name", "start_date"]
    dup_all = df.duplicated(subset=key, keep=False)
    df[dup_all].sort_values(key).to_csv(
        os.path.join(review_dir, "duplicate_rows.csv"), index=False
    )
    # Sort so the preferred row is last, then keep="last".
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


def collapse_contiguous_stints(df, review_dir, by_cols=None):
    """Merge back-to-back rows at the same agency into one stint.

    Adapted from ``db/preprocess/src/src.py::collapse_contiguous_stints``.
    Rows are contiguous when the next start is no more than one day after
    the latest end seen so far in the group. The merged stint takes the
    earliest start, the latest end, and every other field (rank, status,
    name) from the most recent member.

    Unlike the preprocess version, an *open* end date on a row that is
    followed by another row at the same agency is treated as stale — POST
    never closed it — and is taken to end when the next row starts. The
    merged stint is open only if its most recent row is open.
    """
    by_cols = by_cols or ["person_nbr", "agency_name"]
    one_day = pd.Timedelta(days=1)
    far = pd.Timestamp("2262-01-01")  # stand-in for "still employed"

    w = df.copy()
    w["_start"] = pd.to_datetime(w["start_date"])
    w["_end"] = pd.to_datetime(w["end_date"].replace("", None))
    w = w.sort_values(by_cols + ["_start", "_end"]).reset_index(drop=True)
    grouped = w.groupby(by_cols, sort=False)
    next_start = grouped["_start"].shift(-1)
    w["_eff_end"] = w["_end"].fillna(next_start).fillna(far)
    prev_end = grouped["_eff_end"].transform(lambda s: s.cummax().shift(1))
    w["_new_stint"] = ((w["_start"] - prev_end) > one_day) | prev_end.isna()
    w["_stint_id"] = grouped["_new_stint"].cumsum()

    stint_key = by_cols + ["_stint_id"]
    sizes = w.groupby(stint_key)["_start"].transform("size")
    w[sizes > 1].drop(columns=["_new_stint", "_end"]).to_csv(
        os.path.join(review_dir, "collapsed_stints.csv"), index=False
    )

    agg = {c: "last" for c in df.columns if c not in by_cols}
    agg["_start"] = "min"
    agg["_eff_end"] = "max"
    out = w.groupby(stint_key, sort=False).agg(agg).reset_index()
    out["start_date"] = out["_start"].dt.strftime("%Y-%m-%d")
    out["end_date"] = out["_eff_end"].dt.strftime("%Y-%m-%d")
    out.loc[out["_eff_end"] == far, "end_date"] = ""
    print(
        f"Collapsed contiguous stints: {len(df):,} → {len(out):,} rows "
        f"({len(df) - len(out):,} merged)"
    )
    return out[df.columns]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--output-dir", default="data/output")
    args = parser.parse_args()
    review_dir = os.path.join(args.output_dir, "review")
    os.makedirs(review_dir, exist_ok=True)

    print("Loading:")
    old = normalize(load_old(args.input_dir))
    new = normalize(load_new(args.input_dir))

    # Drop old rows that the Nov-Dec 2024 file re-reports.
    superseded = old["start_date"] >= SUPERSEDE_FROM
    old[superseded].to_csv(
        os.path.join(review_dir, "superseded_rows.csv"), index=False
    )
    print(
        f"\nSuperseded {superseded.sum():,} old-index rows with "
        f"start_date >= {SUPERSEDE_FROM}"
    )
    df = pd.concat([old[~superseded], new], ignore_index=True)

    no_start = df["start_date"] == ""
    print(f"Rows with empty start_date (dropped): {no_start.sum():,}")
    df = df[~no_start]

    df = drop_test_records(df, review_dir)
    df = resolve_duplicates(df, review_dir)
    df = collapse_contiguous_stints(df, review_dir)

    # Sanity checks — reported, not silently fixed.
    bad_order = (df["end_date"] != "") & (df["end_date"] < df["start_date"])
    if bad_order.any():
        print(f"Rows with end_date < start_date (kept): {bad_order.sum():,}")
        df[bad_order].to_csv(
            os.path.join(review_dir, "end_before_start.csv"), index=False
        )
    for col in ["person_nbr", "first_name", "last_name", "agency_name"]:
        n = (df[col] == "").sum()
        if n:
            print(f"Warning: {col} has {n:,} empty values")

    df = df[OUTPUT_COLUMNS].sort_values(["person_nbr", "start_date"])
    out = os.path.join(args.output_dir, "ks_index.csv")
    df.to_csv(out, index=False)
    print(
        f"\nWrote {len(df):,} rows, {df.person_nbr.nunique():,} officers, "
        f"{df.agency_name.nunique():,} agencies → {out}"
    )


if __name__ == "__main__":
    main()
