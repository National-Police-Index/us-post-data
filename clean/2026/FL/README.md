# Florida FDLE ATMS — 2026

## Data Files

Obtained under Florida's public records law from the [Florida Department of
Law Enforcement](https://www.fdle.state.fl.us/OGC/Public-Records.aspx)
(FDLE). It is an export of ATMS, FDLE's officer certification database,
covering every officer certified in the state back to the 1940s. Each table
is a CSV in `data/input/`:

| File | Rows | Used | Contents |
|---|---|---|---|
| `employment.csv` | 675,833 | yes | One row per officer × agency × employment class |
| `person_data.csv` | 567,026 | yes | Name, sex, race, birth year per `person_nbr` |
| `agencies.csv` | 888 | yes | `agcy_nbr` → agency name |
| `codes.csv` | 2,667 | yes | Code → description for every coded column |
| `certificates.csv` | 374,139 | yes | Certificates held and their current status |
| `complaint.csv` | 46,660 | yes | One row per FDLE case against an officer |
| `complaint_offenses.csv` | 47,889 | yes | Violations alleged in each case |
| `complaint_discipline.csv` | 15,619 | yes | Sanctions imposed in each case |
| `complaint_status.csv` | 102,737 | no | Case status history |
| `complaint_activity.csv` | 227,131 | no | Staff activity log per case |
| `complaint_expenses.csv` | 3,427 | no | Case expenses |
| `basic_exam.csv` | 889,358 | no | State certification exam results |
| `training.csv` | 1,231,699 | no | Training classes completed |
| `course.csv` | 352 | no | Training course catalogue |

**Every coded value is decoded from `codes.csv`**, including employment
class, employment type, separation reason, race, sex, certificate type and
status, offense, plea and sanction. Unknown codes are kept as-is (5 offense
rows use `6100`/`3700`, which are not defined).

All dates are `MM/DD/YY HH:MM:SS` with **two-digit years**, except
`complaint_offenses.offense_date` (`M-DD-YYYY`). The latest date in the
export is 2025-12-12 and no year is `26`, so `00–25` are 20xx and `26–99`
are 19xx. pandas' default pivot would put a 1968 hire in 2068.

The 2023 release was cleaned by CBS News in R (`readmes/FL_README.md`,
`clean_deprecated/src/FL/`). This release is cleaned from scratch.

## Replicating

Run from `clean/2026/FL/`:

```bash
python src/clean.py --input-dir data/input --output-dir data/output
```

Takes about 1 minute. It writes `data/output/fl_index.csv`,
`data/output/fl-discipline_index.csv` and audit files in
`data/output/review/`. `src/clean.ipynb` is the exploratory notebook the
script grew out of.

## Python Packages Used

- `pandas`: everything

## Employment index (`fl_index.csv`)

### People (`person_data.csv`)

- **Duplicates:** 9 `person_nbr`s appear more than once, as case or spelling
  variants of the same person (`QUINONES`/`Quinones`). The first is kept;
  all are in `review/person_data_duplicates.csv`.
- **Names:** whitespace is collapsed, and stray commas are stripped.
- **Suffixes:** ATMS has no suffix column, so suffixes are typed into the
  name fields (`Torres Jr.`, `Farrin, Jr`, first name `James Jr`, middle
  name `Jr`). `jr`, `sr`, `ii`, `iii` and `iv` are moved to `suffix`. `V`
  is not, because here it is almost always a middle initial.
- **`full_name`:** `last, first middle suffix`, lowercased.
- **Race:** decoded from `codes.csv`. `NA` means **American Indian/Native
  Alaskan**, not missing. `WHI` and `H` are undefined variants of `Wh` and
  `His`.
- **Sex:** decoded. `U` (Unknown) and undefined values (`O`) are left
  empty.
- **`year_of_birth`:** `birth_year` when it is a 4-digit year.

### Agencies (`agencies.csv`)

Names are already title case. `clean_agency_names` does three things:

- Finishes names cut off at 60 characters (`…Investigations Di` →
  `Division`, `…Police Departmen` → `Department`).
- Expands agency-specific prefixes: `Dc,` → Department Of Corrections,
  `Dep,` → Department Of Environmental Protection, `Fdle` → Florida
  Department Of Law Enforcement.
- Expands common abbreviations: `Dept`, `Svcs`, `Mgt`, `Ctr`, `Afb`,
  `Sec Pol Squad`, `Fl`, `U S`.

`St.` and `Ft.` are place names and are left alone. Two agency numbers
share a name (FDLE is `11` and `611`); their stints are treated as one
agency.

### Employment rows (`employment.csv`)

1. **Decode codes:** `type` ← `employ_class` (Correctional, Law
   Enforcement, Instructor, Concurrent, Corr Probation, Civilian);
   `employment_status` ← `employ_type` (Full-Time, Part-Time, Auxiliary,
   Special Elected or Appointed Position); `separation_reason` ←
   `separation_code`. A separation reason is cleared on open rows.
2. **`notes`** ← `employ_comments` (8% filled), with email addresses
   and phone numbers replaced by `[email]` / `[phone]`. See open question 1.
3. **Drop** to review:
   - `test_agency.csv` (2): FDLE's "Fake Training Center"
   - `end_before_start.csv` (237): separation before hire
   - `exact_duplicates.csv` (2,798): same person, agency, start and end
   - `no_name.csv` (4): no first or last name
4. **Collapse stints** (672,792 → 595,282 rows; the members of each merged
   stint are in `review/collapsed_stints.csv`). See below.
5. **`current_certificate_status`**: for each certificate type the officer
   holds, the status of their latest one, e.g. `Correctional: Inactive
   Revoked; Law Enforcement: Active`. It is per officer, so it is the same
   on every one of their rows. 87% of officers have a certificate.

### Why stints are collapsed

ATMS opens a new employment row whenever an officer's **class** changes
(Correctional → Law Enforcement, adding a concurrent or instructor
appointment). The previous row is closed as "Transfer Within Agency (No
break in service)". Before collapsing, ~80k rows continue an earlier row at
the same agency, and 25k of those overlap it.

