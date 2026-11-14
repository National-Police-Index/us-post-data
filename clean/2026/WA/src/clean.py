"""Clean the Washington (WSCJTC) 2026 release into the index schema.

Usage (from clean/2026/WA/):
    python src/clean.py --input-dir data/input --output-dir data/output
"""

import argparse
import os
import re

import pandas as pd


# helpers


def read_tbl(input_dir):
    """Read the ALL sheet: one row per officer, employment stints side by
    side."""
    return pd.read_excel(
        os.path.join(input_dir, "PRR_7.29.26.xlsx"),
        sheet_name="ALL",
        dtype=str,
    )


def snake_case(name):
    name = re.sub(r"\(current\)", "", name.lower())
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def write_review(df, review_dir, fname, label, dropped=True):
    df.to_csv(os.path.join(review_dir, fname), index=False)
    verb = "dropped" if dropped else "kept"
    print(f"  {label} ({verb}): {len(df):,} → review/{fname}")


# employment history data


def employment_groups(columns):
    """Map each stint's columns to their base name, one dict per stint.

    A stint starts at each "Employment Start Date" column; the export drops
    columns empty for every officer, so later stints have fewer fields.
    """
    groups = []
    for col in columns:
        base = re.sub(r"\.\d+$", "", col)
        if base == "Employment Start Date":
            groups.append({})
        # agency addresses and certification columns are not stint fields
        if groups and base.startswith(("Employment ", "Employing ")):
            groups[-1].setdefault(base, col)
    return groups


def melt_stints(df):
    """Reshape to one row per officer per stint, dropping empty stints."""
    person_cols = [c for c in df.columns if c.startswith("Person ")]
    groups = employment_groups(df.columns)
    fields = list(dict.fromkeys(base for g in groups for base in g))

    frames = []
    for i, group in enumerate(groups, start=1):
        stint = df[person_cols].copy()
        for base in fields:
            stint.loc[:, base] = df[group[base]] if base in group else None
        stint.loc[:, "stint_nbr"] = i
        frames.append(stint)
    out = pd.concat(frames, ignore_index=True)

    out = out.dropna(subset=fields, how="all")
    out.columns = [snake_case(c) for c in out.columns]
    return out.sort_values(["person_student_id", "stint_nbr"]).reset_index(
        drop=True
    )


def rename_cols(df):
    df = df.rename(
        columns={
            "person_student_id": "person_nbr",
            "person_first_name": "first_name",
            "person_middle_name": "middle_name",
            "person_last_name": "last_name",
            "person_suffix": "suffix",
            "person_gender": "sex",
            "employment_start_date": "start_date",
            "employment_end_date": "end_date",
            "employment_appointment_type": "certification_type",
            "employment_title_rank": "rank",
            "employment_status": "status",
            "employment_change_reason": "separation_reason",
            "employing_organization_name": "agency_name",
        }
    )
    return df.drop(
        columns=[
            "employing_organization_ori_or_wa_ubi",
            "stint_nbr",
            "employing_organization_is_employer",
            "employment_employment_assignment",
        ]
    )


def strip_text(df):
    """Fill blanks with "" and collapse whitespace in every column."""
    return df.fillna("").apply(
        lambda col: col.str.replace(r"\s+", " ", regex=True).str.strip()
    )


def clean_person_nbr(df):
    df.loc[:, "person_nbr"] = df.person_nbr.str.lower()
    return df


def clean_dates(df):
    """Excel datetimes to YYYY-MM-DD. 1901-01-01 (once 1900-01-01) is
    WSCJTC's placeholder for an unknown date and is blanked."""
    for col in ["start_date", "end_date"]:
        date = df[col].str[:10]
        df.loc[:, col] = date.where(~date.str.match(r"190[01]-01-01"), "")
    return df


def clean_suffix(df):
    """Keep generational suffixes only (credentials like "M.D." are not
    suffixes), and pull the few typed into last_name."""
    trailing = r"\s+(Jr|Sr|II|III|IV)\.?$"
    found = df.last_name.str.extract(trailing, flags=re.IGNORECASE)[0]
    has = found.notna() & (df.suffix == "")
    df.loc[has, "suffix"] = found[has]
    df.loc[found.notna(), "last_name"] = df.last_name.str.replace(
        trailing, "", regex=True, flags=re.IGNORECASE
    )

    suffix = df.suffix.str.rstrip(".")
    generational = suffix.str.fullmatch(r"(?i)jr|sr|i|ii|iii|iv|v|x")
    df.loc[:, "suffix"] = suffix.where(generational, "")
    return df


def build_full_name(df):
    df.loc[:, "full_name"] = (
        (
            df.last_name
            + ", "
            + df.first_name
            + " "
            + df.middle_name
            + " "
            + df.suffix
        )
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.lower()
    )
    return df


def clean_rank(df):
    """ "Unknown" is a placeholder, not a rank."""
    df.loc[:, "rank"] = df["rank"].where(df["rank"] != "Unknown", "")
    return df


