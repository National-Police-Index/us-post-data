# Arizona Officer History Data Processing

These data were obtained under the state open records law from the [Arizona Peace Officer Standards and Training Board](https://post.az.gov). 

The data released includes personnel and employment history for all officers certified in the state going back to the 1950s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `readxl`: For reading Excel files
- `janitor`: For cleaning data and managing the workspace

## Data Files

The APOST provided one Excel data file in response to a state public records request:

1. `006_PR_2023_0413_AllOfficers_w_AppointmentsAndFinalActions.xlsx`: Contains certification and work history data for law enforcement officers in Arizona.

## Data Cleaning and Processing

The data cleaning process involves several steps:

- Importing the Excel file and cleaning up the column names for consistency with the index files created for other states in the project. 
- Including splitting the full name into first name, middle name, last name, and suffix. Cleaning up the suffixes. Reassembling the full name.
- In a few cases, manual corrections were made to the names suffixes after additional reporting and research to confirm the names were correct.

## Output

The script generates three CSV files:

1. `az-2023-original-employment.csv`: Contains work history information data in csv format with all original data and fields provided by the state.
2. `az-2023-index-enhanced.csv`: Contains a standardized index of officers, with additional fields indicating the current status of the officers' license, including if it is revoked or suspended. This certificate status field is a  snapshot in time from when the state released the data.
3. `az-2023-index.csv`: Contains a standardized index of officers.

The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at JohnL.Kelly@cbsnews.com.

