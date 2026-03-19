import numpy as np
import pandas as pd


def read_tbl():
    """Read and prepare the officer appointments data"""
    df = pd.read_csv("../data/input/2025-8-26/Officer List 082225.csv")

    df = df.rename(
        columns={
            "Agency": "agency_name",
            "Agency ORI": "agency_ori",
            "Last_Name": "last_name",
            "First_Name": "first_name",
            "Middle_Name": "middle_name",
            "AppointedDate": "start_date",
            "TerminationDate": "end_date",
            "Term_Desc": "separation_reason",
            "PostId": "person_nbr",
            "Rank": "rank",
            "CertStatus_Current": "status", 
        }
    )

    df = df.fillna("")

    df = df.drop(
        columns=[
            "CertStatus_atTerm",
            "FinalActions",
        ]
    )
    return df


def clean_sep_reason(df):
    """Clean and standardize separation reasons"""
    df.loc[:, "separation_reason"] = (
        df.separation_reason.str.lower()
        .str.strip()
        .str.replace(r"misconduct - no", "not for misconduct", regex=True)
        .str.replace(r"misconduct - yes", "misconduct", regex=True)
    )

    df.loc[df.separation_reason == "", "separation_reason"] = "unknown"
    return df


def clean_agency_name(df):
    """Clean and standardize agency names"""
    df.loc[:, "agency_name"] = (
        df.agency_name.str.lower()
        .str.strip()
        .str.replace(r"^az ", "arizona ", regex=True)
        .str.replace(r" dept ", " department ", regex=False)
        .str.replace(r"dept$", "department", regex=True)
        .str.replace(r"departme$", "department", regex=True)
        .str.replace(r" enf ", " enforcement ", regex=False)
        .str.replace(r" az ", " arizona ", regex=False)
        .str.replace(r" & ", " and ", regex=False)
        .str.replace(r"contr$", "control", regex=True)
        .str.replace(r"pd$", "police department", regex=True)
        .str.replace(r"departm$", "department", regex=True)
        .str.replace(r" cty ", " county ", regex=False)
        .str.replace(r"-(\w+)$", r"- \1", regex=True)
        .str.replace(r"(\w+)\,(\w+)", r"\1, \2", regex=True)
        .str.replace(r"animal se", "animal services", regex=False)
        .str.replace(r"^ret\,? ", "", regex=True)
        .str.replace(r"sheriffs", "sheriff's", regex=False)
        .str.replace(r"comm coll", "community college", regex=False)
    )
    return df


def read_ori():
    """Read and prepare the ORI agency reference data"""
    df = pd.read_csv("../data/input/da35158-0001.csv")

    df = df[
        [
            "ORI9",
            "ORI7",
            "NAME",
            "COUNTYNAME",
            "AGCYTYPE",
            "ADDRESS_NAME",
            "ADDRESS_STR1",
            "ADDRESS_STR2",
            "ADDRESS_CITY",
            "ADDRESS_STATE",
            "ADDRESS_ZIP",
            "LG_POPULATION",
            "INTPTLAT",
            "INTPTLONG",
        ]
    ]

    df = df.rename(
        columns={
            "ORI9": "ori_9",
            "ORI7": "ori_7",
            "NAME": "ori_name",
            "COUNTYNAME": "county",
            "AGCYTYPE": "type",
            "ADDRESS_NAME": "addr_name",
            "ADDRESS_STR1": "addr_street_one",
            "ADDRESS_STR2": "addr_street_two",
            "ADDRESS_CITY": "city",
            "ADDRESS_STATE": "state",
            "ADDRESS_ZIP": "zipcode",
            "LG_POPULATION": "population_served",
            "INTPTLAT": "latitude",
            "INTPTLONG": "longitude",
        }
    )
    return df


def create_officers_table(df):
    """
    Create officers table with one record per unique person_nbr.
    Schema: id, first_name, middle_name, last_name, suffix, year_of_birth,
            race, sex, created_at, created_by, updated_at, updated_by,
            deleted_at, deleted_by
    """
    # Get unique officers by person_nbr
    officers = df[
        ["person_nbr", "first_name", "middle_name", "last_name"]
    ].copy()

    # Remove empty strings and convert to None for proper handling
    officers = officers.replace("", np.nan)

    # Deduplicate based on person_nbr
    officers = officers.drop_duplicates(subset=["person_nbr"]).reset_index(
        drop=True
    )

    # Use person_nbr as the officer ID
    officers = officers.rename(columns={"person_nbr": "id"})

    # Add optional fields (not available in source data)
    officers["suffix"] = None
    officers["year_of_birth"] = None
    officers["race"] = None
    officers["sex"] = None

    # Add audit fields (using defaults for import)
    officers["created_by"] = 1  # System user
    officers["created_at"] = pd.Timestamp.now()
    officers["updated_by"] = None
    officers["updated_at"] = None
    officers["deleted_by"] = None
    officers["deleted_at"] = None

    return officers


