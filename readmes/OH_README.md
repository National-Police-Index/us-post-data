# Ohio Officer History Data Processing

These data were obtained under the state open records law from the [Ogio Peace Officer Training Commission](https://www.ohioattorneygeneral.gov/Law-Enforcement/Ohio-Peace-Officer-Training-Academy/Ohio-Peace-Officer-Training-Commission). 

The data released includes personnel and employment history for all officers certified in the state going back to the 1950s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `readxl`: For reading Excel files
- `janitor`: For cleaning data and managing the workspace

## Data Files

The Ohio commission provided two Excel data files in response to a state public records request:

1. `Decertified_and_Voluntary_Surrender_Officers_4-3-2023_3-31-31_PM`: Contains decertified and surrendered license data for law enforcement officers in Ohio.
2. `Muckrock_PRR12536.xlsx`: Contains employment history data for law enforcement officers in Ohio.

## Data Cleaning and Processing

The data cleaning process involves several steps:

- Importing the Excel files and cleaning up the column names for consistency with the index files created for other states in the project.
- Including splitting the full name into first name, middle name, last name, and suffix. Cleaning up the suffixes. Reassembling the full name in the order for standardization across all states' index files.
- In a few cases, dates that 

## Output

The script generates two CSV files:

1. `oh-2023-original-employment.csv`: Contains work history information data in csv format with most original data and fields provided by the state. The original file contained a full date of birth which we've replaced with year of birth and an age calculated from the date these files were processed, 2024-06-08. There are some dates that appear to be incorrect (e.g., dates of birth that indicate a minor or dates that are impossible for officers' service), but the original data is preserved in this file as it came from the state.
2. `oh-2023-original-officers.csv`: Contains personnel information in csv format with most original data and fields provided by the state, including a flag for whether an officer's certification has ever been revoked. The original file contained a full date of birth which we've replaced with year of birth and an age calculated from the date these files were processed, 2024-06-08.
3. `oh-2023-original-decertified.csv`: Contains all fields provided by the state for officers that Ohio says are decertified or have voluntarily surrendered their peace officer certification.
4. `az-2023-index.csv`: Contains a standardized index of officers, with start and end dates. Most dates are preserved as they were provided by the state.

The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at `JohnL.Kelly@cbsnews.com`.

