# Washington State Police & Corrections Officers Certification

These data were obtained from the [Washington State Criminal Justice Training Commission](https://www.cjtc.wa.gov/certification/certification-information). It includes all certified peace and corrections officers, with work history data going back into the late 1970s. The data provides officer work history, reason for separation, certification actions, etc. It does not contain information on investigations conducted by the WSCJTC, which they make available here: https://data.wa.gov/stories/s/WSCJTC-Certification-Database/3xkp-u89m/. 

## Data Files

The WSCJTC provided two data files in response to a state public records request:

1. `Ad_Hoc_Export_2022_11_22_03_37_21_PM.csv`: Contains certification data for law enforcement officers
2. `Ad_Hoc_Export_2022_11_22_03_46_32_PM.csv`: Contains certification data for corrections officers

## R Packages Used

- tidyverse: For data manipulation and visualization
- lubridate: For handling date-time data
- pacman: For handling R packages
- janitor: For cleaning data and managing the workspace

## Data Cleaning and Processing

The processing script performs the following operations to clean, standardize and reformat the data for further analysis:

- Renames columns for the "index" output file to be have a consistent schema across states
- Column names for all "original" output files were cleaned using janitor package to remove special character and duplicates. Otherwise, names are provided by the state.
- Formats date columns to the 'yyyy-mm-dd' format, where possible.
- Birth dates replaced with birth year. 
- Standardizes case formatting for string columns to uppercase. 
- Standardizes name columns be removing extra white space and periods.
- Creates a 'full_name' field by concatenating 'first_name', 'middle_name', 'last_name', and 'suffix'
- To create a normalized work history file, the data was reformatted from "wide" to "long". For law enforcement officers, there can be up to 10 prior agencies listed in the work history. For each officer, the agency data (name, appointment, rank, start, end, status, change reason) has been formatted vertically in the index and enhanced output files. For corrections officers, there can be up to three prior agencies listed in the work history. 
- To create a normalized certification actions file, the data was reformatted from "wide" to "long" (same as the work history file). This was only possible to do for law enforcement officers, not corrections officers. Each law enforcement officer can have up to five actions listed against his/her certification. 

## Output

The script generates five CSV files:

1. `wa-2023-original-leo.csv`: Contains original data for law enforcement officer certification as provided by the state.
2. `wa-2023-original-corrections.csv`: Contains original data for corrections officer certification as provided by the state.
3. `wa-2023-index.csv`: Contains a standardized index for both law enforcement and corrections officers. Each law enforcement officer can have up to 11 agencies listed. Each corrections officer can have up to four agencies listed. Data cleaning mentioned above. 
4. `wa-2023-enhanced-work-history.csv`: Contains all of the columns from the index file, but with status and change_reason included. This allows you to see the reason an officer separated from an agency, including: retirement, resignation, terminated, etc. Data cleaning mentioned above.
5. `wa-2023-enhanced-actions.csv`: Contains action/status of certifications for law enforcement officers only. This allows you to see actions including: expired, lapsed, revoked, , reinstated, etc. There are up to five actions for each officer. 

The output files are stored in the `data/processed/wa` directory.

Reciprocal file: `Ad_Hoc_Export_2023_05_19_09_24_32_AM.csv` This reciprocal file was requested from WSCJTC separately. Reciprocity data lists police officers who came from another state and were allowed to gain certification in Washington without having to go through the full certification process. In this file, only those officers with a value in the column "Person UDF - Out of State Lateral State" were certified from outside Washington.  

## Questions or suggestions for improvement?

Processing by Justin Mayo, Big Local News, jamayo@stanford.edu
