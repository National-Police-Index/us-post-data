# North Carolina Law Enforcement Work History and License History

These data were obtained under the state open records law from the [xxxx](https://xxxxxxx.gov/xxxxx).

The data released includes certification information and employment history for all officers certified in the state going back to the 1930s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `readxl`: For reading Excel files
- `janitor`: For cleaning data and managing the workspace
- `peopleparser`: For parsing and cleaning name data

## Data Files

The state of North Carolina provided one data file in response to a state public records request:

1. `nc_certification_lists_22.xlsx`: The state says this contains records of all certifications of North Carolina law enforcement officers.
2. `nc_officer_employment_history_2023.xlsx`: The state says this contains service / work history records of North Carolina law enforcement officers.

## Import note about the difference between this file and other state files

Because of how the work history data is released by the state of North Carolina, we could (but did not) try to discern end dates for each point in the work history because it was clear that for some records that the 'new' start date might not always perfectly align with what we would have to assume was the past end date. In many cases it would. In other cases it might not. For this particular file, we've chosen to include the action date and description of the action. This still allows for construction of a work history without making assumptions about a missing piece of information. It cannot be assumed that the next start date immediately followed/aligned with the prior end date. More reporting will be necessary by users to follow up.

## Data Cleaning and Processing

The script performs several steps to clean and process the data:

- Renamed columns for consistency.
- Converted all character columns to uppercase.
- Output processed original data to CSV files.
- Prepared an index file by renaming and modifying columns.
- Parsed and cleaned full names using `peopleparser` plus some review/manual cleanup.
- Merged parsed names back into the original data.
- Created a public officers index by merging cleaned data with the template.
- Exported the enhanced and standard work history index to CSV files.

## Output

The script generates five CSV files:

1. `nc-2023-original-officers.csv`: Contains standardized work history records data in csv format with all original data and fields provided by the state
2. `nc-2023-original-certifications.csv`: Contains standardized licensing data in csv format with all original data and fields provided by the state
3. `nc-2023-original-decertifications.csv`: Contains standardized licensing data in csv format for all officers the state reported in original data as decertified
4. `nc-2023-index.csv`: Contains a standardized index of officers' work histories in simplified format matching other states in the project.
5. `nc-2023-index-enhanced.csv`: Contains a standardized index of officers, with additional fields provided by the state that may be useful in further identifying or scrutinizing officers' histories.

The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at `JohnL.Kelly@cbsnews.com`
