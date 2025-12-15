# Wyoming Officer Data Processing

These data were obtained under the state open records law from the [Wyoming Peace Officer Standards and Training Board](https://post.wyo.gov). 

The data released includes personnel information, license and certification information, and employment history for all officers certified in the state going back to the 1960s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `janitor`: For cleaning data and managing the workspace

## Data Files

The state board provided five data files in response to a state public records request:

1. `Muckrock_FOI_request_6-16-23.csv`: Contains personnel identifying data for law enforcement officers who are active including work history changes
2. `Muckrock_2nd_request.csv`: Contains certification data for no longer active law enforcement officers' work histories
3. `WY_certification_revocations_2000_2-22-23.csv`: Contains records of all officers whose law enforcement certification had been revoked by February 2023

## Data Cleaning and Processing

- A template dataframe for the officers index is created to ensure the final dataframe has the correct structure.
- Relevant date columns are converted to the YYYY-MM-DD format to be consistent with other date fields throughout the project files from other states.
- The two officer files are transformed from a single record per officer to a single record for each work period / agency and then combined into a single file of active and inactive officers
- All the name columns are changed to upper case and a full name field is created.
- Processed index plus a series of CSV files with the original data obtained from the state are also exported.

## Output

The script generates four CSV files:

1. `wy-2023-original-employment-change.csv`: Contains personal information data in csv format with all original data and fields provided by the state
2. `wy-2000-2023-revocations.csv`: Contains decertification data in csv format with all original data and fields as provided by the state for the period from 2000 through early 2023
6. `wy-2023-index.csv`: Contains a standardized index of officers' work histories.
7. `wy-2023-index-enhanced.csv`: Contains a standardized index of officers, with several additional fields indicating whether the officer was full time or part time, status as active or not, and the type of agency.

The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at JohnL.Kelly@cbsnews.com.