`collapse_stints` groups by `(person_nbr, agency_name)`, sorts by start,
and starts a new stint when a row begins more than one day after the
**running maximum** end date so far. A long appointment therefore absorbs
everything nested inside it. In each merged stint:
- `start_date` is the earliest start and `end_date` the latest end. The
  stint is open if any member is open.
- `separation_reason` comes from the member that ended last.
- `notes` joins every member's notes with ` | `.
- Everything else comes from the latest-starting member.

**No stale-open rule.** KS/IL treat an open row followed by a later row at
the same agency as never closed. In Florida, the later rows are usually
concurrent or instructor appointments that lapse ("Failure to Meet
Mandatory Retraining") while the officer stays employed. Only 167 of the
947 affected officers have a later job elsewhere, so open rows are taken at
face value.

Florida is not in `COLLAPSE_STINTS` in `db/preprocess`. It wouldn't matter
if it were: after this pass no two stints at one agency are within a day of
each other.

**Result:** 595,282 stints, 320,096 officers, 730 agencies. 99,652 stints
are open (currently employed).

## Discipline index (`fl-discipline_index.csv`)

One row per **sanctioned violation**.

1. **Violations** (`complaint_offenses.csv`): `violation` is the decoded
   `offense_code`, prefixed by the decoded plea or finding in
   `offense_prefix` when present ("Pled No Contest to Obscene
   Material-Possess"). Trailing hyphens in the code descriptions are
   stripped. `violation_comments` ← `offense_comments` ("(3 Counts)",
   "FELONY"). `violation_date` ← `offense_date` (13% filled).
2. **Sanctions** (`complaint_discipline.csv`): `sanction` is the decoded
   `discipline_imposed` (Revocation, Vol Relinquishment, Susp/Prob,
   Probation, Dismissed, …). `sanction_date` ← `final_order_date`.
   `sanction_comments` ← `discipline_comments`.
3. **Inner join** violations to sanctions on `complaint_nbr`, so only
   violations with a sanction are kept. When a case has several sanctions,
   the most recent is kept per violation, which avoids the many-to-many
   blow-up. About 31k complaints have no sanction (dismissed at probable
   cause, closed, or pending) and are not in this index.
4. **Case dates** from `complaint.csv`: `case_opened_date`,
   `case_closed_date`.
5. **Attach to an employment stint.** `complaint.csv` records the agency
   and employment start date each case was opened against. The violation
   takes the collapsed stint at that agency that contains that start date.
   Failing that, it takes the stint that contains the case-opened date, and
   failing that, the closest stint at that agency. About 10% of complaints
   name no agency, and most of those were opened after the officer left
   (median ~2.3 years after). Those take the stint at any agency that
   contains, or is closest to, the case-opened date, usually the job that
   just ended. 71 violations name an agency the officer has no stint at;
   they go to `review/discipline_no_stint.csv`.
6. **One row per incident.** FDLE sometimes opens a separate case for the
   same incident, e.g. one per certificate or agency. Such cases share the
   person, violation, sanction and final-order date but have a different
   `case_id`. One row is kept, the one on the most recently started stint,
   so misconduct isn't counted twice. 77 duplicates go to
   `review/duplicate_incidents.csv`.

**Result:** 18,955 violations, 14,111 officers, 544 agencies.

## Output columns

`fl_index.csv`: `person_nbr`, `full_name`, `first_name`, `middle_name`,
`last_name`, `suffix`, `agency_name`, `type`, `employment_status`,
`start_date`, `end_date`, `separation_reason`, `notes`,
`current_certificate_status`, `race`, `sex`, `year_of_birth`, `state`.

`fl-discipline_index.csv`: `case_id`, `person_nbr`, `full_name`,
`first_name`, `middle_name`, `last_name`, `suffix`, `agency_name`, `type`,
`start_date`, `end_date`, `case_opened_date`, `case_closed_date`,
`violation`, `violation_date`, `violation_comments`, `sanction`,
`sanction_date`, `sanction_comments`, `race`, `sex`, `year_of_birth`,
`state`.

## Columns deliberately dropped

- Audit metadata on every table: `*_user_code`, `*_datetime`,
  `row_revision`, `id`.
- Agency administrator names and contact fields; region and staff numbers.
- `complaint.complaint_received_from`: free text that names complainants.
- `employment.employ_tea`, `equivalency`, `fingerprint_card_process_date`,
  `military*`: administrative, or nearly empty.

## Issues / open questions

1. **`notes` contains third-party names.** Phone numbers and emails are
   redacted, but the free text still names HR contacts, coworkers and
   occasionally inmates ("Contact HR - <name>"). Review before publishing
   it on the front end.
2. **Sanctions include non-punitive outcomes.** `Dismissed`, `No
   Cause-Dismissed`, `Denied` and `None` are FDLE dispositions in
   `complaint_discipline.csv` and are kept, as in the 2023 release.
3. **Birth-year edge cases.** 60 stints start before age 16 and 1,103 after
   age 75. These are likely DOB errors in the source and are left as-is.
