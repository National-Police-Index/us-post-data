# Illinois Officer Data Processing

These data were obtained under the state open records law from the [Illinois Law Enforcement Training and Standards Board](https://www.ptb.illinois.gov). 

The data released includes personnel information, license and certification information, and employment history for all officers certified in the state going back to the 1960s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `janitor`: For cleaning data and managing the workspace

## Data Files

The Training and Standards Board provided five data files in response to a state public records request:

1. `Individuals.csv`: Contains personnel identifying data for law enforcement officers
2. `Certificates.csv`: Contains certification data for law enforcement officers
3. `Employments.csv`: Contains employment history data for all officers
4. `Employers.csv`: Contains employer / police agency data for the state
5. `Decertifications.csv`: Contains decertification data for officers


## Data Cleaning and Processing

- A template dataframe for the officers index is created to ensure the final dataframe has the correct structure.
- Relevant date columns are converted to the YYYY-MM-DD format to be consistent with other date fields throughout the project files from other states.
- The employment, agencies, person_data, and codes dataframes are combined on a unique ID (identified by the state of Illinois) to create a more complete work history index similar to those compiled for other states in the project.
- All the name columns are changed to title case and a full name field is created.
- Decertification offense date and decertification reason are added to the index file as a flag indicating that researchers can reference more detailed information about decertification in the decertification file. 
- Processed index plus a series of CSV files with the original data obtained from Illinois are also exported.

## Output

The script generates seven CSV files:

1. `il-2023-original-officers.csv`: Contains personal information data in csv format with all original data and fields provided by the state
2. `il-2023-original-licenses.csv`: Contains certification data in csv format with all original data and fields provided by the state
3. `il-2023-original-employment.csv`: Contains employment history data in csv format with all original data and fields provided by the state
4. `il-2023-original-agencies.csv`: Contains employer data in csv format with all original data and fields provided by the state
5. `il-2023-original-decertifications.csv`: Contains decertification data in csv format with all original data and fields provided by the state
6. `il-2023-index.csv`: Contains a standardized index of officers' work histories.
7. `il-2023-index-enhanced.csv`: Contains a standardized index of officers, with several additional fields indicating the current status of an officer's license, including if it is revoked or suspended and the reason. These final fields are snapshots in time, as of the data provided in October 2022.

The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at JohnL.Kelly@cbsnews.com.