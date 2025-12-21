# vim: set ts=4 sts=0 sw=4 si fenc=utf-8 et:
# vim: set fdm=marker fmr={{{,}}} fdl=0 foldcolumn=4:
# note: code originally by @ayyubibrahimi for aug2024 release
# adapted for 2025 update by @tarakc02

import pandas as pd


# dealing with goofy excel format {{{
def remove_first_column(df):
    df = df.iloc[:, 1:]
    return df


def propagate_uids(df):
    result_df = df.copy()

    # Initialize variables to track current person
    current_uid = None
    current_person_rows = []

    # Process rows sequentially
    processed_rows = []

    for _, row in result_df.iterrows():
        # Check if this is a subtotal row (has 'Subtotal' in last_name)
        if isinstance(row["last_name"], str) and "Subtotal" in row["last_name"]:
            # Process accumulated rows for the previous person
            if current_person_rows:
                processed_rows.extend(current_person_rows)

            # Reset tracking variables
            current_uid = None
            current_person_rows = []

            # Add the subtotal row
            processed_rows.append(row.to_dict())

        else:
            # If this row has a non-NaN UID, store it as the current UID
            if pd.notna(row["person_nbr"]):
                current_uid = row["person_nbr"]

            # Create a copy of the row and update its UID
            row_dict = row.to_dict()
            if current_uid is not None:
                row_dict["person_nbr"] = current_uid

            # Add this row to the current person's rows
            current_person_rows.append(row_dict)

    # Process the last person's rows if any remain
    if current_person_rows:
        processed_rows.extend(current_person_rows)

    # Convert processed rows back to DataFrame
    result_df = pd.DataFrame(processed_rows)

    # Ensure numeric UIDs where possible
    result_df["person_nbr"] = pd.to_numeric(
        result_df["person_nbr"], errors="ignore"
    )

    return result_df


def remove_first_8_rows(df):
    df = df.iloc[9:]
    return df


def drop_empty_rows(df):
    return df[~(df.person_nbr == "Subtotal")]


def drop_cols(df):
    df = df.drop(columns=["agency_status", "Unnamed: 2"])
    return df


def rename_cols(df):
    df = df.rename(
        columns={
            "Unnamed: 1": "person_nbr",
            "Unnamed: 3": "last_name",
            "Unnamed: 4": "first_name",
            "Unnamed: 5": "middle_name",
            "Unnamed: 6": "agency_name",
            "Unnamed: 7": "employment_status",
            "Unnamed: 8": "start_date",
            "Unnamed: 9": "agency_status",
            "Unnamed: 10": "end_date",
        }
    )
    return df


# }}}


# cleaning data {{{
def clean_agency_name(df):
    df.loc[:, "agency_name"] = (
        df.agency_name.str.lower()
        .str.strip()
        .str.replace(r"dept\.?", "department", regex=True)
        .str.replace(r"\bco\.", "county", regex=True)
    )
    return df[~(df.agency_name.fillna("") == "")]


def fix_dates(df):
    df.loc[:, "start_date"] = pd.to_datetime(df.start_date, errors="coerce")
    df.loc[:, "end_date"] = pd.to_datetime(df.end_date, errors="coerce")
    return df


def clean_status(df):
    df.loc[:, "employment_status"] = (
        df.employment_status.str.lower()
        .str.strip()
        .str.replace(r"terminated", "inactive", regex=False)
    )
    return df


# }}}


if __name__ == "__main__":
    df = pd.read_excel("input/mn-2025-01-21.xlsx")
    df = (
        df.pipe(remove_first_column)
        .pipe(rename_cols)
        .pipe(propagate_uids)
        .pipe(remove_first_8_rows)
        .pipe(drop_empty_rows)
        .pipe(drop_cols)
        .pipe(clean_agency_name)
        .pipe(fix_dates)
        .pipe(clean_status)
    )
    df.to_csv("output/mn-index-2025-01-21.csv", index=False)
