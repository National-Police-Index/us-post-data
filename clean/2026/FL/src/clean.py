"""Clean the Florida (FDLE ATMS) 2026 release into the index schema.

Usage (from clean/2026/FL/):
    python src/clean.py --input-dir data/input --output-dir data/output
"""

import argparse
import os
import re

import pandas as pd


# helpers


def read_tbl(input_dir, name):
    df = pd.read_csv(
        os.path.join(input_dir, f"{name}.csv"),
        dtype=str,
        keep_default_na=False,
    )
    return df.apply(lambda col: col.str.strip())


def read_codes(input_dir):
    df = read_tbl(input_dir, "codes")
    df.columns = df.columns.str.lower()
    return df


def decode(series, codes, category):
    """Map ATMS codes to their codes.csv description. Unknown codes are kept as-is."""
    sub = codes[codes.category == category]
    lookup = dict(
        zip(sub.code_value.str.lower(), sub.code_description, strict=False)
    )
    return series.map(lambda v: lookup.get(v.lower(), v))


def parse_dates(series):
    """Parse "MM/DD/YY HH:MM:SS" strings. Two-digit years 00-25 are 20xx, 26-99 are 19xx."""
    last_yy = 25
    parts = series.str.extract(r"^(\d{1,2})/(\d{1,2})/(\d{2})\b").apply(
        pd.to_numeric
    )
    yy = parts[2]
    year = yy.where(yy > last_yy, yy + 2000).where(yy <= last_yy, yy + 1900)
    return pd.to_datetime(
        {"year": year, "month": parts[0], "day": parts[1]}, errors="coerce"
    )


def to_iso(ts):
    return ts.dt.strftime("%Y-%m-%d").fillna("")


def write_review(df, review_dir, fname, label, dropped=True):
    df.to_csv(os.path.join(review_dir, fname), index=False)
    verb = "dropped" if dropped else "kept"
    print(f"  {label} ({verb}): {len(df):,} → review/{fname}")


# employment history data


def dedupe_people(df, review_dir):
    """Keep the first row for person_nbrs listed more than once."""
    dup = df.person_nbr.duplicated(keep=False)
    write_review(
        df[dup].sort_values("person_nbr"),
        review_dir,
        "person_data_duplicates.csv",
        "person_data rows sharing a person_nbr (first kept)",
        dropped=False,
    )
    return df.drop_duplicates("person_nbr").copy()


def clean_names(df):
    for col in ["first_name", "middle_name", "last_name"]:
        df.loc[:, col] = (
            df[col].str.replace(r"\s+", " ", regex=True).str.strip(" ,")
        )
    return df


def split_suffixes(df):
    """Move suffixes typed into the name fields ("Torres Jr.") to suffix. "V" is left alone; here it is a middle initial."""
    trailing = r"[\s,]+(jr|sr|ii|iii|iv)\.?$"
    alone = r"^(jr|sr|ii|iii|iv)\.?$"

    df.loc[:, "suffix"] = ""
    for col in ["last_name", "first_name"]:
        found = df[col].str.extract(trailing, flags=re.IGNORECASE)[0]
        # never empty the name itself ("Jr" alone stays a name)
        found = found.where(df[col].str.len() > found.str.len() + 1)
        has = found.notna()
        new = has & (df.suffix == "")
        df.loc[new, "suffix"] = found[new].str.lower()
        df.loc[has, col] = (
            df.loc[has, col]
            .str.replace(trailing, "", regex=True, flags=re.IGNORECASE)
            .str.strip(" ,")
        )

    mid = df.middle_name.str.match(alone, flags=re.IGNORECASE)
    df.loc[mid & (df.suffix == ""), "suffix"] = (
        df.loc[mid, "middle_name"].str.rstrip(".").str.lower()
    )
    df.loc[mid, "middle_name"] = ""
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


def clean_race(df, codes):
    """Decode race_code; "NA" is American Indian/Native Alaskan, not missing."""
    race = df.race_code.replace({"WHI": "Wh", "H": "His"})
    df.loc[:, "race"] = decode(race, codes, "race")
    return df


