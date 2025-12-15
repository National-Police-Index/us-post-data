# Utah Police & Corrections Officers Certification

These data were obtained from the [Utah Peace Officer Standards & Training](https://post.utah.gov/). It includes all certified peace and corrections officers, with work history data going back into the 1970s. The data provides officer work history, reason for separation, certification status, etc. The POST data in Utah has never been released before. The data was obtained through legal action taken by [The Utah Investigative Journalism Project](https://www.utahinvestigative.org/) and supported by the law firm [Parr Brown Gee & Loveless](https://parrbrown.com/services/the-utah-freedom-of-information-hotline/). 

## Data Files

Utah POST provided three data files in response to a state public records request:

1. `Report SLCPD Only 7-2-2024 Final (2).xlsx`: Contains certification data for law enforcement and corrections officers from Salt Lake City PD 
2. `Report Minus SLCPD 7-2-2024 Final (2).xlsx`: Contains certification data for law enforcement and corrections officers from all other departments
3. `Certification Report 4_14_23 (1).csv`: Contains names of officers who have lost their certification

## R Packages Used

- tidyverse: For data manipulation and visualization
- lubridate: For handling date-time data
- pacman: For handling R packages
- janitor: For cleaning data and managing the workspace
- rio: For importing/exporting data

## Data Cleaning and Processing

The processing script performs the following operations to clean, standardize and reformat the data for further analysis:

- Renames columns for the "index" output file to be have a consistent schema across states
- Column names for all "original" output files were cleaned using janitor package to remove special character and duplicates. Otherwise, names are provided by the state.
- Formats date columns to the 'yyyy-mm-dd' format, where possible.
- Standardizes case formatting for string columns to uppercase. 
- Standardizes name columns be removing extra white space and periods.
- To create a normalized work history file, the data was reformatted from "wide" to "long". For law enforcement officers, there can be up to 13 prior agencies listed in the work history. For each officer, the agency data (name, appointment, rank, start, end, status, change reason) has been formatted vertically in the index file.  

## Output

The script generates three CSV files:

1. `ut-2024-original-certification.csv`: Contains original data for law enforcement and corrections officers certification as provided by the state.
2. `ut-2024-original-actions.csv`: Contains original data for officers who had certifications relinquished, revoked or suspended as provided by the state.
3. `ut-2024-index.csv`: Contains a standardized index for both law enforcement and corrections officers. Each officer can have up to 13 agencies listed. Data cleaning mentioned above. 

The output files are stored in the `data/processed/ut` directory.

## Questions or suggestions for improvement?

Processing by Justin Mayo, Big Local News, jamayo@stanford.edu
