import argparse

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


def getargs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--output")
    return parser.parse_args()


def clean_names(df):
    out = df
    hn = out.officer_name.apply(nameparser.HumanName)
    out["last_name"] = hn.apply(lambda x: x.last)
    out["first_name"] = hn.apply(lambda x: x.first)
    out["middle_name"] = hn.apply(lambda x: x.middle)
    return out


if __name__ == "__main__":
    args = getargs()
    ca = pd.read_excel(args.input)
    ca.columns = ca.columns.str.lower()
    ca["separation_reason"] = ca.separation_code.map(term_code_dictionary)

    out = (
        ca.drop("rank", axis=1)
        .pipe(clean_names)[
            [
                "post_id",
                "first_name",
                "middle_name",
                "last_name",
                "agency",
                "employment_start_date",
                "employment_end_date",
                "separation_reason",
            ]
        ]
        .rename(
            columns={
                "post_id": "person_nbr",
                "agency": "agency_name",
                "employment_start_date": "start_date",
                "employment_end_date": "end_date",
            }
        )
    )

    out.start_date = pd.to_datetime(out.start_date).dt.strftime("%Y-%m-%d")
    out.end_date = pd.to_datetime(out.end_date).dt.strftime("%Y-%m-%d")
    out.to_csv("output/ca-leo-processed.csv", index=False)
