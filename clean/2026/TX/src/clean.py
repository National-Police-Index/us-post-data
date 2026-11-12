"""Clean the Texas (TCOLE) POST employment table into the index schema.

Input (``data/input/``): ``post_data_texas.csv`` — one row per officer per
appointment (``SERVICE``) per agency. Output (``data/output/``):
``tx_index.csv`` plus audit files in ``review/``.

Usage (from clean/2026/TX/):
    python src/clean.py --input-dir data/input --output-dir data/output
"""

import argparse
import os
import re

import pandas as pd


INPUT_FILE = "post_data_texas.csv"
OUTPUT_FILE = "tx_index.csv"

COLUMN_MAP = {
    "PUBLIC ID": "person_nbr",
    "FULL NAME": "full_name",
    "DOB": "dob",
    "DEPARTMENT NAME": "agency_name",
    "SERVICE": "rank",
    "START DATE": "start_date",
    "END DATE": "end_date",
}

# Dates are M/D/YY. The export's latest date is 2025-12-31 and it has no
# year "26", so two-digit years up to this value are 20xx, the rest 19xx.
LAST_YY = 25
# Youngest plausible age at first appointment, used to pick a birth
# century (see resolve_year_of_birth).
MIN_AGE_AT_HIRE = 14

OUTPUT_COLUMNS = [
    "person_nbr",
    "full_name",
    "first_name",
    "middle_name",
    "last_name",
    "suffix",
    "agency_name",
    "rank",
    "start_date",
    "end_date",
    "year_of_birth",
    "state",
]

_ACRONYMS = [
    (r"\bc\.\s*i\.\s*s\.\s*d\.", "consolidated independent school district"),
    (r"\bi\.\s*s\.\s*d\.", "independent school district"),
    (r"\bd\.\s*p\.\s*s\.", "department of public safety"),
    (r"\bp\.\s*d\.", "police department"),
    (r"\bd\.\s*a\.", "district attorney"),
    (r"\bs\.\s*d\.", "school district"),
    (r"\bu\.\s*s\.", "us"),
]

_ABBREVS = [
    (r"\bco\.", "county"),
    (r"\bdist\.", "district"),
    (r"\bdept\.", "department"),
    (r"\bdeten\.", "detention"),
    (r"\bconst\.", "constable"),
    (r"\bpct\.", "precinct"),
    (r"\buniv\.", "university"),
    (r"\bmunic\.", "municipal"),
    (r"\bmun\.", "municipal"),
    (r"\butil\.", "utility"),
    (r"\breg\.", "regional"),
    (r"\bintl\.", "international"),
    (r"\bcrim\.", "criminal"),
    (r"\bauth\.", "authority"),
    (r"\binvest\.", "investigation"),
    (r"\bivest\.", "investigation"),
    (r"\binv\.", "investigation"),
    (r"\bprev\.", "prevention"),
    (r"\bvolun\.", "volunteer"),
    (r"\bhosp\.", "hospital"),
    (r"\bsupp\.", "supply"),
    (r"\bcont\.", "control"),
    (r"\batty\.'s", "attorney's"),
    (r"\batty\.", "attorney"),
    (r"\batt\.", "attorney"),
    (r"\bdiv\.", "division"),
    (r"\btech\.", "technical"),
    (r"\btex\.", "texas"),
    (r"\bjr\.", "junior"),
    (r"\boff\.", "office"),
    (r"\bst\.", "saint"),
    (r"\bcomm\. college", "community college"),
]

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix"}

_PARTICLES = {
    "de", "del", "dela", "della", "dello", "delos", "dellos", "la", "las",
    "los", "le", "van", "von", "der", "den", "di", "da", "du", "dos", "das",
    "des", "san", "santa", "saint", "st", "ste", "y",
}  # fmt: skip


# --------------------------------------------------------------------------
# Load
# --------------------------------------------------------------------------


def load(input_dir):
    df = pd.read_csv(
        os.path.join(input_dir, INPUT_FILE),
        dtype=str,
        keep_default_na=False,
    )
    # "Unnamed: 7" is a fully empty column left over from the source once
    # being an .xlsx.
    df = df.rename(columns=COLUMN_MAP)[list(COLUMN_MAP.values())]
    df = df.apply(lambda col: col.str.strip().replace("NULL", ""))
    print(f"Loaded {len(df):,} rows from {INPUT_FILE}")
    return df


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------


def parse_mdy(series):
    """Parse M/D/YY strings, resolving the century with LAST_YY.

    pandas' own two-digit-year pivot (69) would put e.g. a 1968 hire in
    2068, so the century is set explicitly.
    """
    parts = series.str.extract(r"^(\d{1,2})/(\d{1,2})/(\d{2})$").apply(
        pd.to_numeric
    )
    yy = parts[2]
    year = yy.where(yy > LAST_YY, yy + 2000).where(yy <= LAST_YY, yy + 1900)
    return pd.to_datetime(
        {"year": year, "month": parts[0], "day": parts[1]}, errors="coerce"
    )


