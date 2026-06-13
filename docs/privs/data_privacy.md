# Data Privacy — SRAG Agent

## Decisions on PII handling

### Columns removed from the dataset

The following PII columns are identified and removed during ETL processing:

| Column | Type | Risk | Action |
|--------|------|------|--------|
| `NM_PACIENT` | Direct identifier | Re-identification | Remove |
| `NU_CPF` | Direct identifier | Re-identification | Remove |
| `NU_CNS` | Direct identifier | Re-identification | Remove |
| `NM_MAE_PAC` | Quasi-identifier | Re-identification | Remove |
| `END_*` (all columns starting with END_) | Quasi-identifier | Re-identification | Remove |

### Columns retained with aggregation

These columns carry re-identification risk when combined, but are essential for epidemiological analysis. They are **never returned as individual records** — only as aggregated statistics:

| Column | Risk | Mitigation |
|--------|------|------------|
| `NU_IDADE_N` | Age can identify individuals when combined with other fields | Output aggregated by age groups |

> **Note**: Columns such as `ID_MN_RESI` (municipality) and `CS_RACA` (race/ethnicity) were evaluated but excluded from `SELECTED_COLUMNS` in `etl.py` — they are never loaded into the database, applying the principle of data minimization at the source.

### LGPD compliance

- **Legal basis**: DATASUS data is publicly available under the Open Data policy (Portaria GM/MS No. 1.119/2022)
- **Purpose limitation**: Data is used exclusively for epidemiological surveillance and reporting
- **Minimization**: Only columns relevant to the specified metrics are loaded
- **Anonymization in outputs**: All agent outputs present aggregated data, never individual records
- **No cross-referencing**: Patient data is not combined with external datasets

### Output guardrails

- The SQL tool only returns aggregated values (COUNT, rates)
- The PII filter in `guardrails.py` masks CPF, phone numbers, and emails in any LLM output
- Reports display data by state, age group, and time period — never individual records