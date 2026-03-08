# CS6727 Synthetic Datasets (100 Users, Age 65+)

## Files generated
- `data/cs6727_DS1.csv`
- `data/cs6727_DS2.csv`
- `data/generation_metadata.json`
- generator code: `generate_cs6727_datasets.py`

## Data sources
1. BLS source spreadsheet (age-based annual spending means):
   - https://www.bls.gov/cex/tables/calendar-year/mean-item-share-average-standard-error/reference-person-age-ranges-2024.xlsx
2. BLS table index page:
   - https://www.bls.gov/cex/tables.htm
3. BLS note supporting dense transaction framing:
   - https://www.bls.gov/opub/btn/volume-4/consumer-expenditures-vary-by-age.htm
4. FinCEN pig-butchering alert (red flags):
   - https://www.fincen.gov/sites/default/files/shared/FinCEN_Alert_Pig_Butchering_FINAL_508c.pdf

## Reproducible generation command
```bash
python3 generate_cs6727_datasets.py \
  --source-xlsx reference-person-age-ranges-2024.xlsx \
  --output-dir data \
  --seed 6727 \
  --metadata-json data/generation_metadata.json
```

## Reproducibility details
- Seed: `6727`
- Deterministic dataset seeds internally:
  - DS1: `seed + 1`
  - DS2: `seed + 2`
- Users: `100`
- Transactions per user-month: `50`
- Months per user: `18`
- Age scope used: BLS columns `H`, `I`, `J` (65+, 65-74, 75+)

## Dataset definitions implemented
### Data Set 1 (`cs6727_DS1.csv`)
- 100 users total.
- First 12 months normal for all users.
- 80 users: final 6 months normal.
- 20 users: final 6 months scam-indicating months.
- Scam-indicating transaction patterns include:
  - new payees,
  - escalated payments to new payees,
  - payee categories tied to investment `taxes`, `fees`, `penalties`.

### Data Set 2 (`cs6727_DS2.csv`)
- 100 users total.
- 80 users: all 18 months normal.
- 20 users: all 18 months scam-indicating months (continuing scam behavior).

Note: prompt text says DS2 name `cs6727_DS1`; output uses `cs6727_DS2.csv` to avoid filename collision.

## Generated outputs (this run)
- `data/cs6727_DS1.csv`
  - SHA-256: `9d8e32665619f289664272e5a3ad8ce75263f6434f5ee4292f24640620f200f9`
  - Rows: `90000`
  - Users: `100`
  - Scam rows: `2700`
  - Normal rows: `87300`
- `data/cs6727_DS2.csv`
  - SHA-256: `2344487f3a56763e023a135be4a7dbcf3cbba6efa7336b035c1645900d3dc2e2`
  - Rows: `90000`
  - Users: `100`
  - Scam rows: `12300`
  - Normal rows: `77700`

## What is ignored intentionally
- race
- gender
- education
- other demographic factors beyond age category (65+ bands)

## Code used
- `generate_cs6727_datasets.py`
  - Parses `.xlsx` directly (zip+xml) without external dependencies.
  - Extracts top-level expenditure categories from BLS table.
  - Generates monthly transaction-level synthetic spending.
  - Injects scam indicators with requested red flags.

## Runtime/tool metadata
- Execution date: 2026-03-07
- Assistant runtime: Codex (GPT-5 based)
- Exact model version string: not exposed in this local environment

## Full prompt provided to Codex
```text
I need to generate some data sets that will be used for research 

1. Use this spreadsheet  (https://www.bls.gov/cex/tables/calendar-year/mean-item-share-average-standard-error/reference-person-age-ranges-2024.xlsx) as source of spending habits by age group for a year, this spreadsheet came from https://www.bls.gov/cex/tables.htm
2. I want to generate simulated data for age group 65 and older (65 and all above 65 age categories)  Assume the annual expenditure is uniformly  distributed across months. Make the data reasonably dense about 50 transactions per month 
3. To generate the data set ignore race/gender/education etc - just focus on age group 
4. Why 50 transactions - https://www.bls.gov/opub/btn/volume-4/consumer-expenditures-vary-by-age.htm
5. Here is lit of  red flags that can be used to simulate data that points to a scam using this pdf https://www.fincen.gov/sites/default/files/shared/FinCEN_Alert_Pig_Butchering_FINAL_508c.pdf
6. This data will be used for research paper - use some seed to make sure this data generation is reproducible when some one tries to reproduce this data independently
7. List of code that is used to generate this data
8. create a REDME.md file that provides reproducible command and all other relevant details like seed , how many users, how many rows SHA ... what is ignored , from where the distribution data came , from where Finn report came , which GPT model was used , what version - every possible detail
9. In readme add this whole prompt/command given to codex

Details of data sets to be generated
Data Set 1  
    1. name it cs6727_DS1
    2. Generate data for 100 people - where first 12 month data is normal data as per earlier assumptions (the spreadsheet given and 50 transactions per month)
    3. For 80 people add another 6 months of data that is continuing same pattern i.e. no scam
    4.  For remaining 20 -  insert 6 months of data that includes fraud indicating transactions 
    5. For fraud indicating transactions use these red flags (a) New payees (b) increased - escalated payments to new payees (c) category of payees in - “taxes,” “fees,” or “penalties” tied to the investment. 


Data Set 2 
1. name it cs6727_DS1
2. same as data set 1  with slight variatio 80 users with 18 months of data without any scam ; 20 users where   scam data is continuing for 18 months - use the same red flags used for Data Set
```