def resolve_year_of_birth(df):
    """Turn the M/D/YY DOB into a four-digit year_of_birth.

    A two-digit birth year is ambiguous (``/05`` could be 1905 or 2005), so
    it is resolved per person: 20xx unless that would make them younger
    than MIN_AGE_AT_HIRE at their first appointment, in which case 19xx.
    DOBs not in M/D/YY form (one row, ``1774-06-16``) are left empty.
    """
    yy = pd.to_numeric(df["dob"].str.extract(r"/(\d{2})$")[0])
    first_hire = df.groupby("person_nbr")["_start"].transform("min").dt.year
    year = (yy + 2000).where(yy + 2000 <= first_hire - MIN_AGE_AT_HIRE)
    year = year.fillna(yy + 1900)
    df["year_of_birth"] = year.astype("Int64").astype(str).replace("<NA>", "")
    return df


# --------------------------------------------------------------------------
# Agency names
# --------------------------------------------------------------------------


def clean_agency_name(df):
    s = df["agency_name"].str.lower().str.strip()

    for pat, repl in _ACRONYMS:
        s = s.str.replace(pat, repl, regex=True)
    for pat, repl in _ABBREVS:
        s = s.str.replace(pat, repl, regex=True)

    # spelling fix in source data
    s = s.str.replace(r"\bwest virgina\b", "west virginia", regex=True)

    # strip trailing dept-id codes, e.g. "reno police department (367204) -
    # 367204"
    s = s.str.replace(r"\s*\(\d+\)\s*(-\s*\d+)?\s*$", "", regex=True)
    s = s.str.replace(r"\s*-\s*\d+\s*$", "", regex=True)
    # drop trailing "(inactive)" marker and trailing comma/period/whitespace
    s = s.str.replace(r"\s*\(inactive\)\s*$", "", regex=True)
    s = s.str.replace(r"[,.\s]+$", "", regex=True)
    # normalize "# 1" spacing and collapse repeated whitespace
    s = s.str.replace(r"#\s*(\d+)", r"#\1", regex=True)
    s = s.str.replace(r"\s{2,}", " ", regex=True)

    df["agency_name"] = s
    return df


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------


def _is_initial(tok):
    return re.fullmatch(r"[A-Za-z]\.?", tok) is not None


def _key(tok):
    return tok.replace(".", "").lower()


def _split_one(raw):
    """Split 'First [Middle] Last [Suffix]'; see README for the rules."""
    name = re.sub(r"\s+", " ", str(raw)).strip()
    # a hyphen spaced on BOTH sides ("Jeannine - Langley") is a separator;
    # a hyphen attached on either side ("Choice -Farkasdi") is a real
    # hyphenated name.
    name = re.sub(r"\s+-\s+", " ", name)
    name = re.sub(r"\s*-\s*", "-", name)
    name = name.replace(",", " ")
    name = re.sub(r"\s+", " ", name).strip()
    toks = name.split(" ") if name else []

    # collapse consecutive identical single initials, e.g. "D D" -> "D"
    collapsed = []
    for t in toks:
        if (
            collapsed
            and _is_initial(t)
            and _is_initial(collapsed[-1])
            and _key(t) == _key(collapsed[-1])
        ):
            continue
        collapsed.append(t)
    toks = collapsed

    # pull generational suffix(es) off the end (keep >=2 tokens)
    suffix = ""
    while len(toks) >= 3 and _key(toks[-1]) in _SUFFIXES:
        tok = toks[-1].rstrip(".")
        suffix = tok if not suffix else tok + " " + suffix
        toks = toks[:-1]

    first = middle = last = ""
    n = len(toks)
    if n == 1:
        first = toks[0]
    elif n == 2:
        first, last = toks
    elif n >= 3:
        # pivot on the first single initial in positions 1..n-2
        pivot = next((i for i in range(1, n - 1) if _is_initial(toks[i])), None)
        if pivot is not None:
            first = " ".join(toks[:pivot])
            middle = toks[pivot]
            last = " ".join(toks[pivot + 1 :])
        else:
            # no middle initial: last = trailing surname + leading
            # particles. One leftover word is the middle name; any further
            # words are extra surname components.
            j = n - 1
            while j - 1 >= 1 and _key(toks[j - 1]) in _PARTICLES:
                j -= 1
            rest = toks[:j]
            first = rest[0]
            middle = rest[1] if len(rest) >= 2 else ""
            last = " ".join(rest[2:] + toks[j:])

    return first, middle, last, suffix


