# US National Police Index - Backend Data Repository

This repository contains the backend data processing infrastructure for the National Police Index. 

## Repository Structure

### Main Directories

#### 1. `clean/`
Scripts and tools for cleaning and processing raw data from state POST agencies.

**Key Points:**
- All raw data is stored in Dropbox under the `national-post-db` folder
- You will create custom cleaning scripts for each state
- Raw data is located in each state's `input/` subdirectory in Dropbox
- Download links in the `download/` directory may be outdated - always consult Dropbox for the most recent raw data

**Workflow:**
1. Download raw data from Dropbox (`national-post-db/<state>/input/`)
2. Create a cleaning script for the state (reference existing examples)
3. Process the data to match the standardized schema
4. Upload processed CSV to Dropbox (`national-post-db/<state>/output/<state>-index.csv`)

See [clean/README.md](clean/README.md) for detailed cleaning script creation guidance.

#### 2. `readmes/`
Historical README files documenting the data cleaning process for each state.

**Important Note:** Most READMEs are outdated due to:
- Frequent data updates from state agencies
- Schema changes and reprocessing of existing data
- Evolving data cleaning methodologies

These files provide historical context but may not reflect current processing procedures.

See [readmes/README.md](readmes/README.md) for more information.

#### 3. `db/`
Database operations for downloading cleaned data, preprocessing, and uploading to the production database.

**Important:** This is a separate task that must be run AFTER data has been cleaned and uploaded to Dropbox.

**Three-stage workflow:**
1. `download/` - Downloads recently cleaned data from Dropbox
2. `preprocess/` - Preprocesses all downloaded data
3. `upload/` - Uploads preprocessed data to the database

**Final step:** After uploading to the database, you must run state-specific commands in the front-end repository for the data to appear in the application.

See [db/README.md](db/README.md) for detailed database operations.

#### 4. `data/`
Local data storage organized by state abbreviation (e.g., `AK/`, `CA/`, `TX/`).
## Complete Workflow

### 1. Clean New State Data
- Download raw data from Dropbox (`national-post-db/<state>/input/`)
- Create a cleaning script in `clean/src/<STATE>/` (reference existing state examples)
- Run your script to process the data according to the standardized schema
- Upload processed CSV to Dropbox (`national-post-db/<state>/output/<state>-index.csv`)

See [clean/README.md](clean/README.md) for detailed guidance on creating cleaning scripts.

### 2. Database Operations
Navigate to the `db/` directory and run the three-stage process:
- **Download:** Fetch cleaned data from Dropbox
- **Preprocess:** Process and normalize the data
- **Upload:** Upload to the production database

### 3. Front-end Deployment
Switch to the front-end repository ([github.com/National-Police-Index](https://github.com/National-Police-Index)) and run state-specific deployment commands.

## Data Schema

The standardized schema across all states includes the following core fields:

```typescript
interface PoliceOfficer {
  // Core identification
  person_nbr: string;           // Unique officer identifier

  // Name fields
  full_name: string;            // Complete name
  first_name: string;           // First name
  middle_name?: string;          // Middle name
  last_name: string;            // Last name

  // Employment details
  agency_name: string;          // Agency/department name
  rank: string;                 // Officer rank/title
  start_date: string;           // Employment start date (YYYY-MM-DD)
  end_date: string;             // Employment end date (YYYY-MM-DD)
  state: string;                // State abbreviation


  // Optional fields
  current_certificate_status: string;  // Current certification status
  position?: string;            // Position title
  status?: string;              // Employment status
  notes?: string;               // Additional notes
  offense?: string;             // Disciplinary offense
  sanction?: string;            // Sanction imposed
  violation?: string;           // Type of violation
  sanction_date?: string;       // Date of sanction
  separation_reason?: string;   // Reason for separation
  employment_status?: string;   // Current employment status
  certification_type?: string;  // Type of certification
  type?: string;                // Officer type (police/corrections)

  // Additional fields
  [key: string]: any;           // Allow for state-specific fields
}
```

## Prerequisites

```bash
pip install -r requirements.txt
```

## Contributing

When adding a new state:

1. Download raw data from Dropbox (`national-post-db/<state>/input/`)
2. Create a new cleaning script in `clean/src/<STATE>/` (reference existing examples)
3. Process the data to match the standardized schema
4. Verify output conforms to the schema and is named `<state>-index.csv`
5. Upload cleaned data to Dropbox (`national-post-db/<state>/output/`)
6. Run the three-stage database workflow in `db/`
7. Deploy to front-end repository

See [clean/README.md](clean/README.md) for detailed cleaning guidance.

## Resources

- **Dropbox:** `national-post-db/` - Raw and processed data
- **Front-end Repository:** [github.com/National-Police-Index](https://github.com/National-Police-Index)
