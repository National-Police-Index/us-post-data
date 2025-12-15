# Oregon State Police Officers Certification

These data were obtained from the [Oregon Department of Public Safety Standards & Training](https://www.oregon.gov/dpsst/cj/pages/default.aspx). It includes certified police officers, corrections officers, parole/probation officers with work history data going back into the 1970s. The data provides officer work history, certification actions and training info.  

## Data Files

The DPSST provided eight data files in response to a state public records request:

1. `Employees.csv`: Contains officer-level data including, name, gender, race, age (as of Sept 2022).
2. `Employees_archive.csv`: Same as above with archived data.
3. `Employment.csv`: Contains historical agency-level data for each officer appointment, including date, action, rank.
4. `Employment_archive.csv`: Same as above with archived data.
5. `Certifications.csv`: Contains historical certification level, status, status date and date of certification.
6. `Certifications_archive.csv`: Same as above with archived data.
7. `Training.csv`: Contains detailed training history for each officer including training date, course/class description, status (pass/fail). 
8. `Training_archive.csv`: Same as above with archived data.

## R Packages Used

- tidyverse: For data manipulation and visualization
- lubridate: For handling date-time data
- pacman: For handling R packages
- janitor: For cleaning data and managing the workspace
- rio: For handling imports

## Data Cleaning and Processing

The processing script performs the following operations to clean, standardize and reformat the data for further analysis:

- Combines all "archive" files with the corresponding current file (i.e. Employees.csv combined with Employees_archive.csv).
- Renames columns for the "index" output file to be have a consistent schema across states
- Column names for all "original" output files were cleaned using janitor package to remove special character and duplicates. Otherwise, names are provided by the state.
- Combines first, middle, last, suffix name columns to create full name. 
- Formats date columns to the 'yyyy-mm-dd' format, where possible.
- Standardizes case formatting for string columns to uppercase. 
- Standardizes name columns be removing extra white space and periods.
- Removed columns with potential personal information such as drivers license, address, telephone, email, etc. 
- The employment file was used to generate the work history index. However, it does not list start and end dates for each officer's appointment at an agency. Instead, the file has one action date for each type of action (de-certified, hired, promoted, resigned, retired, terminated, etc.). In order to create a work history, each officer's start date for any given agency and rank was determined by using the earliest entry with one of these actions: "ACTIVE", "CERTIFICATION REINSTATED", "HIRED", "PROMOTION", "RECLASSIFICATION", "REINSTATED", "RETURN FROM LEAVE OF ABSENCE", "RETURN FROM MILITARY LOA", "TRANSFERRED". Likewise, the end date for any given agency and rank was determined by using the latest entry with one of these actions: "CERTIFICATION DENIED", "CERTIFICATION REVOKED", "CERTIFICATION SUSPENDED", "DECEASED", "DEMOTION", "DEMOTION-VOLUNTARY", "DISCHARGED", "DOC TRANSFER", "INACTIVE", "LAYOFF", "LEAVE OF ABSENCE", "LEAVE-NON CERTIFIED", "MILITARY LEAVE OF ABSENCE", "PROBATIONARY DISCHARGE", "RESIGNED", "RESIGNED-OTHER", "RETIRED", "RETIRED-DISABILITY", "SUSPENSION", "TERMINATED". 
- The employee and employment files were joined to create the index file using emp_rec_no. 
- Before exporting the index file, any row with an agency of "DPSST USE ONLY" was filtered out. These entries appear to indicate police academy training and not actual agency work history. However, these rows were left in the original files. 

## Output

The script generates five CSV files:

1. `or-2023-original-employees.csv`: Contains original data for law enforcement officer certification as provided by the state.
2. `or-2023-original-employment.csv`: Contains original data for officer historical work history as provided by the state.
3. `or-2023-original-certifications.csv`: Contains original data for officer  historical certification status as provided by the state. Caution with this file as it does not appear to be complete for some certification types. For example, emergency medical dispatchers and telecommunicators only show up in this file if their certification was denied or revoked. 
4. `or-2023-original-training.csv`: Contains original data for officer historical training courses and classes. WARNING: this file has nearly 3.5 million records and can not be opened in Excel.  
5. `or-2023-index.csv`: Contains a standardized index for law enforcement officers. Each row in the index represents one officer's rank at a particular agency. Some start and ends dates are missing due to the format the state provided the original data. The certification type (police, corrections, etc.) was not available. Data cleaning mentioned above. 

The output files are stored in the `data/processed/or` directory.

Documentation file: `RecDefPerm_1200.xlsx` This spreadsheet was provided by DPSST. It appears to be a full data dictionary for their certification and training system. It does not match the original data files provided here but could provide some context. It is included as a reference only.

Reciprocal file: `WaiversTrackingLog.xlsx` This spreadsheet was requested from DPSST separately. Reciprocity data lists police officers who came from another state and were allowed to gain certification in Oregon without having to go through the full certification process. 

## Questions or suggestions for improvement?

Processing by Justin Mayo, Big Local News, jamayo@stanford.edu