def clean_sex(df, codes):
    """Decode sex_code; Unknown and undefined values are left empty."""
    sex = decode(df.sex_code, codes, "sex")
    df.loc[:, "sex"] = sex.where(sex.isin(["Male", "Female"]), "")
    return df


def clean_birth_year(df):
    df.loc[:, "year_of_birth"] = df.birth_year.where(
        df.birth_year.str.fullmatch(r"(19|20)\d\d"), ""
    )
    return df


def clean_people(df, codes, review_dir):
    df = (
        df.pipe(dedupe_people, review_dir)
        .pipe(clean_names)
        .pipe(split_suffixes)
        .pipe(build_full_name)
        .pipe(clean_race, codes)
        .pipe(clean_sex, codes)
        .pipe(clean_birth_year)
    )
    return df[
        [
            "person_nbr",
            "full_name",
            "first_name",
            "middle_name",
            "last_name",
            "suffix",
            "race",
            "sex",
            "year_of_birth",
        ]
    ]


def clean_agency_names(df):
    """Expand abbreviations and finish names truncated at 60 characters."""
    rules = [
        # truncated at 60 characters
        (r"\bInvestigations Di$", "Investigations Division"),
        (r"\bPolice Departmen$", "Police Department"),
        (r"\bTraining Academ$", "Training Academy"),
        (r"\bLaw Enforcement Aca$", "Law Enforcement Academy"),
        (r"\bMotor Carrier Complian$", "Motor Carrier Compliance"),
        (r"\bCommission Law Enforc$", "Commission Law Enforcement"),
        # agency-specific prefixes
        (r"^Dc\b,?", "Department Of Corrections,"),
        (r"^Dep\b,", "Department Of Environmental Protection,"),
        (r"^Fdle\b", "Florida Department Of Law Enforcement"),
        # general abbreviations
        (r"\bDept\b\.?", "Department"),
        (r"\bSvcs\b", "Services"),
        (r"\bMgt\b", "Management"),
        (r"\bCtr\b", "Center"),
        (r"\bInd\.", "Industry"),
        (r"\bSec Pol Squad\b", "Security Police Squadron"),
        (r"\bAfb\b", "Air Force Base"),
        (r"\bFl\b", "Florida"),
        (r"\bU\.? ?S\.?(?= )", "US"),
        (r"\s*/\s*", " / "),
        (r"\s+", " "),
    ]
    s = df.agcy_name
    for pattern, repl in rules:
        s = s.str.replace(pattern, repl, regex=True)
    df = df.copy()
    df.loc[:, "agency_name"] = s.str.strip(" ,")
    return df[["agcy_nbr", "agency_name"]]


def current_certificate_status(df, codes):
    """Per officer, the status of their latest certificate of each type."""
    df = df.copy()
    df.loc[:, "_date"] = parse_dates(df.certificate_date)
    df.loc[:, "_type"] = decode(df.certificate_type, codes, "certificate_type")
    df.loc[:, "_status"] = decode(
        df.certificate_status, codes, "certificate_status"
    )
    latest = df.sort_values("_date").drop_duplicates(
        ["person_nbr", "_type"], keep="last"
    )
    latest = latest.sort_values(["person_nbr", "_type"])
    latest.loc[:, "_pair"] = latest._type + ": " + latest._status
    out = latest.groupby("person_nbr")._pair.agg("; ".join).reset_index()
    return out.rename(columns={"_pair": "current_certificate_status"})


def clean_employment_dates(df):
    df.loc[:, "_start"] = parse_dates(df.employ_start_date)
    df.loc[:, "_end"] = parse_dates(df.separation_date)
    return df


def decode_employment_codes(df, codes):
    df.loc[:, "type"] = decode(df.employ_class, codes, "employ_class")
    df.loc[:, "employment_status"] = decode(
        df.employ_type, codes, "employ_type"
    )
    df.loc[:, "separation_reason"] = decode(
        df.separation_code, codes, "separation_code"
    )
    # a separation reason only makes sense on a closed row
    df.loc[df._end.isna(), "separation_reason"] = ""
    return df


