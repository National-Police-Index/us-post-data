# Vermont State Police Officers Certification

These data were obtained from the [Vermont Criminal Justice Council](https://vcjc.vermont.gov/about-us). It includes all certified police officers, with work history data going back into the late 1970s. The data provides officer work history, appointments, certification actions, etc.  

## Data Files

The VCJC provided three data files in response to a state public records request:

1. `Employees.csv`: Contains officer-level data such as, name gender, birth year, current certification type
2. `Employment.csv`: Contains historical agency-level data for each officer appointment, including date, rank, classification (full/part-time)
3. `Certifications.csv`: Contains historical certification status and date of certification

## R Packages Used

- tidyverse: For data manipulation and visualization
- lubridate: For handling date-time data
- pacman: For handling R packages
- janitor: For cleaning data and managing the workspace
- rio: For handling imports
- textclean: For non-ascii character issues

## Data Cleaning and Processing

The processing script performs the following operations to clean, standardize and reformat the data for further analysis:

- Renames columns for the "index" output file to be have a consistent schema across states
- Column names for all "original" output files were cleaned using janitor package to remove special character and duplicates. Otherwise, names are provided by the state.
- Formats date columns to the 'yyyy-mm-dd' format, where possible.
- Birth dates replaced with birth year. 
- Standardizes case formatting for string columns to uppercase. 
- Standardizes name columns be removing extra white space and periods.
- Removed columns with potential personal information such as drivers license, address, telephone, email, etc. 
- Some agency names in the employment file had non-ascii characters. Those were stripped out using the textclean package.
- The employment file was used to generate the work history index. However, it does not list start and end dates for each officer's appointment at an agency. Instead, the file has one action date for each type of action (appointed, de-certified, hired, promoted, resigned, retired, terminated, etc.). In order to create a work history, each officer's start date for any given agency, rank and classification was determined by using the earliest entry with one of these actions: "APPOINTED", "ELECTED", "HIRED", "PROMOTION", "RANK CHANGE". Likewise, the end date for any given agency, rank and classification was determined by using the latest entry with one of these actions: "DECEASED", "DECERT", "DISCHARGED", "OTHER SEPARATION - SEE COMMENTS", "RESIGNED", "RETIRED", "TERMINATED", "TERMINATED (NOT SPECIFIED)". 
- The employee and employment files were joined to create the index file using emp_rec_no. 
- Before exporting the index file, any row with a type_description of "TESTIING APPLICANT" was filtered out. These entries are not fully certified officers and do not have any work history data in the employment file. However, these rows were left in the original files. 

## Output

The script generates four CSV files:

1. `vt-2023-original-employees.csv`: Contains original data for law enforcement officer certification as provided by the state.
2. `vt-2023-original-employment.csv`: Contains original data for officer historical work history as provided by the state.
3. `vt-2023-original-certifications.csv`: Contains original data for officer  historical certification status as provided by the state. Caution with this file as it does not appear to be complete. For example, some officers that show as de-certified in the employment file, do not appear here. The main usefulness of this file is the date of certification. 
4. `vt-2023-index.csv`: Contains a standardized index for law enforcement officers. Each row in the index represents one officer's rank and classification at a particular agency. Some start and ends dates are missing due to the format the state provided the original data. Data cleaning mentioned above. 

The output files are stored in the `data/processed/vt` directory.

## Questions or suggestions for improvement?

Processing by Justin Mayo, Big Local News, jamayo@stanford.edu
