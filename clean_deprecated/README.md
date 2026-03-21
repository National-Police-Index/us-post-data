# Data Cleaning Directory

This directory contains all scripts and tools used to clean and process raw POST data from state agencies.

## Important: Data Location

**All data is stored in Dropbox, NOT in this repository.**

- **Dropbox folder:** `national-post-db/`
- **Organization:** Data is organized by state abbreviation (e.g., `ca/`, `tx/`, `fl/`)
- **Input data:** Located in `national-post-db/<state>/input/`
- **Output data:** Should be uploaded to `national-post-db/<state>/output/`

**Warning:** The download links in the `download/` directory may be outdated. Always consult Dropbox for the most recent raw data.

## Directory Structure

```
clean/
├── download/          # Download scripts (may contain outdated links)
│   ├── Makefile
│   ├── data/
│   └── src/
└── src/              # State-specific cleaning scripts
    ├── AK/
    ├── CA/
    ├── FL/
    ├── ...
```

## Data Cleaning Workflow

### 1. Download Raw Data

Download the raw data for your state from Dropbox:
- Navigate to `national-post-db/<state>/input/`
- Download all relevant files to your local machine

**Note:** Do not rely on the `download/` directory scripts as they may contain outdated links.

### 2. Create Cleaning Script

You will need to create a new cleaning script for your state. Reference existing state directories in `src/<STATE>/` for examples.

**Location:** `src/<STATE>/clean.py` (or similar)

Your cleaning script should:
1. Read the raw data files
2. Parse and normalize officer names
3. Standardize dates to YYYY-MM-DD format
4. Clean and standardize agency names and ranks
5. Map state-specific fields to the standardized schema
6. Handle state-specific data quirks and edge cases
7. Output `<state>-index.csv`

See the "Creating a Cleaning Script" section below for detailed guidance.

### 3. Upload Processed Data

After cleaning:
1. Verify the output CSV matches the required schema (see below)
2. Upload the processed CSV to Dropbox: `national-post-db/<state>/output/`
3. Name the file: `<state>-index.csv` (e.g., `ca-index.csv`, `tx-index.csv`)

## Standardized Data Schema

All cleaned data must conform to the following TypeScript interface, which defines the columns configured to render on the front-end:

```typescript
export interface PoliceOfficer {
  // core fields
  agency_name: string;                    // Name of the employing agency
  start_date: string;                     // Employment start date (YYYY-MM-DD)
  end_date: string;                       // Employment end date (YYYY-MM-DD)
  full_name: string;                      // Complete name
  first_name: string;                     // First name
  last_name: string;                      // Last name
  person_nbr: string;                     // Unique person identifier
  state: string;                          // State abbreviation (lowercase)

  // Optional fields
  rank: string;                           // Officer rank/title
  middle_name: string;                    // Middle name
  current_certificate_status: string;     // Current certification status
  position?: string;                      // Position title
  status?: string;                        // Employment status
  notes?: string;                         // Additional notes
  offense?: string;                       // Disciplinary offense
  sanction?: string;                      // Sanction imposed
  violation?: string;                     // Type of violation
  sanction_date?: string;                 // Date of sanction (YYYY-MM-DD)
  separation_reason?: string;             // Reason for separation
  employment_status?: string;             // Current employment status
  certification_type?: string;            // Type of certification
  type?: string;                          // Officer type (police/corrections)

  // Extensibility
  [key: string]: any;                     // Allow for state-specific fields
}
```

### Key Schema Notes

1. **Dates:** Must be in `YYYY-MM-DD` format
2. **State:** Use lowercase two-letter abbreviation (e.g., `ca`, `tx`)
3. **Names:** Properly parsed into `first_name`, `middle_name`, `last_name`, and combined `full_name`
4. **Identifiers:** Both `person_nbr`
5. **Optional Fields:** Include when available in source data

## Creating a Cleaning Script

When creating a new cleaning script for a state, you'll need to develop a custom Python script that processes the raw data into the standardized schema.

### Recommended Libraries

Common libraries used in cleaning scripts:
- `pandas`: Data manipulation and analysis
- `fuzzywuzzy`: Fuzzy string matching for agency names

### Typical Cleaning Steps

#### 1. State-Specific Cleaning

These steps vary by state based on the raw data format:

**a. Reading and Renaming Columns**
- Load the raw data files (CSV, Excel, etc.)
- Rename columns to more readable and consistent names

**b. Splitting Names**
- Parse full names into `first_name`, `middle_name`, `last_name`
- Handle suffixes (Jr., Sr., III, etc.)
- Clean names by removing extra whitespace and periods

**c. Cleaning Personal Numbers**
- Standardize `person_nbr` format (remove whitespace, lowercase)
- Ensure uniqueness where possible

