# State Processing READMEs

This directory contains historical README files documenting the data cleaning and processing procedures for each state's POST data.

## Important Notice

**Most READMEs in this directory are outdated.**

These documents may not reflect current processing procedures due to:

1. **Frequent data updates:** State agencies regularly release new data with different formats or structures
2. **Schema changes:** The standardized schema has evolved over time, requiring reprocessing of data
3. **Methodology improvements:** Data cleaning techniques and tools have been refined and updated
4. **Source changes:** Some states have changed their data sources or reporting methods

## Purpose

These READMEs serve as:

- **Historical documentation:** Record of how data was processed at a specific point in time
- **Reference material:** Examples of data cleaning approaches and challenges for each state
- **Context:** Understanding of state-specific data quirks and edge cases
- **Starting point:** Initial guidance when working with a state's data (verify current accuracy)

## Using These READMEs

When working with a state's data:

1. **Read the relevant README** to understand historical context and challenges
2. **Verify current accuracy** by checking the actual source data format
3. **Check the cleaning scripts** in `../clean/src/<STATE>/` for current implementation
4. **Consult Dropbox** for the most recent raw data at `national-post-db/<state>/input/`
5. **Update as needed** if you find significant discrepancies

## Available State READMEs

The following states have historical documentation:

- Alaska (AK)
- Arizona (AZ)
- California (CA)
- Florida (FL)
- Georgia (GA)
- Idaho (ID)
- Illinois (IL)
- Kentucky (KY)
- Maryland (MD)
- Michigan (MI)
- North Carolina (NC)
- Nebraska (NE)
- New Jersey (NJ)
- Ohio (OH)
- Oregon (OR)
- South Carolina (SC)
- Tennessee (TN)
- Texas (TX)
- Utah (UT)
- Vermont (VT)
- Washington (WA)
- West Virginia (WV)
- Wyoming (WY)

## What These READMEs Typically Contain

Most state READMEs document:

- **Data sources:** Where the raw data was obtained
- **File formats:** Structure of the source files
- **Processing steps:** How the data was cleaned and transformed
- **Field mappings:** How source fields map to the standardized schema
- **Edge cases:** Special handling for unusual data patterns
- **Known issues:** Data quality problems or limitations
- **Processing date:** When the documentation was created

## Example: California README

The California README (`CA_README.md`) documents:
- Data obtained from CA POST in 2024
- Processing of both law enforcement and corrections data
- Name parsing using the `nameparser` library
- Field mappings from source to standardized schema
- Handling of duplicate person records across systems

**However:** If processing California data today, verify this information matches the current data format.

## Best Practices

### When Reading READMEs

- Treat as historical reference, not current documentation
- Cross-reference with actual source data
- Look for patterns and approaches rather than exact procedures
- Note state-specific challenges that may still apply

### When Updating READMEs

- Consider whether updating an old README or creating new documentation is more appropriate
- Include dates and data source information
- Document significant changes from previous versions
- Note any assumptions or decisions made during processing

## Current Data Processing

For current data cleaning procedures:

1. **Cleaning scripts:** `../clean/src/<STATE>/`
2. **Schema definition:** `../clean/src/schema.yml`
3. **Raw data:** Dropbox at `national-post-db/<state>/input/`
4. **Standardized schema:** See `../clean/README.md`
