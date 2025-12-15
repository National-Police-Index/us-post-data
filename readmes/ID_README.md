# Idaho State Police Officers Certification

## Data Files

I downloaded data from the shared dropbox folder on May 25, 2024. The two files
I used:

- **police-certification/ID/2023-5-12/Employee_Public_Record_Report_5-23.xlsx**:
  renamed to **input/id-2023-employee-public-record-report-5-23.xlsx**
- **police-certification/ID/Public Records Request Idaho Officers Decertified
  dated 4 20 17.xls**: renamed to
  **input/id-2017-decertified-officers-20170420.xls**

For reference, the sha1 hashes of the two files:

```
$ date +"%Y-%m-%d %H:%M %p"
2024-05-26 08:54 AM

$ find input -type f | xargs sha1sum
a3be312e02caa09b4b2e32ab4a9c06b97e3594a3  input/id-2017-decertified-officers-20170420.xls
162ab1f6de6d5494214894229dc61e2d3feb75e5  input/id-2023-employee-public-record-report-5-23.xlsx
```

`src/xl2csv.py` takes an Excel file and outputs the same file as a CSV with
cleaned column names.

`src/clean-officers.py` and `src/clean-licensing.py` both take two command-line
arguments, the name of the input original CSV file and the name of the output
to create:

```bash
$ python src/clean-officers.py INPUTFILE OUTPUTFILE
$ python src/clean-licensing.py INPUTFILE OUTPUTFILE
```

## Python Packages Used

- pandas: For data manipulation
- openpyxl: to read Excel files

## Data Cleaning and Processing

## `index`

These are the required fields for the main index file. This script does not
output all of the required fields, below is the list of fields and explanations
for those that do not appear in the ID index:

- `person_nbr`: There is no unique identifier for individuals provided in the
  data, and I did not do any kind of entity resolution that could provide such
  an id. So there is no `person_nbr` column in the data.
- `full_name`: concatenation of `first_name` and `last_name`
- `last_name`: uppercased, input column was `Last Name`
- `first_name`: uppercased, input column was `First Name`
- `middle_name`: was not provided, so not output
- `middle_initial`: was not provided, so not output
- `suffix`: was not provided, so not output
- `birth_year`: was not provided, so not output
- `age`: was not provided, so not output
- `agcy_name`: uppercased, input column was `Agency`
- `type`: uppercased, input column was `Employment Classification`
- `rank`: was not provided, so not output
- `start_date`: converted to string in YYYY-MM-DD format
- `end_date`: converted to string in YYYY-MM-DD format

For both `start_date` and `end_date`, there were several records dated either
1900-01-01 or 1901-01-01, the script replaces these with missing values.

## licenses

- `full_name`: concatenation of `first_name` and `last_name`
- `last_name`: uppercased, input column was `Last Name`
- `first_name`: uppercased, input column was `First Name`
- `certification`: uppercased, input column was `Certification`
- `certification_classification`: uppercased, input column was `Certification
  Classification`
- `certification_level`: uppercased, input column was `Level`
- `issue_date`: converted to string in YYYY-MM-DD format, input column was
  `Issue Date`
- `status`: uppercased, input column was `Status`
- `status_date`: converted to string in YYYY-MM-DD format, input column was
  `Status Date`

## Questions or suggestions for improvement?

Processing by Tarak Shah, Human Rights Data Analysis Group (HRDAG) at
tarak@hrdag.org
