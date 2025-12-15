# California State Police Officers Certification

## Data Files

These data were obtained in 2024 under the Public Records Act from the [CA
Commission on Peace Officer Standards and Training](https://post.ca.gov/) and
in 2023 from the [California Department of Corrections and
Rehabilitation](https://www.cdcr.ca.gov/).

Additionally, `ca-2023-corrections-dictionary.docx` contains metadata about the
corrections officer data.

The sha1 hashes of the received files:

```
$ date +"%Y-%m-%d %H:%M %p"
2024-06-11 19:43 PM

$ find input -type f | xargs sha1sum
c74f1eca550b764135577980bbfe292a5de2defd  input/ca-2023-corrections-dictionary.docx
654aa3863b38b22a42f634777e94ffa43f5ca234  input/CPRA_2024_R000304-011624.xlsx
e446e1a97ab3205f5e95a0cf5c0b9113d9cdac02  input/PDSQ118B-C_CDCR-Appts-Seps-2005-2023_Final.xlsx
```

## Python Packages Used

- `pandas`: For data manipulation
- `openpyxl`: to read Excel files
- `nameparser`: to parse full names into first/last/middle/suffix

## Data Cleaning and Processing

Law enforcement officer data and corrections officer data were processed
separately to create:

- ca-2024-clean-leo.csv
- ca-2023-clean-corrections.csv

Finally, to create the main index file, the two tables were concatenated. **The
two databases come from separate data systems, and do not share a unique
identifier.** No matching has been done between the two. If an individual
worked in both law enforcement and corrections, they would appear in this data
with two separate `person_nbr`s.

### `leo` data:

- `person_nbr`: input column was `POST_ID`
- `full_name`: uppercased, input column was `officer_name`
- `last_name`: extracted from `full_name` using `nameparser.HumanFormat`
- `first_name`: extracted from `full_name` using `nameparser.HumanFormat`
- `middle_name`: extracted from `full_name` using `nameparser.HumanFormat`
- `middle_initial`: first character of `Middle_name` if it exists
- `suffix`: extracted from `full_name` using `nameparser.HumanFormat`
- `birth_year`: was not provided, so not output
- `age`: was not provided, so not output
- `agcy_name`: uppercased, input column was `agency`
- `type`: `POLICE` for police, `CORRECTIONS` for corrections officers
- `rank`: uppercased, input column was `rank`
- `start_date`: converted to string in YYYY-MM-DD format, input column was
  `employment_start_date`
- `end_date`: converted to string in YYYY-MM-DD format, input column was
  `employment_end_date`

### `corrections` data

Corrections data from CDCR included event-level data for appointments and
separations. I linked separations to the relevant appointment records to create
employment history data with start and end date. Linking is based first on
exact match of `position_number`, and then on a combination of agency and rank,
linking to the most recent appoinment that precedes the separation.

The event data includes things promotions and inter-facility transfers that
have the same rank and employing agency. In these cases I flattened the stints
into a single stint.

In some cases a person's name changes during the course of their employment
(e.g. people changing their last name). In these cases, I've preserved
duplicate stint information, with a record for each version of the name, in
order to better facilitate look-ups.

- `person_nbr`: input column was `pernr`
- `full_name`: concatenation of first name, middle initial, and last name
- `last_name`: input column was `last_name`, uppercased and removed extra
  whitespace
- `first_name`: extracted from `first_middle`, uppercased and removed extra
  whitespace
- `middle_name`: not provided, not output
- `middle_initial`: extracted from `first_middle`, uppercased and removed extra
  whitespace
- `suffix`: not provided, not output
- `birth_year`: was not provided, so not output
- `age`: was not provided, so not output
- `agcy_name`: uppercased, input column was `facility_program`. In some cases
  the same numeric agency code was associated with multiple spelling variations
  of the `facility_program`. I used the numeric agency code extracted from the
  `position_number` input column (see the data dictionary for more details) to
  standardize the agency name across records.
- `type`: `POLICE` for police, `CORRECTIONS` for corrections officers
- `rank`: uppercased, input column was `class_title`. In some cases the same
  numeric class code was associated with multiple spelling variations of the
  `class_title`, I used the numeric code (extracted from `position_number` as
  described in the data dictionary) to create a standardized version of the
  rank
- `start_date`: converted to string in YYYY-MM-DD format. Input column was
  `trans_effective_date` for non-separation records
- `end_date`: converted to string in YYYY-MM-DD format. Input column was
  `trans_effective_date` for records marked "SEPARATION"

## Questions or suggestions for improvement?

Processing by Tarak Shah, Human Rights Data Analysis Group (HRDAG) at
tarak@hrdag.org
