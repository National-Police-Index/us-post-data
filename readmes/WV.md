# West Virginia POST Data Cleaning README

This README provides an overview of the data cleaning process for the West Virginia POST (Peace Officer Standards and Training) dataset. The dataset includes information on all certified peace and corrections officers, with work history data dating back to the mid-1980s. The script processes raw data files, cleans and standardizes the information, and outputs several CSV files for further analysis.

## Libraries Used

The following libraries are used in the script:

- `pandas`: Used for data manipulation and analysis.

## Data Sources

The script utilizes the following main data sources:

1. `active-inactive-wv-le--20231220144255.csv`: Contains the actual data, including employment history and demographic details of officers.

## Data Cleaning Process

The script performs the following data cleaning steps:

1. **Reading and Renaming Columns**: The script reads the CSV file and renames specific columns to standardize the dataset.
   
2. **Transforming Columns**: The script identifies columns that remain constant across employments and those that vary for each employment stint. It then melts and pivots the DataFrame to arrange the data accordingly.

3. **Arranging New DataFrame**: The script renames columns for clarity and drops unnecessary columns.

4. **Cleaning Separation Reason**: The script standardizes the format of the separation reasons for officers.

5. **Dropping Fire Department Rows**: The script filters out rows associated with fire departments.

6. **Uppercasing Columns**: The script converts all text columns to uppercase.

7. **Setting Full Name Column**: The script creates a 'full_name' field by concatenating 'first_name' and 'last_name'.

## Non-state Specific Cleaning Steps

1. Renames columns for the "index" output file to have a consistent schema across states.
2. Formats date columns to the 'yyyy-mm-dd' format, where possible.
3. Standardizes case formatting for string columns to uppercase.
4. Standardizes name columns by removing extra white space and periods.
5. Creates a 'full_name' field by concatenating 'first_name' and 'last_name'.

## Output

The script generates three CSV files:

1. `wv-2024-original-leo.csv`: Contains the original certification data with cleaned column names for law enforcement officers and corrections officers.

2. `wv-2024-enhanced-work-history.csv`: Contains the cleaned and enhanced work history data, including status and change reasons. This allows you to see the reason an officer separated from an agency, such as retirement, resignation, or termination.

3. `wv-2024-index.csv`: Contains a standardized index for both law enforcement and corrections officers. Each officer can be associated with a single department multiple times within one employment stint. Common reasons for multiple associations with a single department include changes in rank.

## Additional information
The input directory contains `wv-2024-reciprocity.csv`. This table contains information on officers who joined the Georgia POST agency after being affiliated with a POST agency in a different state. 

## Questions or Suggestions for Improvement?

Processing by Ayyub Ibrahim, Louisiana Law Enforcement Accountability Database ayyubi@ip-no.org
