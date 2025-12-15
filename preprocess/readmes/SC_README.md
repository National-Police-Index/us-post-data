# South Carolina Officer Data Processing

These data were obtained under the state open records law from the [South Carolina Criminal Justice Academy](https://sccja.sc.gov).

The data released includes personnel information, certification information, and employment history for all officers certified in the state going back to the early 1950s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `readxl`: For reading Excel files
- `janitor`: For cleaning data and managing the workspace

## Data Files

The script processes three Excel files provided by the state of South Carolina:

1. `Export_Officer_Info_2023_07_24.xlsx`: Contains personal information of officers
2. `Export_Certification_2023_07_24.xlsx`: Contains certification information of officers
3. `Export_Employment_Officer_2023_07_24.xlsx`: Contains employment history of officers

## Data Cleaning and Processing

The script performs several steps to clean and process the data:

- Imports the Excel files and assigns appropriate data types to the columns
- Renames columns for consistency with a standardized data dictionary we're using across states, where possible
- Formats date columns to the 'yyyy-mm-dd' format
- Standardizes case formatting for the 'first_name', 'middle_name', 'last_name', and 'suffix' fields
- Handles missing values in the 'middle_name' and 'suffix' fields
- Standardizes and cleans the 'suffix' field to all variations of suffixes where we can be certain the string is a suffix. Raw values are kept in the raw csv files for officers and licenses for reference.
- Creates a 'full_name' field by concatenating 'first_name', 'middle_name', 'last_name', and 'suffix'
- South Carolina's data allowed adding of fields indicating the current status of an officer's license, including if it is revoked or suspended. These fields are snapshots in time, as of the data provided in July 2023.
- There are records in the work history that did not have a correlating record in the officer or license data. We are following up with South Carolina to determine why, but we've provided this data in each case available.

## Output

The script generates the following CSV files:

1. `sc-2023-original-officers.csv`: Contains personal information data in csv format with all original data and fields provided by the state
2. `sc-2023-original-licenses.csv`: Contains certification data in csv format with all original data and fields provided by the state
3. `sc-2023-original-employment.csv`: Contains employment history data in csv format with all original data and fields provided by the state
4. `sc-2023-index.csv`: Contains a standardized index of officers, with additional fields indicating the current status of an officer's license.
5. `sc-2023-index-enhance.csv`: Contains the standardized index of officers, with additional fields indicating the current status of an officer's license, including key dates and if it is revoked or suspended. These fields are snapshots in time, as of the data provided in July 2023.


The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at JohnL.Kelly@cbsnews.com.
