# Nebraska Police Officers Certification Data

These data were obtained from the [Nebraska Crime Commission](https://ncc.nebraska.gov). It includes all certified peace and corrections officers with their earliest hire date and agencies they've worked for in the state. It also contains the status of the officers' certification, including whether it has been revoked. The data importantly does not provide a detailed work history.

## Data Files

The Nebraska Crime Commission provided one data file about officers' work histories in response to a state public records request:

1. `Ad_Hoc_Export_2022_11_22_03_37_21_PM.csv`: Contains certification data for law enforcement officers

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `readxl`: For reading Excel files
- `janitor`: For cleaning data and managing the workspace

## Data Cleaning and Processing

The processing script performs the following operations to clean, standardize and reformat the data for further analysis:

-  The workspace was cleared and the root and output directories were defined.
- The path to the source Excel file and the output CSV files were defined.
- A template dataframe for the officers index was created to ensure the final dataframe has the correct structure.
- The Excel file was imported and the column names were cleaned using the janitor package.
- The original officers file was exported as a CSV.
- Unnecessary columns were filtered out from the dataframe.
- The columns were renamed to be consistent with the template.
- The type column was filled with "Police Officer" as the file contains only police officers.
- The date columns were cleaned and formatted.
- The "@" character in the agency list field was replaced with ", ".
- A suffix field was created that extracts the suffix from the last name field. If there was a suffix in the last name or first name field, it was removed from that field and appended to the suffix field.
- The full name was reassembled from the first_name, middle_name, last_name, and suffix fields.
- The cleaned data was merged into the index template.
- The final cleaned data was exported as a CSV.

## Output

The script generates five CSV files:

1. `ne-2023-original-employment.csv`: Contains original data for law enforcement officer certification as provided by the state.
2. `ne-2023-index.csv`: Contains a standardized index for both law enforcement and corrections officers. The Nebraska file is different from other states in the project because of the format the state shared its data, which does not provide start and end dates for each period or agency served. We've shared the data that is nearest to the format of other states in the project, exactly as state shared.

The output files are stored in the `data/processed/` directory.


## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at JohnL.Kelly@cbsnews.com.
