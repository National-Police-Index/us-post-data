# Georgia POST Data Cleaning README

This README provides an overview of the data cleaning process for the Georgia POST (Peace Officer Standards and Training) dataset. You can access their website [here](https://gapost.org/). The dataset includes information on all certified peace and corrections officers, with work history data dating back to the early 1990s. While there is some data from earlier years, it is of lower quality, covering less than five hundred officers. The script processes raw data files, cleans and standardizes the information, and outputs several CSV files for further analysis.

## Libraries Used

The following libraries are used in the `clean.py` script:

- `pandas`: Used for data manipulation and analysis.
- `fuzzywuzzy`: Used for fuzzy string matching to compare and map agency names between different datasets.

## Data Sources

The script utilizes two main data sources:

1. `officer_employment-20231220144255.csv`: Contains information about the employment history of officers, including their agency, rank, start date, and end date.
2. `officer_data-20231220144255.csv`: Contains demographic data of officers, including their name, sex, race, and year of birth.

## Data Cleaning Process

The `clean.py` script performs the following data cleaning steps:

1. **Reading and Renaming Columns**: The script reads the `officer_employment-20231220144255.csv` and `officer_data-20231220144255.csv` files and renames the columns to more readable and consistent names.

2. **Splitting Names**: The script splits the full name of officers into separate columns for first name, middle name, and last name.

3. **Cleaning Personal Numbers**: The `person_nbr` column is cleaned by removing whitespace and converting it to lowercase.

4. **Cleaning Ranks**: The `ofc_rank` column is cleaned by removing leading/trailing whitespace, replacing abbreviations with full words, and standardizing rank names. Some specific notes regarding rank cleaning:
  - The array has values for both "peace officer" and "police officer". It may be necessary to decide which one should be used consistently.
  - "Certified corrections officer" and "sworn corrections officer" are currently treated as distinct values in the rank column.
  - Reserve officer ranks were simplified by removing "officer" when the rank contained a higher rank. For example, "reserve ofc - lt (peace ofc)" was changed to "reserve lieutenant (peace officer)".
  - The focus of rank cleaning was on expanding contracted names rather than inferring anything not contained within the data.

5. **Cleaning Agency Names**: The `agcy_name` column is cleaned by removing prefixes, suffixes, and replacing abbreviations with full words. Similar to rank cleaning, the focus was on expanding names rather than making inferences.

6. **Merging Datasets**: The script merges the cleaned employment history dataset with the demographic dataset based on the `person_nbr` column.

7. **Extracting Agency UIDs**: The script extracts the agency UIDs from the cleaned agency names.

## Agency Name Mapping

One important aspect of the data cleaning process is ensuring consistency in agency names across different datasets. The script uses the `agency_data-20231220144255.csv` file as the ground truth data for agency names.

To map the agency names from the `employment-history.csv` file to the ground truth data, the script employs the `fuzzywuzzy` library for fuzzy string matching. The `get_unique_fuzzy_matches` function is used to find the best matches between agency names based on a threshold score.

The script compares the agency names from the employment history dataset (`agcy_name_x`) with the ground truth agency names (`agcy_name_y`) and calculates a fuzzy match score. The unique fuzzy matches above a specified threshold are stored in a separate dataframe for further analysis.

Finally, the script merges the cleaned employment history dataset with the ground truth agency names based on the agency UIDs, ensuring that the agency names are consistent across the merged dataset.

It's important to note that while both datasets were nearly analogous, there was a discrepancy in 11 rows between the datasets, as observed from the `get_unique_fuzzy_matches` function. The chosen rows were derived from the `agency_data-20231220144255.csv` dataset.

## Non-state Specific Cleaning Steps

1. Renames columns for the "index" output file to be have a consistent schema across states
2. Formats date columns to the 'yyyy-mm-dd' format, where possible.
3. Standardizes case formatting for string columns to uppercase.
4. Standardizes name columns be removing extra white space and periods.
5. Creates a 'full_name' field by concatenating 'first_name', 'middle_name', and 'last_name'.

## Output 

The script generates four CSV files:

1. `ga-2024-original-leo.csv`: Contains the original certification data with cleaned column names for law enforcement officers and corrections officers as provided by the state.

2. `ga-2024-original-leo-demographics.csv`: Contains the original demographic data with cleaned column names for law enforcement officers and corrections officers as provided by the state.

3. `ga-2024-index.csv`: Contains a standardized index for both law enforcement and corrections officers. Each officer can be associated with a single department multiple times within one employment stint. Common reasons for being associated with a single department more than once include changes in rank.

4. `ga-2024-enhanced-work-history.csv`: Contains all the columns from the index file, with the addition of status and change_reason. This allows you to see the reasons an officer separated from an agency, including retirement, resignation, termination, etc.

## Additional information
The input directory contains `ga-2024-reciprocity.csv`. This table contains information on officers who joined the Georgia POST agency after being affiliated with a POST agency in a different state. 

## Questions or suggestions for improvement?

Processing by Ayyub Ibrahim, Louisiana Law Enforcement Accountability Database ayyubi@ip-no.org
