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
## Naming Convention — IMPORTANT

The Firebase `db_launch` collection uses **full lowercase state names** as the
identity key throughout the data pipeline:

- Cleaned-CSV filename: `<full-state>_index.csv` (e.g. `california_index.csv`,
  `georgia_index.csv` — **not** `ca_index.csv`).
- `db/preprocess` derives the Firestore document prefix and the `state` field
  from the directory name. So the source must live under
  `states/<full-state>/<year>/` (e.g. `states/california/2026/`), and the
  `*_index.csv` filename inside `output/` must also use the full state name.
- This produces:
  - Firestore prefix: `<full-state>-processed.csv` (e.g.
    `california-processed.csv_0`, `california-processed.csv_1`, ...)
  - `state` field on each doc: `"<full-state>"` (e.g. `"california"`)
  - `document_id` field: `"<full-state>_<person_nbr>"`
- The frontend (`npi-new/national-police-index/`) queries
  `where state == "<full-state>"` and runs its post-upload pipeline with the
  full state name (e.g. `npx tsx scripts/normalizeStateData.ts california`).

If you use a state abbreviation (e.g. `ca`) for the directory or filename,
preprocess will silently produce a *different* prefix (`ca-processed.csv`)
and `state="ca"` — the frontend will not see those docs, and you will end up
with a parallel set of orphan documents in `db_launch`. Do not do this.

`pipeline/data/registry.csv` separately uses lowercase abbreviations (`ca`,
`ga`, `az`) for change-tracking — that file is independent of Firestore
naming. Keep it as-is.

## Adding New Data

There are two supported ways to add a new `(state, year)` of raw data. In both
cases, **Dropbox is the canonical source** — always upload there first so the
data is preserved for future contributors and automation runs.

### Option A — Automated (CC agent writes `clean.py`)

1. Upload raw files to `dropbox:national-post-db/<state>/<year>/input/`
   (lowercase state code).
2. Optional: upload state-provided reference data to
   `dropbox:national-post-db/<state>/<year>/output/` (used as groundtruth).
3. Optional: upload a state README to `dropbox:national-post-db/<state>/readme/`
   (one per state, not per year). A local copy in `readmes/<STATE>_README.md`
   also works.
4. Run the pipeline:
   ```bash
   set -a && source states/helpers/.env && set +a
   python3 -m pipeline.main --states <state>
   ```
   This pulls the data, invokes the CC agent to write `clean.py` + `validate.py`,
   runs the LLM judge, and opens a PR.

### Option B — Manual cleaning (you write `clean.py` yourself)

Use this when you want full control over the cleaning logic but still want the
raw data preserved in Dropbox for future runs.

1. **Upload to Dropbox** at the canonical path:
   ```
   dropbox:national-post-db/<state>/<year>/input/
   ```
2. **Pull it down** with rclone. The pipeline expects files at
   `states/<state>/<year>/data/input/` (lowercase). Either call rclone directly:
   ```bash
   rclone copy dropbox:national-post-db/<state>/<year>/input/ \
     states/<state>/<year>/data/input/
   ```
   or use the project's `RcloneClient` (matches what the automation does):
   ```bash
   set -a && source states/helpers/.env && set +a
   python3 -c "
   from pipeline.rclone_client import RcloneClient
   c = RcloneClient(remote='dropbox:national-post-db')
   c.copy('<state>', '<year>')
   if c.has_groundtruth('<state>', '<year>'):
       c.copy_groundtruth('<state>', '<year>')
   "
   ```
3. **Write the cleaning script** at `states/<state>/<year>/src/clean.py`
   following [DATA_PREPROCESSING.md](DATA_PREPROCESSING.md). Also write
   `states/<state>/<year>/src/validate.py` (LLM-as-judge).
4. **Run cleaning + validation** from the state/year directory:
   ```bash
   cd states/<state>/<year>
   python src/clean.py --input-dir data/input --output-dir output
   python src/validate.py   # writes output/judge_report.{md,json}
   ```
5. **Run preprocess + dry-run upload** from the repo root:
   ```bash
   cd db && make dry-run STATE=<state>
   ```
6. **Mark it in the registry** so the automation does not try to re-clean it.
   Add a row to `pipeline/data/registry.csv`:
   ```
   <state>,<year>,yes,no
   ```
   Flip the last column to `yes` after a successful Firebase upload.
7. **Upload to Firebase** when ready: `cd db && make upload STATE=<state>`.

8. **Run the front-end pipeline** (from the front-end repo, in order):
   ```bash
   npx tsx scripts/normalizeStateData.ts <full-state>
   npx tsx scripts/normalizeDatesByState.ts <full-state>
   npx tsx scripts/addSearchQueriesByState.ts <full-state>
   npx tsx scripts/generateStateStats.ts <full-state>
   npx tsx scripts/generateAgencyStats.ts <full-state>
   ```

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
Switch to the front-end repository ([github.com/National-Police-Index](https://github.com/National-Police-Index)) and run, in order:
```bash
npx tsx scripts/normalizeStateData.ts <full-state>
npx tsx scripts/normalizeDatesByState.ts <full-state>
npx tsx scripts/addSearchQueriesByState.ts <full-state>
npx tsx scripts/generateStateStats.ts <full-state>
npx tsx scripts/generateAgencyStats.ts <full-state>
```

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