**d. Cleaning Ranks**
- Remove leading/trailing whitespace
- Replace abbreviations with full words (e.g., "Lt" → "Lieutenant")
- Standardize rank names across the dataset
- Note: Expand contracted names rather than inferring information not in the data

**e. Cleaning Agency Names**
- Remove prefixes and suffixes
- Replace common abbreviations (e.g., "Dept" → "Department")
- Uppercase for consistency
- Use fuzzy matching to map to ground truth agency names if available

**f. Merging Datasets**
- If data comes from multiple files (employment, demographics, etc.), merge on `person_nbr`
- Handle missing values appropriately

**g. Date Cleaning**
- Parse various date formats
- Convert to `YYYY-MM-DD` format
- Handle missing or invalid dates

#### 2. Non-State-Specific Cleaning Steps

These steps should be applied to all states for consistency:

**a. Column Renaming**
- Map state-specific column names to standardized schema fields
- Ensure all required fields are present

**b. Date Formatting**
- Convert all date columns to `YYYY-MM-DD` format

**c. Case Standardization**
- Convert string columns to UPPERCASE for consistency
- Exception: `state` field should be lowercase

**d. Name Standardization**
- Remove extra whitespace from name fields
- Remove periods from names
- Create `full_name` by concatenating `first_name`, `middle_name`, `last_name`

**e. Add State Column**
- Add a `state` column with lowercase two-letter abbreviation

### Example Cleaning Script Structure

```python
import pandas as pd
from nameparser import HumanName

# 1. Read raw data
employment_df = pd.read_csv('input/officer_employment.csv')
demographic_df = pd.read_csv('input/officer_data.csv')

# 2. Rename columns
employment_df.rename(columns={
    'officer_id': 'person_nbr',
    'dept_name': 'agency_name',
    # ... etc
}, inplace=True)

# 3. Clean and parse names
def parse_name(full_name):
    name = HumanName(full_name)
    return pd.Series({
        'first_name': name.first.upper(),
        'middle_name': name.middle.upper(),
        'last_name': name.last.upper()
    })

demographic_df[['first_name', 'middle_name', 'last_name']] = \
    demographic_df['full_name'].apply(parse_name)

# 4. Clean ranks and agencies
employment_df['rank'] = employment_df['rank'].str.strip().str.upper()
employment_df['agency_name'] = employment_df['agency_name'].str.strip().str.upper()

# 5. Merge datasets
merged_df = employment_df.merge(demographic_df, on='person_nbr', how='left')

# 6. Standardize dates
merged_df['start_date'] = pd.to_datetime(merged_df['start_date']).dt.strftime('%Y-%m-%d')
merged_df['end_date'] = pd.to_datetime(merged_df['end_date']).dt.strftime('%Y-%m-%d')

# 7. Add state column
merged_df['state'] = 'ga'

# 8. Create full_name
merged_df['full_name'] = (
    merged_df['first_name'] + ' ' +
    merged_df['middle_name'] + ' ' +
    merged_df['last_name']
).str.replace(r'\s+', ' ', regex=True).str.strip()

# 9. Select and order columns according to schema
output_columns = [
    'person_nbr', 'document_id', 'full_name', 'first_name',
    'middle_name', 'last_name', 'agency_name', 'rank',
    'start_date', 'end_date', 'state', 'current_certificate_status',
    # ... additional fields as available
]

output_df = merged_df[output_columns]

# 10. Save output
output_df.to_csv('output/ga-index.csv', index=False)
```

### Tips for Creating Cleaning Scripts

1. **Explore the data first:** Use Jupyter notebooks to understand the data structure
2. **Document your decisions:** Comment your code explaining why certain choices were made
3. **Handle edge cases:** Look for unusual patterns and handle them explicitly
4. **Validate output:** Check that all required fields are present and formatted correctly
5. **Reference existing scripts:** Look at other state directories for patterns and approaches

## State-Specific Cleaning

Each state has unique data formats and challenges. Refer to:

1. **Existing state directories:** `src/<STATE>/` for cleaning script examples
2. **Historical READMEs:** `../../readmes/<STATE>_README.md` for context (note: often outdated)
3. **Similar states:** Look at states with similar data sources or formats

## Best Practices

1. **Always verify raw data:** Check Dropbox for the latest version before starting
2. **Test on sample data:** Run scripts on a small subset first
3. **Document edge cases:** Note any unusual data patterns or decisions
4. **Validate output:** Ensure all required fields are present and properly formatted
5. **Check for duplicates:** Verify no duplicate `person_nbr` or `document_id` values
6. **Quality assurance:** Spot-check random records for accuracy

## Questions or Issues?

When encountering data quality issues:
1. Document the issue in your cleaning script comments
2. Make a best-effort attempt to handle the data
3. Note any assumptions made during cleaning
4. Consider updating relevant documentation
