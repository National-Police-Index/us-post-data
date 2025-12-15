import pandas as pd


def clean_name(name):
    return (
        name.casefold()
        .strip()
        .replace(" ", "_")
        .replace(".", "_")
        .replace("employment_", "")
        .replace("employing_organization_name_", "employer_")
        .replace("person_", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace("_current_", "_")
    )


def clean_column_names(data):
    out = data.copy()
    out.columns = [clean_name(column) for column in out.columns]
    return out.rename(
        columns={
            "date_of_birth": "DOB",
            "psid": "PSID",
            "eeoc_category": "race_ethnicity",
            "employing_organization_name": "employer_0",
            "start_date": "start_date_0",
            "end_date": "end_date_0",
            "title_rank_current": "title_rank_0",
            "status": "status_0",
        }
    )


# Load the spreadsheet
raw = pd.read_excel("input/officer-employment-history-7.25.24.xlsx")
df = clean_column_names(raw)

# Reshape the DataFrame from wide to long format

start_date_columns = [c for c in df.columns if c.startswith("start_date")]
end_date_columns = [c for c in df.columns if c.startswith("end_date")]
title_rank_columns = [c for c in df.columns if c.startswith("title_rank")]
status_columns = [c for c in df.columns if c.startswith("status")]
employer_columns = [c for c in df.columns if c.startswith("employer")]

# Melt the start date columns
start_dates_df = df.melt(
    id_vars=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
    ],
    value_vars=start_date_columns,
    var_name="Start_Date_Number",
    value_name="start_date",
)
start_dates_df = start_dates_df.dropna(subset=["start_date"])

assert set(df.PSID) == set(start_dates_df.PSID)

# Melt the end date columns
end_dates_df = df.melt(
    id_vars=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
    ],
    value_vars=end_date_columns,
    var_name="End_Date_Number",
    value_name="end_date",
)

# Melt the title rank columns
titles_df = df.melt(
    id_vars=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
    ],
    value_vars=title_rank_columns,
    var_name="Title_Rank_Number",
    value_name="title_rank",
)

# Melt the status columns
statuses_df = df.melt(
    id_vars=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
    ],
    value_vars=status_columns,
    var_name="Status_Number",
    value_name="status",
)

# Melt the employers columns
employers_df = df.melt(
    id_vars=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
    ],
    value_vars=employer_columns,
    var_name="Employer_Number",
    value_name="employer",
)

# Extract

start_dates_df["Start_Date_Number"] = start_dates_df[
    "Start_Date_Number"
].str.extract(r"(\d+)")
end_dates_df["End_Date_Number"] = end_dates_df["End_Date_Number"].str.extract(
    r"(\d+)"
)
titles_df["Title_Rank_Number"] = titles_df["Title_Rank_Number"].str.extract(
    r"(\d+)"
)
statuses_df["Status_Number"] = statuses_df["Status_Number"].str.extract(
    r"(\d+)"
)
employers_df["Employer_Number"] = employers_df["Employer_Number"].str.extract(
    r"(\d+)"
)


# Merge jobs and dates DataFrames
long_df = pd.merge(
    start_dates_df,
    end_dates_df,
    left_on=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
        "Start_Date_Number",
    ],
    right_on=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
        "End_Date_Number",
    ],
)

long_df = pd.merge(
    long_df,
    titles_df,
    left_on=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
        "Start_Date_Number",
    ],
    right_on=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
        "Title_Rank_Number",
    ],
)


long_df = pd.merge(
    long_df,
    statuses_df,
    left_on=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
        "Start_Date_Number",
    ],
    right_on=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
        "Status_Number",
    ],
)

long_df = pd.merge(
    long_df,
    employers_df,
    left_on=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
        "Start_Date_Number",
    ],
    right_on=[
        "last_name",
        "first_name",
        "gender",
        "DOB",
        "PSID",
        "race_ethnicity",
        "Employer_Number",
    ],
)

# Drop unnecessary columns
final_df = long_df.drop(
    columns=[
        "Start_Date_Number",
        "End_Date_Number",
        "Title_Rank_Number",
        "Status_Number",
        "Employer_Number",
    ]
)

# format dates
final_df.start_date = pd.to_datetime(
    final_df.start_date, errors="coerce"
).dt.strftime("%Y-%m-%d")
final_df.end_date = pd.to_datetime(
    final_df.end_date, errors="coerce"
).dt.strftime("%Y-%m-%d")
final_df["birth_year"] = pd.to_datetime(
    final_df.DOB, errors="coerce"
).dt.strftime("%Y")

out = final_df.rename(
    columns={
        "PSID": "person_nbr",
        "employer": "agency_name",
        "race_ethnicity": "race",
        "title_rank": "rank",
        "status": "separation_reason",
    }
)[
    [
        "person_nbr",
        "agency_name",
        "last_name",
        "first_name",
        "gender",
        "race",
        "birth_year",
        "start_date",
        "end_date",
        "rank",
        "separation_reason",
    ]
]

assert ~any(out.agency_name.isna())

# Save the transformed DataFrame to a new spreadsheet
out.to_csv("output/indiana_index.csv", index=False)