def clean_notes(df):
    """employ_comments → notes, with emails and phone numbers redacted."""
    df.loc[:, "notes"] = (
        df.employ_comments.str.replace(r"\s+", " ", regex=True)
        .str.replace(r"\S+@\S+", "[email]", regex=True)
        .str.replace(
            r"\(?\b\d{3}\)?[-.\s]?\d{3}[-.]\d{4}\b", "[phone]", regex=True
        )
        .str.strip()
    )
    return df


def drop_test_agency(df, review_dir):
    test = df.agency_name == (
        "Florida Department Of Law Enforcement Fake Training Center"
    )
    write_review(df[test], review_dir, "test_agency.csv", "Test agency")
    return df[~test]


def drop_bad_dates(df, review_dir):
    bad = df._start.isna() | (df._end < df._start)
    write_review(
        df[bad],
        review_dir,
        "end_before_start.csv",
        "Missing start or end before start",
    )
    return df[~bad]


def drop_exact_duplicates(df, review_dir):
    dup = df.duplicated(["person_nbr", "agency_name", "_start", "_end"])
    write_review(
        df[dup], review_dir, "exact_duplicates.csv", "Exact duplicates"
    )
    return df[~dup]


def drop_no_name(df, review_dir):
    no_name = (df.first_name.fillna("") == "") | (df.last_name.fillna("") == "")
    write_review(df[no_name], review_dir, "no_name.csv", "No first/last name")
    return df[~no_name]


def collapse_stints(df, review_dir):
    """Merge overlapping or back-to-back rows at the same agency into one stint. Open end dates are kept open, never treated as stale."""
    key = ["person_nbr", "agency_name"]
    open_end = pd.Timestamp("2262-01-01")

    w = df.copy()
    w.loc[:, "_end"] = w._end.fillna(open_end)
    w = w.sort_values(key + ["_start", "_end"]).reset_index(drop=True)
    prev_end = w.groupby(key, sort=False)._end.transform(
        lambda s: s.cummax().shift(1)
    )
    w.loc[:, "_stint"] = (
        prev_end.isna() | ((w._start - prev_end) > pd.Timedelta(days=1))
    ).cumsum()

    sizes = w.groupby("_stint")._start.transform("size")
    write_review(
        w[sizes > 1].drop(columns=["_end", "_start"]),
        review_dir,
        "collapsed_stints.csv",
        "Rows merged into multi-row stints",
        dropped=False,
    )

    reason = w.loc[w.groupby("_stint")._end.idxmax()].set_index("_stint")
    agg = {c: "last" for c in w.columns if c != "_stint"}
    agg.update(
        {
            "_start": "min",
            "_end": "max",
            "notes": lambda s: " | ".join(dict.fromkeys(s[s != ""])),
        }
    )
    out = w.groupby("_stint", sort=False).agg(agg)
    out.loc[:, "separation_reason"] = reason.separation_reason
    out = out.reset_index(drop=True)

    out.loc[:, "start_date"] = to_iso(out._start)
    out.loc[:, "end_date"] = to_iso(out._end)
    is_open = out._end == open_end
    out.loc[is_open, ["end_date", "separation_reason"]] = ""
    out.loc[is_open, "_end"] = pd.NaT
    print(f"  Collapsed stints: {len(df):,} → {len(out):,} rows")
    return out


def build_employment(tbls, people, agencies, certs, codes, review_dir):
    df = tbls["employment"]
    print(f"employment.csv: {len(df):,} rows")
    return (
        df.merge(agencies, on="agcy_nbr", how="left")
        .pipe(clean_employment_dates)
        .pipe(decode_employment_codes, codes)
        .pipe(clean_notes)
        .pipe(drop_test_agency, review_dir)
        .pipe(drop_bad_dates, review_dir)
        .pipe(drop_exact_duplicates, review_dir)
        .merge(people, on="person_nbr", how="left")
        .pipe(drop_no_name, review_dir)
        .pipe(collapse_stints, review_dir)
        .merge(certs, on="person_nbr", how="left")
        .fillna({"current_certificate_status": ""})
        .assign(state="fl")
    )


# complaint data


