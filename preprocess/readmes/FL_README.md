# Florida Officer Data Processing

These data were obtained under the state open records law from the [Florida Department of Law Enforcement](https://www.fdle.state.fl.us/OGC/Public-Records.aspx). 

The data released includes personnel information, certification information, employment history, complaints and disciplinary actions for all officers certified in the state going back to the 1940s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.


## Data Files

FDLE provided a Microsoft Access database containing multiple relational tables in response to a state public records request, which were converted into a series of CSV files before processing.

1. `person_data.csv`: Contains personnel identifiers for law enforcement officers
2. `certificates.csv`: Contains certification data and current status for law enforcement officers
3. `employment.csv`: Contains employment history data for all officers
4. `agencies.csv`: Contains employer / police agency numbers and names for the state
5. `codes.csv`: Contains code definitions for various tables' shorthand codes
6. `complaint.csv`: Contains a parent complaint table that can be connected to officers
7. `complaint_discipline.csv`: Contains discipline data for complaints
8. `complaint_offenses.csv`: Contains offense data for complaints
9. `complaint_status.csv`: Contains status data for complaints
10. `complaint_activity.csv`: Contains multiple activity records for each complaint

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `stringi`: For string manipulation
- `janitor`: For cleaning data and managing the workspace

## Data Cleaning and Processing

The script performs the following tasks:

- Standardizes column names and tables for the original files provided by FDLE under Florida's open records law, in csv format.
- Creates an overall work history index file in a common format to match other states as part of the project.
- Converts relevant date columns to the `YYYY-MM-DD` format to be consistent throughout project.
- Combines information for unique person numbers for employment, agencies, person_data, and codes dataframes to create work history index.
- Cleans and reformats names throughout to deal with inconsistencies and a few edge cases of badly-formatted suffixes.
- Adds flags for license status. The ever_revoked column indicates whether the officer/person_nbr in question has ever had any law enforcement license revoked in the state of Florida. The column is an indicator that can point to potential issues that could warrant looking at additional detail in the license and complaint data.
- Merges with template index to be consistent with indexes for other states across the project.
- Exports the final processed data to a CSV file.

## Output

The script generates two CSV files:

1. `fl-2023-index.csv`: Contains a standardized index for both law enforcement and corrections officers consistent with indexes of officers provided for other states in the project.
2. `fl-2023-original-officers.csv`: Contains work history information data in csv format with all original data and fields provided by the state
3. `fl-2023-original-licenses.csv`: Contains certification data in csv format with all original data and fields provided by the state
4. `fl-2023-original-employment.csv`: Contains employment history data in csv format with all original data and fields provided by the state
5. `fl-2023-original-agencies.csv`: Contains employer data in csv format with all original data and fields provided by the state
6. `fl-2023-original-codes.csv`: Contains code definitions for various tables' shorthand codes
7. `fl-2023-original-complaints.csv`: Contains complaint data in csv format with all original data and fields provided by the state
8. `fl-2023-original-complaint-discipline.csv`: Contains discipline data for complaints
9. `fl-2023-original-complaint-offenses.csv`: Contains offense data for complaints
10. `fl-2023-original-complaint-status.csv`: Contains status data for complaints
11. `fl-2023-original-complaint-activity.csv`: Contains multiple activity records for each complaint
1. `fl-2023-index-enhanced.csv`: Contains a standardized index for both law enforcement and corrections officers, with two additional columns for the reason for the separation for each individual record plus a flag field for whether that individual officer's certification was ever revoked (a snapshot-in-time flag indicating that researchers should reference more detailed information about the timing and circumstance in the original license history file as well as additional public records and reporting).

The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at JohnL.Kelly@cbsnews.com.
