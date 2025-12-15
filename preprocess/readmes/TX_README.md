# Texas Law Enforcement Work History and License History

These data were obtained under the state open records law from the [Texas Commission on Law Enforcement](https://www.tcole.texas.gov/content/public-information-act). 

The data released includes certification information and employment history for all officers certified in the state going back to the 1930s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference.


## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `readxl`: For reading Excel files
- `janitor`: For cleaning data and managing the workspace

## Data Files

The TCOLE provided two data files in response to a state public records request:

1. `tx_servicerecords_03192024.xlsx`: Contains service / work history records of officers
2. `tx_licenses_03192024.xlsx`: Contains certification / licensing information of officers

## Data Cleaning and Processing

The script performs several steps to clean and process the data:

- Imports the Excel files and assigns appropriate data types to the columns
- Renames columns for consistency with a standardized data dictionary we're following across states, where possible
- Formats date columns to the 'yyyy-mm-dd' format
- Standardizes case formatting for the 'first_name', 'middle_name', 'last_name', and 'suffix' fields
- Handles missing values in the 'middle_name' and 'suffix' fields
- Standardizes and cleans the 'suffix' field to all variations of suffixes where we can be certain the string is a suffix. Raw values are kept in the raw csv files for officers and licenses for reference.
- Creates a 'full_name' field by concatenating 'first_name', 'middle_name', 'last_name', and 'suffix'
- Removes records with a type including the word 'telecommunications' to remove non officer or jailer personnel from the processed data; those individuals remain in the csv versions of the original files for reference.
- Creates a flag for whether an officer's license was ever revoked or surrendered, based on the license history file, as a flag for further investigation via the original license history file. This process was used because some officers' licenses are revoked or surrendered and then reinstated. It's added to the work history file only as a flag to investigate further; it does not indicate the revocation or surrender happened during the particular period in time covered by the individual record in the work history file.

## Output

The script generates three CSV files:

1. `tx-2023-original-persons.csv`: Contains cleaned service records data in csv format with all original data and fields provided by the state
2. `tx-2023-original-licenses.csv`: Contains cleaned licensing data in csv format with all original data and fields provided by the state
3. `tx-2023-index.csv`: Contains a standardized index of officers' work histories matching other states in the project.
4. `tx-2023-index-enhanced.csv`: Contains a standardized index of officers, with additional fields indicating whether an officer's license has ever been revoked or surrendered as an indicator to further investigate the officer's history in the original license history file.


The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at `JohnL.Kelly@cbsnews.com`
