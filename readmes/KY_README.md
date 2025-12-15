# Kentucky Law Enforcement Work History and License History

These data were obtained under the state open records law from the [Kentucky Law Enforcement Council](https://justice.ky.gov/Boards-Commissions/KLEC/Pages/default.aspx). 

The data released includes certification information and employment history for all officers certified in the state going back to the 1930s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.


## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `readxl`: For reading Excel files
- `janitor`: For cleaning data and managing the workspace
- `peopleparser`: For parsing and cleaning name data

## Data Files

The state of Kentucky provided one data file in response to a state public records request:

1. `Certified_Employed_POPS_-_All_Cert_Statuses_Employment_History_Training_History.xlsx`: Contains service / work history records of Kentucky law enforcement officers.

## Data Cleaning and Processing

The script performs several steps to clean and process the data:

- Creates a template dataframe for the officers index
- Import and rename columns for consistency with template for other states
- Convert all character columns to upper case for consistency with data for other states
- Rename columns for index preparation for consistency
- Parse full names, split into components, and concatenate into a new full_name field using the peopleparser library. Post-parsing manual validation to ensure proper, consistent handling of unusual name formats.
- Convert and consistently format all dates and converts year of birth to numeric
- Merge cleaned data into the work history index file and sort by person_nbr and start_date
- Remove extra columns for standard work history index to be consistent with other states

## Output

The script generates four CSV files:

1. `ky-2023-original-persons.csv`: Contains standardized work history records data in csv format with all original data and fields provided by the state
2. `ky-2023-original-licenses.csv`: Contains standardized licensing data in csv format with all original data and fields provided by the state
3. `ky-2023-index.csv`: Contains a standardized index of officers' work histories in simplified format matching other states in the project.
4. `ky-2023-index-enhanced.csv`: Contains a standardized index of officers, with additional fields provided by the state that may be useful in further identifying or scrutinizing officers' histories.


The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at `JohnL.Kelly@cbsnews.com`
