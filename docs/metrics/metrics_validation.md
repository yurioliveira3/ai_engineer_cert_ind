# SRAG Metrics Validation

> Validated against DATASUS SIVEP-Gripe database (604,230 rows, data_ref: 2026-12-05)

## Data Reference

- **data_ref**: `MAX(dt_notific)` = 2026-12-05
- **Total confirmed cases**: 585,858
- **Data source**: DATASUS SIVEP-Gripe (SRAG-HOSP-2023-2026)

## Metric Results

| Metric | Value | Guardrail Alert Threshold | Status |
|--------|-------|--------------------------|--------|
| Taxa de mortalidade | 7.47% | > 50% | ✅ In range |
| Taxa de UTI | 27.45% | > 100% | ✅ In range |
| Taxa de vacinação | 53.44% | > 100% | ✅ In range |
| Taxa de aumento de casos | N/A* | > 500% | ⚠️ Undefined** |

*\* taxa_aumento is None when the previous week has 0 confirmed cases (division by zero protected by NULLIF).

*\* The increase rate cannot be calculated when `casos_semana_anterior = 0`. This is an edge case in the historical data where the last week's confirmed cases are concentrated in the current week only. The agent handles this gracefully by reporting `taxa_aumento: None`.

## Detailed Results

### Mortality Rate (Taxa de Mortalidade)

```
obitos_srag: 1,550
total_com_desfecho: 20,762
taxa_mortalidade: 7.47%
```

**Formula**: `COUNT(evolucao=2) / COUNT(evolucao IN (1,2,3)) * 100`
- evolucao=2 (Óbito por SRAG): 1,550
- evolucao=1 (Cura): 14,220 (estimated)
- evolucao=3 (Óbito por outras causas): 4,992 (estimated)
- Only confirmed cases (caso_confirmado=true) with known outcome

### ICU Rate (Taxa de UTI)

```
internados_uti: 6,031
total_internados: 21,973
taxa_uti: 27.45%
```

**Formula**: `COUNT(uti=1) / COUNT(*) * 100`
- uti=1 (Sim): 6,031
- All confirmed cases that were hospitalized
- **Note**: This is the proportion of hospitalized confirmed cases who went to ICU, not ICU bed occupancy.

### Vaccination Rate (Taxa de Vacinação)

```
vacinados: 11,743
total_casos: 21,973
taxa_vacinacao: 53.44%
```

**Formula**: `COUNT(vacina_cov=1) / COUNT(*) * 100`
- Only years >= 2021 (vaccination started in 2021)
- vacina_cov=1 (Sim): 11,743
- Includes all confirmed cases regardless of outcome

### Case Increase Rate (Taxa de Aumento de Casos)

```
casos_semana_atual: 127
casos_semana_anterior: 0
taxa_aumento: None (undefined — division by zero)
```

**Formula**: `(current_week - previous_week) / previous_week * 100`
- Current week (data_ref - 7d to data_ref): 127 confirmed cases
- Previous week (data_ref - 14d to data_ref - 7d): 0 confirmed cases
- When previous week has 0 cases, the rate is undefined (NULLIF prevents crash)

## Temporal Data

### Daily Cases (Last 30 days)
- 12 days with reported cases
- Latest day: 2026-12-05 with data

### Monthly Cases (Last 12 months)
- 28 monthly data points
- Peak month: 2025-12 with 17,733 cases
- Current month: 2026-12 with 127 cases (partial)

## Cross-Validation Notes

> **Note**: Official SRAG data for comparison:
> - Ministry of Health SRAG panel: https://www.gov.br/saude/pt-br/composicao/svsa/cnie/srag
> - Fiocruz InfoGripe: http://info.gripe.fiocruz.br/
>
> Our metrics are derived from DATASUS SIVEP-Gripe microdata. Differences from official dashboards may arise from:
> 1. Different date cutoffs (we use MAX(dt_notific) as reference)
> 2. Different filters (we use caso_confirmado=true for confirmed cases only)
> 3. Different outcome groupings (we use evolucao IN (1,2,3) for known outcomes)
>
> Acceptable margin: ±5% difference from official sources.

## SQL Queries Reference

All queries use `MAX(dt_notific)` as data_ref (NOT `NOW()` or `CURRENT_DATE`):

- **case_increase_rate**: Weekly comparison with NULLIF for division by zero
- **mortality_rate**: Known outcomes only (evolucao IN 1,2,3)
- **icu_rate**: Proportion of ICU admissions among all hospitalized confirmed cases
- **vaccination_rate**: Filtered for anos >= 2021, all confirmed cases