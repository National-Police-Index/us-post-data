# Authors: LB
# Mainrainers: LB
# Copyright:   2024, HRDAG, GPL v2 or later
# =========================================
# us-post-data/preprocess/clean/KS/import/src
import logging
import os
from pathlib import Path

import pandas as pd
from nameparser import HumanName


# Configue the logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Create logger instance
logger = logging.getLogger(__name__)

"""
Column standard naming convention use all names that are present in dataframe.

column_names = [
    "person_nbr",
    "full_name",
    "last_name",
    "first_name",
    "middle_name",
    "middle_initial",
    "suffix",
    "birth_year",
    "age",
    "agcy_name",
    "type",
    "rank",
    "start_date",
    "end_date"]
"""

column_names = [
    "person_nbr",
    "full_name",
    "last_name",
    "first_name",
    "middle_name",
    "middle_initial",
    "suffix",
    "agency_name",
    "rank",
    "status",
    "start_date",
    "end_date",
]


def clean_names(df):
    out = df
    hn = out.officer_name.apply(HumanName)
    out["last_name"] = hn.apply(lambda x: x.last)
    out["first_name"] = hn.apply(lambda x: x.first)
    out["middle_name"] = hn.apply(lambda x: x.middle)
    out["middle_initial"] = hn.apply(lambda x: x.middle[:1])
    out["suffix"] = hn.apply(lambda x: x.suffix)
    return out


if __name__ == "__main__":
    data_input = Path("../input/")

    filtered_files = [
        x for x in data_input.rglob("*.xls") if "Certification" not in str(x)
    ]
    complete = pd.concat(
        pd.read_excel(x, skiprows=5, usecols="c:k") for x in filtered_files
    )
    logger.info("Data Loaded")

    complete.columns = complete.columns.str.lower()
    complete.columns = complete.columns.str.replace(" ", "_")
    new_complete = clean_names(complete)
    new_complete.drop(["unnamed:_3", "unnamed:_4"], axis=1, inplace=True)
    logger.info("Columns cleaned")

    print("\n")
    logger.info("Checking for duplicates")
    logger.info(new_complete[new_complete["cert_id"] == 16215])
    new_complete_2 = new_complete.copy()
    new_complete_2.drop_duplicates(inplace=True)
    print("\n")
    logger.info("Duplicates removed")
    logger.info(new_complete_2[new_complete_2["cert_id"] == 16215])

    print("\n")
    logger.info("Current column names")

    logger.info(new_complete_2.columns)
    new_complete_2.rename(
        columns={
            "officer_name": "full_name",
            "officers_rank": "rank",
            "stop_or_leave_date": "end_date",
            "cert_id": "person_nbr",
            # "agency_name": "agcy_name",
        },
        inplace=True,
    )
    new_complete_2 = new_complete_2.loc[:, column_names]

    print("\n")
    logger.info("Column standards applied")
    logger.info(new_complete_2.columns)
    new_complete_2["end_date"] = new_complete_2["end_date"].replace(
        "1/1/0001", ""
    )

    print("\n")

    logger.info("Data being exported to output directory.")
    output_path = "../output/ks-2024-index.csv"
    dir_path = os.path.dirname(output_path)
    os.makedirs(dir_path, exist_ok=True)
    new_complete_2.to_csv(output_path, index=False)

    assert (
        complete.duplicated().value_counts().iloc[0] == new_complete_2.shape[0]
    )
    print("\n")
    logger.info(
        f"Total number of records in data set are {new_complete_2.shape[0]}"
    )
    print("\n")
    logger.info("DONE")
