# Alaska Officer Data Processing

These data were obtained under the state open records law from the [Alaska Department of Public Safety's Police Standards Council](https://dps.alaska.gov/APSC/Home). 

The data released includes personnel information, license and certification information, and employment history for all officers certified in the state. The employment change data only tracks the changes since 2017. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `janitor`: For cleaning data and managing the workspace

## Data Files

The Training and Standards Board provided three data files in response to a state public records request:

1. `APSC Current Officers.csv`: Contains personnel identifying data for law enforcement officers with active certifications/employment.
2. `APSC Certification 2017.csv`: Contains certification data for all law enforcement officers, dating back to 2017.
3. `APSC Employment Status Changes since 2017.csv`: Contains employment history data for all officers, but only the changes since 2017.


## Data Cleaning and Processing

- Column Name Standardization: Standardizes column names across dataframes for consistency.
- Identifies officers in the person data not present in the employment change file and creates a more comprehensive roster, although the work history is limited to changes since 2017, it is possible some officers are missing. We are following up with the state to get additional data to make sure the index is as complete as possible.
- Generates a `full_name` column by combining `first_name` and `last_name`.
- License Status Identification: Creates dataframes to identify licenses that are revoked or surrendered.
- Merge with Template Index: Merges cleaned data with the template index and sorts by officer number, start date, and full name to be consistent with other states' data in this project.
- Adds a flag for Revoked or Surrendered Licenses: Adds flags to the enhanced index to indicate whether an officer has ever had their license revoked or surrendered. This is a snapshot in time from the release of the data in January 2023. It also flags any peace officer license the officer may have that's been revoked. It is a flag to identify persons that reporters should further research in the raw data files or via other reporting/records.

## Output

The script generates seven CSV files:

1. `ak-2023-original-officers.csv`: Contains personal information data in csv format with all original data and fields provided by the state
2. `ak-2023-original-licenses.csv`: Contains certification data in csv format with all original data and fields provided by the state
3. `ak-2023-original-employment.csv`: Contains employment history data in csv format with all original data and fields provided by the state
4. `il-2023-index.csv`: Contains a standardized index of officers' work histories.
5. `il-2023-index-enhanced.csv`: Contains a standardized index of officers, with several additional fields indicating the current employment status with the agency in question as well as whether the officer has ever had their license revoked or if they have ever surrendered a license. These final fields are snapshots in time, as of the data provided in January 2023.

The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at JohnL.Kelly@cbsnews.com.