def clean_agency_names(df):
    """Expand acronyms, resolve redirects and variants, and tidy spacing.

    Names are otherwise already clean; db/preprocess lowercases them.
    """
    rules = [
        # one agency recorded under another's name
        (r"^.*\(Use ([^)]+)\)$", r"\1"),
        (r"^A1 Security Services", "A-1 Security Services"),
        # acronyms
        (r"^WSCJTC PS\b", "WSCJTC Private Security"),
        (
            r"^WSCJTC\b",
            "Washington State Criminal Justice Training Commission",
        ),
        (r"^WSP IIT$", "WSP Independent Investigation Team"),
        (r"\s*\(WSP\)$", ""),
        (r"^WSP\b", "Washington State Patrol"),
        (r"^JRA\b", "Juvenile Rehabilitation Administration"),
        (r"^UW\b", "University of Washington"),
        (r"\bHIDTA\b", "High Intensity Drug Trafficking Area"),
        (r"^NW\b", "Northwest"),
        (r"\bWA\b", "Washington"),
        # noise and spacing
        (r"\s*\(s\)$", ""),
        # "2- Yakima", "Center -Northwest"; leaves "Sedro-Woolley" alone
        (r"(?<=\S)- (?=\S)|(?<=\S) -(?=\S)", " - "),
        (r"\s+", " "),
    ]
    s = df.agency_name
    for pattern, repl in rules:
        s = s.str.replace(pattern, repl, regex=True)
    df.loc[:, "agency_name"] = s.str.strip(" ,")
    return df


def drop_non_agency(df, review_dir):
    """Drop rows whose agency is a placeholder rather than an agency."""
    bad = df.agency_name.str.lower().isin(["", "other", "unknown", "n/a"])
    write_review(df[bad], review_dir, "non_agency.csv", "Non-agency value")
    return df[~bad]


def drop_no_start(df, review_dir):
    no_start = df.start_date == ""
    write_review(
        df[no_start],
        review_dir,
        "no_start_date.csv",
        "Start date missing or 1901 placeholder",
    )
    return df[~no_start]


def resolve_duplicates(df, review_dir):
    """One row per (person, agency, start date); a closed row beats an
    open one, and otherwise the latest end wins."""
    key = ["person_nbr", "agency_name", "start_date"]
    dup = df.duplicated(key, keep=False)
    ordered = df.assign(_open=df.end_date == "").sort_values(
        key + ["_open", "end_date"], ascending=[True, True, True, False, True]
    )
    kept = ordered.drop_duplicates(key, keep="last").drop(columns="_open")
    write_review(
        df[dup].sort_values(key),
        review_dir,
        "duplicate_rows.csv",
        "Rows sharing person, agency and start date (one kept)",
        dropped=False,
    )
    return kept


def collapse_stints(df, review_dir):
    """Merge overlapping or back-to-back rows at the same agency into one
    stint. Open end dates are kept open, never treated as stale."""
    key = ["person_nbr", "agency_name"]
    open_end = pd.Timestamp("2262-01-01")

    w = df.copy()
    w.loc[:, "_start"] = pd.to_datetime(w.start_date)
    w.loc[:, "_end"] = pd.to_datetime(w.end_date.replace("", None)).fillna(
        open_end
    )
    w = w.sort_values(key + ["_start", "_end"]).reset_index(drop=True)
    prev_end = w.groupby(key, sort=False)._end.transform(
        lambda s: s.cummax().shift(1)
    )
    w.loc[:, "_stint"] = (
        prev_end.isna() | ((w._start - prev_end) > pd.Timedelta(days=1))
    ).cumsum()

    sizes = w.groupby("_stint")._start.transform("size")
    write_review(
        w[sizes > 1].drop(columns=["_start", "_end"]),
        review_dir,
        "collapsed_stints.csv",
        "Rows merged into multi-row stints",
        dropped=False,
    )

    agg = {c: "last" for c in w.columns if c != "_stint"}
    agg.update({"_start": "min", "_end": "max"})
    out = w.groupby("_stint", sort=False).agg(agg).reset_index(drop=True)
    out.loc[:, "start_date"] = out._start.dt.strftime("%Y-%m-%d")
    out.loc[:, "end_date"] = out._end.dt.strftime("%Y-%m-%d")
    out.loc[out._end == open_end, "end_date"] = ""
    print(f"  Collapsed stints: {len(df):,} → {len(out):,} rows")
    return out.drop(columns=["_start", "_end"])


# main


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
    assert not missing, f"missing required columns {missing}"
    assert (df.start_date != "").all(), "empty start_date"
    key = ["person_nbr", "agency_name", "start_date"]
    assert not df.duplicated(key).any(), f"duplicate {key}"
    for col in required[:-1]:
        n = (df[col] == "").sum()
        if n:
            print(f"  Warning: {col} has {n:,} empty values")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--output-dir", default="data/output")
    args = parser.parse_args()
    review_dir = os.path.join(args.output_dir, "review")
    os.makedirs(review_dir, exist_ok=True)

    df = read_tbl(args.input_dir)
    print(f"ALL sheet: {len(df):,} officers")
    df = melt_stints(df)
    print(f"  Melted to {len(df):,} stints")

    df = (
        df.pipe(rename_cols)
        .pipe(strip_text)
        .pipe(clean_person_nbr)
        .pipe(clean_dates)
        .pipe(clean_suffix)
        .pipe(build_full_name)
        .pipe(clean_rank)
        .pipe(clean_agency_names)
        .pipe(drop_non_agency, review_dir)
        .pipe(drop_no_start, review_dir)
        .pipe(resolve_duplicates, review_dir)
        .pipe(collapse_stints, review_dir)
        .assign(state="wa")
    )

    columns = [
        "person_nbr",
        "full_name",
        "first_name",
        "middle_name",
        "last_name",
        "suffix",
        "sex",
        "agency_name",
        "certification_type",
        "rank",
        "status",
        "start_date",
        "end_date",
        "separation_reason",
        "state",
    ]
    df = df[columns].sort_values(["person_nbr", "start_date"])
    validate(df)

    path = os.path.join(args.output_dir, "wa_index.csv")
    df.to_csv(path, index=False)
    print(
        f"\nWrote {len(df):,} rows, {df.person_nbr.nunique():,} officers, "
        f"{df.agency_name.nunique():,} agencies → {path}"
    )


if __name__ == "__main__":
    main()
