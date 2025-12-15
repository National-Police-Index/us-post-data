# Tennessee POST Data Cleaning README

This README provides an overview of the data cleaning process for the Tennessee POST (Peace Officer Standards and Training) dataset. The dataset includes information on all certified peace and corrections officers, with work history data dating back to the mid 1980s. While there is some data from earlier years, it is of lower quality, covering less than five hundred officers. The script processes raw data files, cleans and standardizes the information, and outputs several CSV files for further analysis.

## Libraries Used

The following libraries are used in the script:

- `pandas`: Used for data manipulation and analysis.

## Data Sources

The script utilizes two main data sources:

1. `tn_ad-hoc-export-2023-filtered-20231220144255.csv`: Contains header information to determine the columns to be read from the Excel file.
2. `tn_ad-hoc-export-2023-filtered-20231220144255.xlsx`: Contains the actual data, including employment history and demographic details of officers.

## Data Cleaning Process

The script performs the following data cleaning steps:

1. **Reading and Renaming Columns**: The script reads the CSV file to get the column names and reads the first 126 columns from the Excel file. These columns are those associated with employment history data. 

2. **Filtering Rows**: The script filters out rows where the "Person PSID"/UID column is empty.

3. **Splitting Rows by Employment Stints**: The script splits a single row into individual employment stints based on the employment columns (up to 11 stints/rows per office). 

4. **Cleaning UIDs**: The "person_nbr" column is cleaned by removing any leading "**".

## Non-state Specific Cleaning Steps

1. Renames columns for the "index" output file to be have a consistent schema across states
2. Formats date columns to the 'yyyy-mm-dd' format, where possible.
3. Standardizes case formatting for string columns to uppercase.
5. Standardizes name columns be removing extra white space and periods.
6. Creates a 'full_name' field by concatenating 'first_name', 'middle_name', and 'last_name'.


## Output

The script generates three CSV files:

1. `tn-2024-original-leo.csv`: Contains the original certification data with cleaned column names for law enforcement officers and corrections officers.

2. `tn-2024-enhanced-work-history.csv`: Contains the cleaned and enhanced work history data, including status and change reasons. This allows you to see the reason an officer separated from an agency, such as retirement, resignation, or termination.

3. `tn-2024-index.csv`: Contains a standardized index for both law enforcement and corrections officers. Each officer can be associated with a single department multiple times within one employment stint. Common reasons for multiple associations with a single department include changes in rank.

## Additional information
The input directory contains `tn-2024-reciprocity.csv`. This table contains information on officers who joined the Georgia POST agency after being affiliated with a POST agency in a different state. 

## Questions or suggestions for improvement?

Processing by Ayyub Ibrahim, Louisiana Law Enforcement Accountability Database ayyubi@ip-no.org