def split_full_name(df):
    df["full_name"] = df["full_name"].str.replace(r"\s+", " ", regex=True)
    # parse each distinct name once, then map back
    lookup = {n: _split_one(n) for n in df["full_name"].unique()}
    for i, col in enumerate(
        ["first_name", "middle_name", "last_name", "suffix"]
    ):
        df[col] = df["full_name"].map(lambda n, i=i: lookup[n][i])
    return df


# --------------------------------------------------------------------------
# Stints
# --------------------------------------------------------------------------


def collapse_stints(df, review_dir):
    """Merge overlapping or back-to-back rows at the same agency.

    Texas keeps one row per appointment type (SERVICE), so one job is often
    several rows: concurrent (Jailer + Peace Officer, same dates), nested
    (an open Jailer row spanning several Peace Officer rows) or adjacent.
    Rows join the current stint when they start no more than a day after
    the latest end seen so far in the (person, agency) group — a running
    max, so a long open row absorbs everything inside it.

    An open end date is taken at face value (still employed). Unlike the
    KS/IL versions it is NOT treated as stale when a later row follows:
    in Texas the later row is usually a concurrent appointment or a
    zero-length artifact, and the open appointment is genuinely open.

    The merged stint takes the earliest start, the latest end (open if any
    member is open) and every other field from its latest-starting row.
    """
    key = ["person_nbr", "agency_name"]
    one_day = pd.Timedelta(days=1)
    open_end = pd.Timestamp("2262-01-01")  # stand-in for "still employed"

    w = df.copy()
    w["_end"] = w["_end"].fillna(open_end)
    w = w.sort_values(key + ["_start", "_end"]).reset_index(drop=True)
    grouped = w.groupby(key, sort=False)
    prev_end = grouped["_end"].transform(lambda s: s.cummax().shift(1))
    w["_new"] = prev_end.isna() | ((w["_start"] - prev_end) > one_day)
    w["_stint"] = w["_new"].cumsum()

    sizes = w.groupby("_stint")["_start"].transform("size")
    w[sizes > 1].drop(columns=["_new", "_end", "_start"]).to_csv(
        os.path.join(review_dir, "collapsed_stints.csv"), index=False
    )

    agg = {c: "last" for c in w.columns if c not in ("_stint", "_new")}
    agg["_start"] = "min"
    agg["_end"] = "max"
    out = w.groupby("_stint", sort=False).agg(agg).reset_index(drop=True)
    out["start_date"] = out["_start"].dt.strftime("%Y-%m-%d")
    out["end_date"] = out["_end"].dt.strftime("%Y-%m-%d")
    out.loc[out["_end"] == open_end, "end_date"] = ""
    print(
        f"Collapsed stints: {len(df):,} → {len(out):,} rows "
        f"({len(df) - len(out):,} merged; "
        f"{(sizes > 1).sum():,} rows in multi-row stints → review)"
    )
    return out


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def drop_to_review(df, mask, review_dir, fname, label):
    df[mask].to_csv(os.path.join(review_dir, fname), index=False)
    print(f"{label} (dropped): {mask.sum():,} → review/{fname}")
    return df[~mask]


def validate(df):
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
    assert not df.duplicated(
        ["person_nbr", "agency_name", "start_date"]
    ).any(), "duplicate (person_nbr, agency_name, start_date)"
    for col in required[:-1]:
        n = (df[col] == "").sum()
        if n:
            print(f"Warning: {col} has {n:,} empty ({n / len(df):.1%})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--output-dir", default="data/output")
    args = parser.parse_args()
    review_dir = os.path.join(args.output_dir, "review")
    os.makedirs(review_dir, exist_ok=True)

    df = load(args.input_dir)
    df["person_nbr"] = df["person_nbr"].str.lower()
    df["_start"] = parse_mdy(df["start_date"])
    df["_end"] = parse_mdy(df["end_date"])

    # The same rows lack agency, service, start and end: no employment.
    df = drop_to_review(
        df, df["_start"].isna(), review_dir, "no_start_date.csv",
        "No start date",
    )  # fmt: skip
    df = drop_to_review(
        df, df["_end"] < df["_start"], review_dir, "end_before_start.csv",
        "end_date before start_date",
    )  # fmt: skip

    df = resolve_year_of_birth(df)
    df = clean_agency_name(df)
    df = split_full_name(df)
    df["state"] = "tx"

    df = collapse_stints(df, review_dir)
    df = df[OUTPUT_COLUMNS].sort_values(["person_nbr", "start_date"])
    validate(df)

    out = os.path.join(args.output_dir, OUTPUT_FILE)
    df.to_csv(out, index=False)
    print(
        f"\nWrote {len(df):,} rows, {df.person_nbr.nunique():,} officers, "
        f"{df.agency_name.nunique():,} agencies → {out}"
    )


if __name__ == "__main__":
    main()
