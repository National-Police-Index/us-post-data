import argparse

import pandas as pd


# setup and cleaning functions {{{
def getargs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--output")
    return parser.parse_args()


def cleanstring(strings):
    return (
        strings.fillna("")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.upper()
    )


def select_or_create_indexcols(df):
    out = df.rename(
        columns={
            "facility_name": "agcy_name",
            "unique_id": "person_nbr",
            "class_title": "rank",
            "trans_eff_date": "event_date",
            "type_of_transaction": "event",
            "position_number": "position",
            "pos_seq": "position_seq_nbr",
        }
    )
    out["type"] = "CORRECTIONS"
    out["stat05_ind"] = out.stat05.notna()
    outcols = [
        "person_nbr",
        "full_name",
        "last_name",
        "first_name",
        "middle_initial",
        "agcy_name",
        "type",
        "rank",
        "event",
        "event_date",
        "position",
        "position_seq_nbr",
        "stat05_ind",
    ]
    out.event_date = pd.to_datetime(out.event_date)
    return out[outcols]


def clean_names(df):
    out = df.copy()
    # 3,770 rows are NAME WITHHELD
    out.first_name = out.first_name.fillna("")
    out.last_name = cleanstring(out.last_name)
    out["first_middle"] = cleanstring(out.first_name)
    out["middle_initial"] = out.first_middle.str.extract(" ([A-Z])$")
    out["first_name"] = out.first_middle
    out.loc[out.middle_initial.notna(), "first_name"] = (
        out.first_middle.str.slice(0, -2)
    )
    out["full_name"] = cleanstring(
        out.first_name
        + " "
        + out.middle_initial.fillna("")
        + " "
        + out.last_name
    )
    return out


def clean_stringcols(df):
    out = df.copy()
    stringcols = [
        c
        for c in out.columns
        if "date" not in c and "_nbr" not in c and "_ind" not in c
    ]
    for col in stringcols:
        out[col] = cleanstring(out[col])
    return out


def standardize_position(df):
    out = df.copy()
    out.position = out.position.str.replace(r"\-", "", regex=True).str.zfill(13)
    out["agcy_code"] = out.position.str.slice(0, 3)
    out["class_code"] = out.position.str.slice(7, 10)
    out["matchable"] = out.agcy_code + out.class_code
    assert all(~out.position.str.contains("[^0-9]", regex=True))
    return out


def make_dict(df, code, desc):
    return (
        df[[code, desc]]
        .drop_duplicates()
        .groupby(code)
        .agg({desc: lambda x: " -AKA- ".join(x.sort_values())})
        .reset_index()
    )


def standardize(df, code, desc):
    assert all(df[code].notna())
    assert all(df[desc].notna())
    code_dict = make_dict(df, code, desc)
    out = df.drop(desc, axis=1, inplace=False).merge(
        code_dict, on=code, how="inner"
    )
    assert len(out) == len(df)
    assert set(out.columns) == set(df.columns)
    out[desc] = out[code] + ": " + out[desc]
    return out


# }}}


# go from event data to stint data {{{
def make_stints(df, work, seps, matchcols):
    merged = work.merge(seps, on=matchcols, how="inner")
    merged["dd"] = merged.separation_date - merged.event_date
    merged = merged.loc[merged.dd >= pd.Timedelta(0, "days")].copy()
    f1 = pd.concat(pick_seps(g) for gid, g in merged.groupby("record_nbr"))
    f2 = pd.concat(pick_seps(g) for gid, g in f1.groupby("sep_rec_nbr"))
    stints = f2.drop("dd", axis=1, inplace=False).reset_index(drop=True)
    assert len(stints[["record_nbr"]].drop_duplicates()) == len(stints)
    assert len(stints[["sep_rec_nbr"]].drop_duplicates()) == len(stints)
    return stints


# linking separations to appointments/changes
# separation date has to be > appt/change date
# if there are multiple possible candidates,
# keep the one that results in the tightest start/end window
def link_separations(df, usecols):
    work = df[df.event != "SEPARATION"]
    seps = prep_separations(df, usecols)
    stints = make_stints(df, work, seps, usecols)
    work_out = work[~work.record_nbr.isin(stints.record_nbr)].reset_index(
        drop=True
    )
    seps_out = (
        df[
            (df.record_nbr.isin(seps.sep_rec_nbr))
            & (~df.record_nbr.isin(stints.sep_rec_nbr))
        ]
        .rename(columns={"event_date": "separation_date"})
        .reset_index(drop=True)
    )
    out = pd.concat([work_out, seps_out, stints], axis=0, ignore_index=True)
    assert all(out.record_nbr != out.sep_rec_nbr)
    assert (set(out.record_nbr).union(set(out.sep_rec_nbr.dropna()))) == set(
        df.record_nbr
    )
    return out.drop("sep_rec_nbr", axis=1, inplace=False)


def prep_separations(df, matchcols):
    cols = ["record_nbr", "event_date"] + matchcols
    if "separation_date" in df.columns:
        df = df.drop("event_date", axis=1, inplace=False).rename(
            columns={"separation_date": "event_date"}
        )
    seps = df.loc[df.event == "SEPARATION", cols]
    return seps.rename(
        columns={"event_date": "separation_date", "record_nbr": "sep_rec_nbr"}
    )


