# Reproducible Synthetic Spending Dataset (BLS CEX 2024, Age 65+)

## Purpose
This project generates a reproducible synthetic transaction dataset for research:
- Population size: `10` synthetic adults
- Age scope: `65+` only (`65 years and older`, `65-74 years`, `75 years and older`)
- Period: `12` months (`2024`)
- Density target: about `50 transactions per adult per month`

## Data Source and Provenance
- Source workbook (local): `/Users/arvimahe/Downloads/reference-person-age-ranges-2024.xlsx`
- Original BLS file URL: <https://www.bls.gov/cex/tables/calendar-year/mean-item-share-average-standard-error/reference-person-age-ranges-2024.xlsx>
- BLS table index page: <https://www.bls.gov/cex/tables.htm>
- BLS article motivating dense transaction behavior (~50/month context): <https://www.bls.gov/opub/btn/volume-4/consumer-expenditures-vary-by-age.htm>
- Table used inside workbook:
  `Table 1300. Age of reference person: Annual expenditure means, shares, standard errors, and relative standard errors, Consumer Expenditure Surveys, 2024`

## What Was Used vs Ignored
Used:
- Only age-based expenditure columns:
  - `65 years and older`
  - `65-74 years`
  - `75 years and older`
- Annual `Mean` expenditures (overall and item-level categories) from the table.

Ignored:
- Race
- Gender/sex
- Education
- Hispanic/Latino origin
- Housing tenure and all non-age demographic splits

## Generation Logic
1. Parse the XLSX directly (OOXML XML) from the local workbook.
2. Extract annual mean expenditure for the three 65+ columns.
3. Build 10 adults spanning all 65+ categories.
4. Assign each adult an annual budget sampled around their age-group annual mean.
5. Split each adult annual budget uniformly across 12 months.
6. For each adult-month, generate 48-52 transactions (about 50).
7. Allocate each month’s exact budget across transactions (in cents) so totals match.
8. Sample transaction categories with probability proportional to BLS category annual means.

## Reproducible Command
Run from `/Users/arvimahe/Documents/gtech_2767_data_generation`:

```bash
python3 /Users/arvimahe/Documents/gtech_2767_data_generation/generate_65plus_simulated_data.py \
  --source /Users/arvimahe/Downloads/reference-person-age-ranges-2024.xlsx \
  --adults 10 \
  --year 2024 \
  --seed 20260306 \
  --output-csv /Users/arvimahe/Documents/gtech_2767_data_generation/simulated_spending_65plus_10adults_2024.csv \
  --output-metadata /Users/arvimahe/Documents/gtech_2767_data_generation/simulated_spending_65plus_10adults_2024.metadata.json
```

## Fixed Reproducibility Parameters
- Seed: `20260306`
- Adults: `10`
- Year: `2024`
- Transaction density per adult-month: random integer in `[48, 52]`
- Adult-month pairs: `120` (`10 adults * 12 months`)

## Output Artifacts
- Generator script: `/Users/arvimahe/Documents/gtech_2767_data_generation/generate_65plus_simulated_data.py`
- Dataset CSV: `/Users/arvimahe/Documents/gtech_2767_data_generation/simulated_spending_65plus_10adults_2024.csv`
- Metadata JSON: `/Users/arvimahe/Documents/gtech_2767_data_generation/simulated_spending_65plus_10adults_2024.metadata.json`

## Output Summary (Current Reproducible Run)
- Total rows (transactions): `5997`
- Adults: `10`
- Months covered: `1-12` of `2024`
- Transactions per adult-month:
  - Min: `48`
  - Max: `52`
  - Average: `49.975`
- Total simulated spend: `$627,854.04`

Annual mean expenditure inputs from BLS Table 1300 (age columns only):
- `65 years and older`: `61432.0`
- `65-74 years`: `65354.0`
- `75 years and older`: `55834.0`

Item categories used per age group: `111`

## Integrity Checks (SHA-256)
- `simulated_spending_65plus_10adults_2024.csv`
  - `0878e6d12e91ebdf81e0cfc0791df61c6a36643f3e23e5180f8b76b176974ed8`
- `simulated_spending_65plus_10adults_2024.metadata.json`
  - `7c21b3d40122331bd91398d7b986feed1ea56514ed258235e132dc6b3cfcb6f7`
- `generate_65plus_simulated_data.py`
  - `e6a2093dca59cb473f95e32dcea9e8c53804b38b339d2740aed978c4b59f7771`

Verify hashes:

```bash
shasum -a 256 \
  /Users/arvimahe/Documents/gtech_2767_data_generation/simulated_spending_65plus_10adults_2024.csv \
  /Users/arvimahe/Documents/gtech_2767_data_generation/simulated_spending_65plus_10adults_2024.metadata.json \
  /Users/arvimahe/Documents/gtech_2767_data_generation/generate_65plus_simulated_data.py
```

## Runtime Environment (Generation Session)
- UTC timestamp: `2026-03-06T07:06:09Z`
- OS: `Darwin 25.3.0 arm64`
- Python: `3.11.5`
- Working directory:
  `/Users/arvimahe/Documents/gtech_2767_data_generation`

## Model and Tooling Provenance
- Generation script and artifacts were produced in OpenAI Codex desktop.
- Assistant family: `GPT-5` (Codex coding agent).
- Exact backend model build/version string is not exposed in this runtime, so a numeric model revision cannot be recorded from inside this environment.

## Notes for Research Use
- This is synthetic data and should not be interpreted as individual-level observed BLS microdata.
- Category names and high-level distributional structure are informed by BLS age-specific means, but individual records are simulated.
