# Database Operations Directory

This directory contains the pipeline for downloading cleaned data from Dropbox, preprocessing it, and uploading it to the production database.

## Important

This workflow is a **separate task** that must be run **AFTER** data has been cleaned and uploaded to Dropbox via the `clean/` directory workflow.

## Three-Stage Workflow

The database operations follow a sequential three-stage process:

```
1. download/   →   2. preprocess/   →   3. upload/
```

Each stage must be completed before proceeding to the next.

## Directory Structure

```
db/
├── download/          # Stage 1: Download cleaned data from Dropbox
│   ├── Makefile
│   ├── data/
│   └── src/
├── preprocess/        # Stage 2: Preprocess and normalize data
│   ├── Makefile
│   ├── data/
│   └── src/
├── upload/           # Stage 3: Upload to production database
│   ├── Makefile
│   ├── data/
│   ├── src/
│   └── serviceAccountKey.json
└── delete/           # Utility for deleting records
```

## Stage 1: Download

Downloads recently cleaned data from Dropbox.

### Location
`db/download/`

### Purpose
Fetches the cleaned state data files (`<state>-index.csv`) from Dropbox that were uploaded after the data cleaning process.

### Usage

```bash
cd db/download
make download
```

This runs the download script (`src/src.py`) which:
- Connects to Dropbox
- Downloads cleaned CSV files for each state
- Saves files to `data/output/` directory

### Output
Downloaded files are stored in `download/data/output/` and will be used as input for the preprocessing stage.

## Stage 2: Preprocess

Preprocesses and normalizes all downloaded data.

### Location
`db/preprocess/`

### Purpose
Processes the downloaded data to ensure consistency and prepare it for database upload.

### Input
Data from `../download/data/output/`

### Output
Processed data to `data/output/` (compressed as `.csv.gz` files)

### Usage

**Normal run** (only process new/modified files):
```bash
cd db/preprocess
make run
```

**Force reprocessing** (reprocess all files):
```bash
make run-force
```

**Clean output** (remove all processed files):
```bash
make clean
```

**Setup directories** (create necessary directories):
```bash
make setup
```

### What Preprocessing Does

The preprocessing stage:
- Normalizes data formats
- Validates schema compliance
- Compresses output files
- Ensures consistency across states
- Prepares data for database insertion

## Stage 3: Upload

Uploads preprocessed data to the production database.

### Location
`db/upload/`

### Purpose
Uploads the preprocessed data to the production database (Firebase).

### Input
Preprocessed data from `../preprocess/data/output/`

### Authentication
Requires `serviceAccountKey.json` with Firebase credentials (already present).

### Usage

**Normal run** (upload with 5-second delay between states):
```bash
cd db/upload
make run
```

**Force specific states** (force upload specific states):
```bash
make run FORCE_STATES="ca tx fl"
```

**Force all states** (force upload all states):
```bash
make run-all
```

### Parameters

- `INPUT_DIR`: Input directory (default: `../preprocess/data/output`)
- `DELAY`: Delay in seconds between state uploads (default: `5`)
- `FORCE_STATES`: Space-separated list of state codes to force upload

### What Upload Does

The upload stage:
- Reads preprocessed CSV files
- Validates data integrity
- Uploads to Firebase database
- Includes rate limiting (delays between uploads)
- Tracks upload status and errors

## Complete Workflow Example

Here's a complete example of running all three stages:

```bash
# Stage 1: Download cleaned data from Dropbox
cd db/download
make download
cd ..

# Stage 2: Preprocess the downloaded data
cd preprocess
make run
cd ..

# Stage 3: Upload to production database
cd upload
make run
cd ..
```

## After Database Upload

Once data is uploaded to the database, you **must** run state-specific commands in the front-end repository for the data to appear in the application.

### Front-end Deployment

1. Navigate to the front-end repository: [github.com/National-Police-Index](https://github.com/National-Police-Index)
2. Run the state-specific deployment commands
3. Verify the data appears correctly in the application

**Note:** The user should provide front-end command details when ready to deploy.

## Troubleshooting

### Common Issues

**Issue:** Download fails
- **Solution:** Check Dropbox credentials and network connection
- **Solution:** Verify cleaned files exist in Dropbox at `national-post-db/<state>/output/`

**Issue:** Preprocessing fails
- **Solution:** Check that download completed successfully
- **Solution:** Verify input data matches expected schema
- **Solution:** Try `make clean` and `make run-force`

**Issue:** Upload fails
- **Solution:** Verify `serviceAccountKey.json` is present and valid
- **Solution:** Check Firebase permissions and quotas
- **Solution:** Review error logs in upload output

**Issue:** Data not appearing in front-end
- **Solution:** Ensure you've run the front-end deployment commands
- **Solution:** Check that upload completed successfully
- **Solution:** Verify state codes match between backend and front-end

## Utility: Delete

The `delete/` directory contains utilities for removing records from the database when needed.

**Use with caution:** This performs destructive operations on production data.

## Best Practices

1. **Always run stages sequentially:** Download → Preprocess → Upload
2. **Verify each stage:** Check output before proceeding to next stage
3. **Use delays:** Don't rush uploads; rate limiting prevents issues
4. **Monitor logs:** Watch for errors during each stage
5. **Test with one state:** When in doubt, test with a single state first
6. **Back up data:** Ensure Dropbox has clean data before uploading
7. **Coordinate with front-end:** Communicate with front-end team before deploying

## State-Specific Operations

### Processing a Single State

You can process individual states by filtering the data:

```bash
# Download all, but only preprocess/upload specific state
cd preprocess
# Manually move only the state file(s) you want to process
cd ../upload
make run FORCE_STATES="ca"
```

### Re-uploading a State

If you need to re-upload data for a state:

```bash
cd db/upload
make run FORCE_STATES="ca"  # Replace 'ca' with your state code
```

## Data Flow Summary

```
Dropbox (national-post-db/<state>/output/)
    ↓
db/download (fetch cleaned data)
    ↓
db/download/data/output/
    ↓
db/preprocess (normalize and compress)
    ↓
db/preprocess/data/output/
    ↓
db/upload (upload to Firebase)
    ↓
Production Database
    ↓
Front-end Deployment Commands
    ↓
Live Application
```
## Additional Resources

- **Data cleaning:** `../clean/README.md`
- **Historical documentation:** `../readmes/README.md`
- **Main repository README:** `../README.md`
- **Front-end repository:** [github.com/National-Police-Index](https://github.com/National-Police-Index)
