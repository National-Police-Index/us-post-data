# Michigan Revocation database README
This README provides an overview of the data cleaning process for the [Michigan Commission on Law Enforcement Standards](https://www.michigan.gov/mcoles/), or "MCOLES", [Revocation](https://regulations.justia.com/states/michigan/state-police/michigan-commission-on-law-enforcement-standards-mcoles/law-enforcement-standards-and-training/part-6/section-r-28-14604/) data from 2000 - 2018 (exclusive). The code

The names of Michigan Law Enforcement personnel who have had their license revoked by MCOLES between 2018 to present are listed on their [webpage](https://www.michigan.gov/mcoles/commission-info/revocations). Conviction information is not available in the linked summary documents.

### Libraries Used
The following libraries are used to process the data:
- `pdftotext`
- `hashlib`
- `functools`
- `re`
- `pandas`

Other libraries, such as `argparse` and `logging`, are also used but do not operate on data and instead contribute to the organization and automation of the pipeline.

### Data Sources
These scripts utilize one main data source:

1. `Revocation List.pdf`: Contains information about MCOLES investigations that resulted in a conviction. Includes a case number, the officer's name, the date of the investigation (assumed to be the date the investigation closed / date of the conviction), a summary of the conviction, and the datefield called "comm. action" (assumed to be the date MCOLES took [disciplinary action](https://www.michigan.gov/mcoles/-/media/Project/Websites/mcoles/Standards-and-Training/Employment-Standards/MCOLES_Policies_Procedures.pdf?rev=4c6f3294b5f84c12ae89fdc427d6c5f1) and revoked the license).

### Data Cleaning Process

This pipeline was contributed by someone from HRDAG, which uses a particular form of principled data processing to organize its work. For more information about this structure and why its used, check out [The Task Is A Quantum Of Workflow](https://hrdag.org/2016/06/14/the-task-is-a-quantum-of-workflow/).

This data processing is organized into a handful of tasks which run in the following order:
1. `import` takes the source PDF(s), converts to .txt file(s), and builds an index of the file(s)
2. `format` takes the file index and reads in the text revocation file with decertifications prior to 2018. Using the case numbers, identifies the row boundaries and builds an index of the officers who had their license revoked. Also formats the conviction summaries for each row and named officer.
3. `scrape` uses the url of the [revocations page](https://www.michigan.gov/mcoles/commission-info/revocations) to scrape the list of names and corresponding PDF documents for revocations from 2018 onward.
4. `merge` combines the revocation data extracted from the source PDFs with the data scraped from the website.
5. `indicate` standardizes some of the available fields and adds indicators based on keyword patterns in the conviction data.
6. `export` copies the final tables to be exported as processed data.

There is also a `write` task which has some exploratory data analysis using the processed data files.

There are no agency names or duplicate officer names in the source material, so no de-duplication is performed in this pipeline. More specific information about what methods are applied to the data can be found in the corresponding task directory. As explained in [The Task Is A Quantum Of Workflow](https://hrdag.org/2016/06/14/the-task-is-a-quantum-of-workflow/), source code lives in the `src` directory, handwritten files (such as keyword patterns) go in `hand`, and each task has a `Makefile` that maintains the rules for building that task and its `output`. Any Jupyter notebooks or RMarkdown files will go in `note`. The main Makefile has the rules for building all tasks from one `make` call.

```
police-certification/etl/MI$ tree -L 2
.
├── Makefile
├── README.md
├── export
│   ├── Makefile
│   └── output
├── format
│   ├── Makefile
│   ├── hand
│   ├── output
│   └── src
├── import
│   ├── Makefile
│   ├── output
│   └── src
├── indicate
│   ├── Makefile
│   ├── hand
│   ├── output
│   └── src
├── merge
│   ├── Makefile
│   ├── hand
│   ├── output
│   └── src
├── scrape
│   ├── Makefile
│   ├── hand
│   ├── output
│   └── src
└── write
    └── note
```

To run the series of tasks, call `make` from the `etl/MI` directory with the MI `Revocation List.pdf` in a directory called `police-cert-data` that is next to the `police-certification` repo. Alternatively, modify the main Makefile and `import/Makefile` to read from the location where you put this data file.

### Processed files

These are the processed data files available in `export/output` and copied to the main level:
1. `mi-2023-revocation-index.csv`
2. `mi-2023-revocation-indicators.csv`

Running the main Makefile will also download the PDFs linked on the revocations webpage for decertifications since 2018 into `scrape/output/pdfs`, though these files are not otherwise handled in the data processing.

#### 1. Revocation index
The majority of the processed data in `mi-2023-revocation-index.csv` contains the MCOLES case number, the name of the officer whose license was revoked, the date the investigation closed, the date of decertification, and a summary of the conviction. However, the data available since 2018 does not include the date the investigation closed.

The source data lacks information about the agency, the hiring or termination date of the officer, the officer's age, or many other expected features of the POST database.

#### 2. Conviction indicators
While the source data lacks much information about the officer or their position, it does include information about the conviction. Some indicators have been setup in `mi-2023-revocation-indicators.csv` based on keywords found in the `conviction` field. The keywords and corresponding regex patterns applied can be found in `indicate/hand/rules.yml`.

### Questions or comments?
Contact the developer, HRDAG Data Scientist Bailey Passmore: bailey@hrdag.org