def clean_offenses(df, codes):
    """One row per offense: the decoded violation, prefixed by its plea or finding."""
    df = df.copy()
    # some descriptions end in a dangling hyphen ("Dangerous Drugs-")
    offense = decode(df.offense_code, codes, "offense_code").str.rstrip(" -")
    prefix = decode(df.offense_prefix, codes, "OFFENSE_PREFIX")
    df.loc[:, "violation"] = (prefix + " " + offense).str.strip()
    df.loc[:, "violation_comments"] = df.offense_comments.str.replace(
        r"\s+", " ", regex=True
    )
    # offense_date is "M-DD-YYYY", unlike every other ATMS date
    df.loc[:, "violation_date"] = to_iso(
        pd.to_datetime(df.offense_date, format="%m-%d-%Y", errors="coerce")
    )
    return df[
        [
            "complaint_nbr",
            "violation",
            "violation_date",
            "violation_comments",
        ]
    ]


def clean_sanctions(df, codes):
    df = df.copy()
    df.loc[:, "sanction"] = decode(
        df.discipline_imposed, codes, "discipline_imposed"
    )
    df.loc[:, "_sanction_date"] = parse_dates(df.final_order_date)
    df.loc[:, "sanction_date"] = to_iso(df._sanction_date)
    df.loc[:, "sanction_comments"] = df.discipline_comments.str.replace(
        r"\s+", " ", regex=True
    )
    return df[
        [
            "complaint_nbr",
            "sanction",
            "sanction_date",
            "_sanction_date",
            "sanction_comments",
        ]
    ]


def clean_complaints(df, agencies):
    df = df.merge(agencies, on="agcy_nbr", how="left")
    df.loc[:, "_employ_start"] = parse_dates(df.employ_start_date)
    df.loc[:, "_opened"] = parse_dates(df.case_opened_date)
    df.loc[:, "case_opened_date"] = to_iso(df._opened)
    df.loc[:, "case_closed_date"] = to_iso(parse_dates(df.case_closed_date))
    return df[
        [
            "complaint_nbr",
            "person_nbr",
            "agency_name",
            "_employ_start",
            "_opened",
            "case_opened_date",
            "case_closed_date",
        ]
    ]


def join_violations_to_sanctions(offenses, sanctions):
    """Keep only violations with a sanction, and the most recent sanction per violation."""
    df = offenses.merge(sanctions, on="complaint_nbr")
    df = df.sort_values("_sanction_date").drop_duplicates(
        ["complaint_nbr", "violation"], keep="last"
    )
    print(f"  Violations with a sanction: {len(df):,}")
    return df


def attach_stint(df, stints, review_dir):
    """Attach each violation to the stint at the complaint's agency containing its employment start or case-opened date. Complaints with no agency take the closest stint at any agency."""
    df = df.reset_index(drop=True)
    s = stints[["person_nbr", "agency_name", "type", "_start", "_end"]]
    s = s.rename(columns={"agency_name": "_stint_agency"})
    m = df.reset_index(names="_row").merge(s, on="person_nbr", how="left")

    end = m._end.fillna(pd.Timestamp.max)
    anchor = m._employ_start.fillna(m._opened)
    inside = (anchor >= m._start) & (anchor <= end)
    distance = (
        (m._start - anchor).clip(lower=pd.Timedelta(0))
        + (anchor - end).clip(lower=pd.Timedelta(0))
    ).dt.days
    same_agency = m.agency_name == m._stint_agency
    no_agency = m.agency_name.isna()

    m.loc[:, "_score"] = distance.where(inside, distance + 1)
    m.loc[~same_agency, "_score"] += 100_000
    keep = m._start.notna() & (same_agency | no_agency)
    m = m[keep].sort_values(["_row", "_score"]).drop_duplicates("_row")

    unmatched = df.loc[~df.index.isin(m._row)]
    write_review(
        unmatched, review_dir, "discipline_no_stint.csv", "No employment stint"
    )
    m.loc[:, "agency_name"] = m._stint_agency
    m.loc[:, "start_date"] = to_iso(m._start)
    m.loc[:, "end_date"] = to_iso(m._end)
    return m.drop(columns=["_row", "_stint_agency", "_score"])


def drop_duplicate_incidents(df, review_dir):
    """Keep one row when FDLE opened several cases for the same incident. Matches on person, violation, sanction and sanction date."""
    key = ["person_nbr", "violation", "sanction", "sanction_date"]
    df = df.sort_values("_start")
    dup = (df.sanction_date != "") & df.duplicated(key, keep="last")
    write_review(
        df[dup],
        review_dir,
        "duplicate_incidents.csv",
        "Same incident under another case_id",
    )
    return df[~dup]


