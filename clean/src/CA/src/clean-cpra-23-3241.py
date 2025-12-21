import nameparser
import pandas as pd


term_code_dictionary = {
    "1": "Resigned",
    "2": "Discharged",
    "3": "Retired",
    "4": "Deceased",
    "5": "Felony",
    "6": "Other",
    "7": "Promotion/Demotion",
    "8": "Involuntary Separation",
    "9": "Separated Pending Complaint, Administrative Charge, or Investigation for Serious Misconduct",
    "10": "Status Change",
    "11": "Did Not Complete Probation",
    "Z": "Unknown",
}


def clean_names(df):
    out = df
    hn = out.officer_name.apply(nameparser.HumanName)
    out["last_name"] = hn.apply(lambda x: x.last)
    out["first_name"] = hn.apply(lambda x: x.first)
    out["middle_name"] = hn.apply(lambda x: x.middle)
    return out


if __name__ == "__main__":
    officers = pd.read_csv("input/cpra-23-3241-officers.csv")
    officers.columns = officers.columns.str.lower()

    employment = pd.read_csv("input/cpra-23-3241-employment.csv")
    employment.columns = employment.columns.str.lower()
    employment["separation_reason"] = employment.term_code.map(
        term_code_dictionary
    )

    assert all(employment["id"].isin(officers["id"]))
    assert len(employment[["agency", "agency_name"]].drop_duplicates()) == len(
        employment.agency.drop_duplicates()
    )

    out = (
        employment.drop("rank", axis=1)
        .groupby(["id", "agency", "hire_date"])
        .tail(1)
        .merge(officers, on="id", how="inner")
        .pipe(clean_names)[
            [
                "post_id",
                "first_name",
                "middle_name",
                "last_name",
                "agency_name",
                "hire_date",
                "to",
                "separation_reason",
            ]
        ]
        .rename(
            columns={
                "post_id": "person_nbr",
                "hire_date": "start_date",
                "to": "end_date",
            }
        )
    )

    out.start_date = pd.to_datetime(out.start_date).dt.strftime("%Y-%m-%d")
    out.end_date = pd.to_datetime(out.end_date).dt.strftime("%Y-%m-%d")
    out.to_csv("output/ca-23-leo-processed.csv", index=False)