def pick_seps(cands):
    """link separations to the right job record"""
    if len(cands) == 1:
        return cands
    out = cands.loc[cands.dd == cands.dd.min()]
    assert len(out) <= 1
    return out


# }}}

if __name__ == "__main__":
    args = getargs()

    cpost = (
        pd.read_csv(args.input)
        .drop_duplicates()
        .rename(columns={"06_30_2005_cs_ind": "stat05"}, inplace=False)
    )

    clean = (
        cpost.pipe(clean_names)
        .pipe(select_or_create_indexcols)
        .pipe(clean_stringcols)
        .pipe(standardize_position)
        .pipe(standardize, code="agcy_code", desc="agcy_name")
        .pipe(standardize, code="class_code", desc="rank")
        .drop_duplicates()
    )

    clean["record_nbr"] = clean.reset_index().index
    assert all(
        (clean.event.isin(["APPOINTMENT", "SEPARATION"])) | (clean.stat05_ind)
    )

    pass1 = link_separations(clean, usecols=["person_nbr", "position"])

    # the first pass of linking is based on the position number
    # after that, if there is an unlinked separation that is the same agcy+rank as an unterminated appt, use that.
    init_db = (
        pass1.drop(
            [
                "record_nbr",
                "position_seq_nbr",
                "position",
                "agcy_code",
                "class_code",
            ],
            axis=1,
            inplace=False,
        )
        .drop_duplicates()
        .reset_index(drop=True)
    )

    init_db["record_nbr"] = init_db.reset_index().index

    ok = init_db[
        (init_db.event_date.notna()) & (init_db.separation_date.notna())
    ]

    sep_no_start = init_db.loc[
        init_db.event_date.isna(),
        ["record_nbr", "person_nbr", "matchable", "separation_date"],
    ].rename(columns={"record_nbr": "sep_rec_nbr"})

    cands = init_db[
        (init_db.event_date.notna()) & (init_db.separation_date.isna())
    ].drop("separation_date", axis=1, inplace=False)

    extra_stints = make_stints(
        init_db[~init_db.record_nbr.isin(ok.record_nbr)].reset_index(drop=True),
        cands.reset_index(drop=True),
        sep_no_start.reset_index(drop=True),
        ["person_nbr", "matchable"],
    )

    all_stint_data = pd.concat(
        [
            extra_stints.drop("sep_rec_nbr", axis=1, inplace=False),
            init_db.loc[
                (
                    ~init_db.record_nbr.isin(extra_stints.record_nbr)
                    & (~init_db.record_nbr.isin(extra_stints.sep_rec_nbr))
                )
            ],
        ],
        ignore_index=True,
    ).sort_values(["person_nbr", "matchable", "event_date"])

    # now flatten stints at the same location with the same rank
    all_stint_data["new_group"] = (
        all_stint_data.groupby(["person_nbr", "matchable"])
        .event.shift(1)
        .isna()
    )

    all_stint_data["new_stint"] = (
        all_stint_data.new_group
        | all_stint_data.groupby(["person_nbr", "matchable"])
        .separation_date.shift(1)
        .notna()
    )

    all_stint_data["stint_nbr"] = all_stint_data.groupby(
        ["person_nbr", "matchable"]
    ).new_stint.cumsum()

    true_start_dates = (
        all_stint_data.groupby(["person_nbr", "matchable", "stint_nbr"])
        .event_date.min()
        .reset_index()
        .rename(columns={"event_date": "start_date"})
    )

    true_end_dates = (
        all_stint_data.loc[
            all_stint_data.separation_date.notna(),
            ["person_nbr", "matchable", "stint_nbr", "separation_date"],
        ]
        .drop_duplicates()
        .rename(columns={"separation_date": "end_date"})
    )

    assert len(true_end_dates) == len(
        true_end_dates[
            ["person_nbr", "matchable", "stint_nbr"]
        ].drop_duplicates()
    )

    flat = all_stint_data.merge(
        true_start_dates,
        on=["person_nbr", "matchable", "stint_nbr"],
        how="left",
    ).merge(
        true_end_dates, on=["person_nbr", "matchable", "stint_nbr"], how="left"
    )

    assert all(flat.start_date.notna() | flat.event_date.isna())
    assert all(flat.end_date.notna() | flat.separation_date.isna())

    out = (
        flat[
            [
                "person_nbr",
                "first_name",
                "middle_initial",
                "last_name",
                "agcy_name",
                "start_date",
                "end_date",
            ]
        ]
        .drop_duplicates()
        .rename(
            columns={
                "agcy_name": "agency_name",
                "middle_initial": "middle_name",
            }
        )
    )

    origlen = len(clean[["person_nbr", "agcy_name"]].drop_duplicates())
    outlen = len(out[["person_nbr", "agency_name"]].drop_duplicates())
    assert origlen == outlen

    out.to_csv(args.output, index=False)