def create_agencies_table(ori_df, appointments_df):
    """
    Create agencies table from ORI data merged with appointment agency names.
    Also creates records for agencies that exist in appointments but not in ORI data.
    Schema: id, parent_agency_id, name, short_name, type, ori_7, ori_9,
            county, addr_name, addr_street_one, addr_street_two, city, state,
            zipcode, public_agency, population_served, longitude, latitude,
            notes, created_at, created_by, updated_at, updated_by,
            deleted_at, deleted_by
    """
    agencies = ori_df.copy()

    # Get cleaned agency names from appointments
    agency_names = appointments_df[appointments_df["agency_ori"] != ""][
        ["agency_ori", "agency_name"]
    ].drop_duplicates(subset=["agency_ori"])

    # Merge cleaned names with ORI data
    agencies = agencies.merge(
        agency_names, left_on="ori_9", right_on="agency_ori", how="left"
    )

    # Use cleaned agency_name if available, otherwise use ori_name
    agencies["name"] = agencies["agency_name"].fillna(agencies["ori_name"])

    agencies = agencies.drop(columns=["agency_ori", "ori_name", "agency_name"])

    # Deduplicate by ori_9
    agencies = agencies.drop_duplicates(subset=["ori_9"]).reset_index(drop=True)

    # Find agencies in appointments that are NOT in ORI data (excluding empty ORIs)
    ori_oris = set(agencies["ori_9"].unique())
    appointments_oris = set(
        appointments_df[appointments_df["agency_ori"] != ""][
            "agency_ori"
        ].unique()
    )
    missing_oris = appointments_oris - ori_oris

    # Create records for missing agencies
    if missing_oris:
        missing_agencies = appointments_df[
            appointments_df["agency_ori"].isin(missing_oris)
        ][["agency_ori", "agency_name"]].drop_duplicates()

        # Create a dataframe with the same structure as agencies
        missing_df = pd.DataFrame()
        missing_df["ori_9"] = missing_agencies["agency_ori"].values
        missing_df["ori_7"] = None
        missing_df["county"] = None
        missing_df["type"] = None
        missing_df["addr_name"] = None
        missing_df["addr_street_one"] = None
        missing_df["addr_street_two"] = None
        missing_df["city"] = None
        missing_df["state"] = "AZ"
        missing_df["zipcode"] = None
        missing_df["population_served"] = None
        missing_df["latitude"] = None
        missing_df["longitude"] = None
        missing_df["name"] = missing_agencies["agency_name"].values

        agencies = pd.concat([agencies, missing_df], ignore_index=True)

    # Handle agencies with NO ORI code (agency_ori is empty string)
    no_ori_agencies = appointments_df[appointments_df["agency_ori"] == ""][
        ["agency_name"]
    ].drop_duplicates()

    if len(no_ori_agencies) > 0:
        no_ori_df = pd.DataFrame()
        no_ori_df["ori_9"] = None
        no_ori_df["ori_7"] = None
        no_ori_df["county"] = None
        no_ori_df["type"] = None
        no_ori_df["addr_name"] = None
        no_ori_df["addr_street_one"] = None
        no_ori_df["addr_street_two"] = None
        no_ori_df["city"] = None
        no_ori_df["state"] = "AZ"
        no_ori_df["zipcode"] = None
        no_ori_df["population_served"] = None
        no_ori_df["latitude"] = None
        no_ori_df["longitude"] = None
        no_ori_df["name"] = no_ori_agencies["agency_name"].values

        # Append agencies without ORI
        agencies = pd.concat([agencies, no_ori_df], ignore_index=True)

    # Add ID column
    agencies.insert(0, "id", range(1, len(agencies) + 1))

    # Add optional fields not in source data
    agencies.insert(1, "parent_agency_id", None)
    agencies.insert(3, "short_name", None)
    agencies.insert(14, "public_agency", None)
    agencies.insert(17, "notes", None)

    # Ensure state defaults to AZ if missing
    agencies["state"] = agencies["state"].fillna("AZ")

    # Add audit fields
    agencies["created_by"] = 1  # System user
    agencies["created_at"] = pd.Timestamp.now()
    agencies["updated_by"] = None
    agencies["updated_at"] = None
    agencies["deleted_by"] = None
    agencies["deleted_at"] = None

    # Replace empty strings with None
    agencies = agencies.replace("", np.nan)

    return agencies