def build_discipline(tbls, people, agencies, stints, codes, review_dir):
    print(
        f"\ncomplaint.csv: {len(tbls['complaint']):,}, "
        f"complaint_offenses.csv: {len(tbls['complaint_offenses']):,}, "
        f"complaint_discipline.csv: {len(tbls['complaint_discipline']):,}"
    )
    offenses = clean_offenses(tbls["complaint_offenses"], codes)
    sanctions = clean_sanctions(tbls["complaint_discipline"], codes)
    complaints = clean_complaints(tbls["complaint"], agencies)
    return (
        join_violations_to_sanctions(offenses, sanctions)
        .merge(complaints, on="complaint_nbr")
        .pipe(attach_stint, stints, review_dir)
        .pipe(drop_duplicate_incidents, review_dir)
        .merge(people, on="person_nbr", how="left")
        .rename(columns={"complaint_nbr": "case_id"})
        .assign(state="fl")
    )


# main


def validate(df, name, key):
    required = [
        "person_nbr",
        "first_name",
        "last_name",
        "agency_name",
        "start_date",
        "end_date",
    ]
    missing = [c for c in required if c not in df.columns]
    assert not missing, f"{name}: missing required columns {missing}"
    assert (df.start_date != "").all(), f"{name}: empty start_date"
    assert not df.duplicated(key).any(), f"{name}: duplicate {key}"
    for col in required[:-1]:
        n = (df[col].fillna("") == "").sum()
        if n:
            print(f"  Warning: {name}.{col} has {n:,} empty values")


def write_index(df, output_dir, fname):
    path = os.path.join(output_dir, fname)
    df.to_csv(path, index=False)
    print(
        f"\nWrote {len(df):,} rows, {df.person_nbr.nunique():,} officers, "
        f"{df.agency_name.nunique():,} agencies → {path}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--output-dir", default="data/output")
    args = parser.parse_args()
    review_dir = os.path.join(args.output_dir, "review")
    os.makedirs(review_dir, exist_ok=True)

    tbls = {
        name: read_tbl(args.input_dir, name)
        for name in [
            "employment",
            "person_data",
            "agencies",
            "certificates",
            "complaint",
            "complaint_offenses",
            "complaint_discipline",
        ]
    }
    codes = read_codes(args.input_dir)

    people = clean_people(tbls["person_data"], codes, review_dir)
    agencies = clean_agency_names(tbls["agencies"])
    certs = current_certificate_status(tbls["certificates"], codes)

    stints = build_employment(tbls, people, agencies, certs, codes, review_dir)
    discipline = build_discipline(
        tbls, people, agencies, stints, codes, review_dir
    )

    employment_cols = [
        "person_nbr",
        "full_name",
        "first_name",
        "middle_name",
        "last_name",
        "suffix",
        "agency_name",
        "type",
        "employment_status",
        "start_date",
        "end_date",
        "separation_reason",
        "notes",
        "current_certificate_status",
        "race",
        "sex",
        "year_of_birth",
        "state",
    ]
    discipline_cols = [
        "case_id",
        "person_nbr",
        "full_name",
        "first_name",
        "middle_name",
        "last_name",
        "suffix",
        "agency_name",
        "type",
        "start_date",
        "end_date",
        "case_opened_date",
        "case_closed_date",
        "violation",
        "violation_date",
        "violation_comments",
        "sanction",
        "sanction_date",
        "sanction_comments",
        "race",
        "sex",
        "year_of_birth",
        "state",
    ]

    emp = stints[employment_cols].sort_values(["person_nbr", "start_date"])
    validate(emp, "fl_index", ["person_nbr", "agency_name", "start_date"])
    dis = discipline[discipline_cols].sort_values(["person_nbr", "case_id"])
    validate(dis, "fl-discipline_index", ["case_id", "violation"])

    write_index(emp, args.output_dir, "fl_index.csv")
    write_index(dis, args.output_dir, "fl-discipline_index.csv")


if __name__ == "__main__":
    main()
