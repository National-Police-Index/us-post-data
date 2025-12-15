# New Jersey Officer Data Processing

These data were obtained under the state open records law from the [New Jersey Police Training Commission](https://www.njoag.gov/about/divisions-and-offices/division-of-criminal-justice-home/police-training-commission/). 

The data released includes personnel information and employment history for all officers certified in the state going back to the 1940s. Our processing performs several operations to clean, standardize, and reformat the data into a work history index file that is consistent with other states' data obtained as part of this tracking project. The original data is preserved in CSV format for reference. The state did not provide a unique identifier number, end dates for work histories, and other key elements provided by other states. Where that information was not provided, columns are left blank in the standardized index.

## R Packages Used

- `tidyverse`: For data manipulation and visualization
- `lubridate`: For handling date-time data
- `stringi`: For string manipulation
- `janitor`: For cleaning data and managing the workspace

## Data Files

The Police Training Commission provided one data files in response to a state public records request:

1. `nj_response_opra_request.xlsx`: Contains certification and work history for law enforcement officers

## Data Cleaning and Processing

The data cleaning process involves several steps:

- Creating a new column for the year of birth; calculating the age of each officer based on their date of birth and processing date of 6-1-2024.
- Reformatting the full name into first name, middle name, last name, and suffix and full name field in the format consistent with other states' data.
- Cleaning up the suffixes.
- In the start_date field there were several records with the date 1/1/1900. These records were removed. 
- The same was done for years of birth of 1900.

## Output

The script generates three CSV files:

1. `nj-2023-original-employment.csv`: Contains work history information data in csv format with all original data and fields provided by the state
2. `nj-2023-index.csv`: Contains a standardized index of officers' work histories consistent with the files provided for other states.
3. `nj-2023-index-enhanced.csv`: Contains a standardized index of officers, with one additional field indicating the reason for the change of the officer's status.


The output files are stored in the `data/processed/` directory.

## Questions or suggestions for improvement?

Processing by John Kelly, CBS News at JohnL.Kelly@cbsnews.com.