def create_appointments_table(appointments_df, agencies_df):
    """
    Create appointments table linking officers to agencies.
    Deduplicate based on unique combination of person_nbr, agency_ori, start_date, end_date.
    Schema: id, person_nbr, officer_id, agency_id, rank, type, start_date,
            end_date, separation_reason, notes, created_at, created_by,
            updated_at, updated_by, deleted_at, deleted_by
    """
    appointments = appointments_df.copy()

    # First, match agencies by ORI code
    agencies_with_ori = agencies_df[agencies_df["ori_9"].notna()][
        ["id", "ori_9", "name"]
    ].copy()
    agencies_with_ori = agencies_with_ori.rename(columns={"id": "agency_id"})

    appointments = appointments.merge(
        agencies_with_ori[["agency_id", "ori_9"]],
        left_on="agency_ori",
        right_on="ori_9",
        how="left",
    )

    # For appointments without ORI match, try to match by name
    no_match_mask = appointments["agency_id"].isna()
    if no_match_mask.any():
        agencies_no_ori = agencies_df[agencies_df["ori_9"].isna()][
            ["id", "name"]
        ].copy()
        agencies_no_ori = agencies_no_ori.rename(
            columns={"id": "agency_id_by_name"}
        )

        # Merge on agency name for those without ORI match
        appointments = appointments.merge(
            agencies_no_ori, left_on="agency_name", right_on="name", how="left"
        )

        # Fill in agency_id from name match where ORI match failed
        appointments.loc[no_match_mask, "agency_id"] = appointments.loc[
            no_match_mask, "agency_id_by_name"
        ]

        # Drop temporary columns
        if "agency_id_by_name" in appointments.columns:
            appointments = appointments.drop(
                columns=["agency_id_by_name", "name"]
            )

    # officer_id is the same as person_nbr (since we use person_nbr as officer.id)
    appointments["officer_id"] = appointments["person_nbr"]

    # Deduplicate appointments based on unique combination
    # Keep first occurrence of each unique appointment
    appointments = appointments.drop_duplicates(
        subset=[
            "person_nbr",
            "agency_ori",
            "agency_name",
            "start_date",
            "end_date",
        ]
    ).reset_index(drop=True)

    # Select and order columns for appointments table
    appointments = appointments[
        [
            "person_nbr",
            "officer_id",
            "agency_id",
            "rank",
            "start_date",
            "end_date",
            "separation_reason",
            "status",
        ]
    ]

    # Add ID column
    appointments.insert(0, "id", range(1, len(appointments) + 1))

    # Add optional fields not in source data
    appointments.insert(5, "type", None)
    appointments.insert(9, "notes", None)

    # Add audit fields
    appointments["created_by"] = 1  # System user
    appointments["created_at"] = pd.Timestamp.now()
    appointments["updated_by"] = None
    appointments["updated_at"] = None
    appointments["deleted_by"] = None
    appointments["deleted_at"] = None

    # Replace empty strings with None
    appointments = appointments.replace("", np.nan)

    return appointments


if __name__ == "__main__":
    print("Reading and processing data...")

    # pre-process az data
    az_raw = read_tbl()
    appointments_raw = az_raw.pipe(clean_sep_reason).pipe(clean_agency_name)

    # Read ORI data
    ori_data = read_ori()

    # Generate the three tables
    print("\nGenerating officers table...")
    officers = create_officers_table(appointments_raw)

    print("Generating agencies table...")
    agencies = create_agencies_table(ori_data, appointments_raw)

    print("Generating appointments table...")
    appointments = create_appointments_table(appointments_raw, agencies)

    # Display results
    print("\n" + "=" * 80)
    print("OFFICERS TABLE")
    print("=" * 80)
    print(f"Shape: {officers.shape}")
    print(f"\nColumns: {list(officers.columns)}")
    print("\nFirst 5 rows:")
    print(officers.head())

    print("\n" + "=" * 80)
    print("AGENCIES TABLE")
    print("=" * 80)
    print(f"Shape: {agencies.shape}")
    print(f"\nColumns: {list(agencies.columns)}")
    print("\nFirst 5 rows:")
    print(agencies.head())

    print("\n" + "=" * 80)
    print("APPOINTMENTS TABLE")
    print("=" * 80)
    print(f"Shape: {appointments.shape}")
    print(f"\nColumns: {list(appointments.columns)}")
    print("\nFirst 5 rows:")
    print(appointments.head())

    # Save to CSV files
    print("\n" + "=" * 80)
    print("Saving tables to CSV...")
    print("=" * 80)

    output_dir = "../data/output"
    officers.to_csv(f"{output_dir}/officers.csv", index=False)
    agencies.to_csv(f"{output_dir}/agencies.csv", index=False)
    appointments.to_csv(f"{output_dir}/appointments.csv", index=False)

    print(f"\n✓ officers.csv saved ({len(officers)} records)")
    print(f"✓ agencies.csv saved ({len(agencies)} records)")
    print(f"✓ appointments.csv saved ({len(appointments)} records)")
    print("\nDone!")
