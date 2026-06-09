"""Pre-defined SQL query templates for SRAG metrics.

All queries use :data_ref and :data_inicio/:data_fim as parameters.
:data_ref defaults to MAX(dt_notific) from the dataset.
"""

QUERY_CASE_INCREASE_RATE = """
WITH semana_atual AS (
    SELECT COUNT(*) as casos FROM srag.srag_cases
    WHERE dt_notific BETWEEN :data_ref - INTERVAL '7 days' AND :data_ref
    AND caso_confirmado = true
),
semana_anterior AS (
    SELECT COUNT(*) as casos FROM srag.srag_cases
    WHERE dt_notific BETWEEN :data_ref - INTERVAL '14 days' AND :data_ref - INTERVAL '7 days'
    AND caso_confirmado = true
)
SELECT sa.casos, sp.casos,
    ROUND(100.0 * (sa.casos - sp.casos) / NULLIF(sp.casos, 0), 2) as taxa_aumento
FROM semana_atual sa, semana_anterior sp
"""

QUERY_MORTALITY_RATE = """
SELECT
    COUNT(*) FILTER (WHERE evolucao = 2) as obitos_srag,
    COUNT(*) FILTER (WHERE evolucao IN (1,2,3)) as total_com_desfecho,
    ROUND(100.0 * COUNT(*) FILTER (WHERE evolucao = 2) /
        NULLIF(COUNT(*) FILTER (WHERE evolucao IN (1,2,3)), 0), 2) as taxa_mortalidade
FROM srag.srag_cases
WHERE caso_confirmado = true
AND dt_notific BETWEEN :data_inicio AND :data_fim
"""

QUERY_ICU_RATE = """
SELECT
    COUNT(*) FILTER (WHERE uti = 1) as internados_uti,
    COUNT(*) as total_internados,
    ROUND(100.0 * COUNT(*) FILTER (WHERE uti = 1) / NULLIF(COUNT(*), 0), 2) as taxa_uti
FROM srag.srag_cases
WHERE caso_confirmado = true
AND dt_notific BETWEEN :data_inicio AND :data_fim
"""

QUERY_VACCINATION_RATE = """
SELECT
    COUNT(*) FILTER (WHERE vacina_cov = 1) as vacinados,
    COUNT(*) as total_casos,
    ROUND(100.0 * COUNT(*) FILTER (WHERE vacina_cov = 1) / NULLIF(COUNT(*), 0), 2) as taxa_vacinacao
FROM srag.srag_cases
WHERE caso_confirmado = true AND ano_notificacao >= 2021
AND dt_notific BETWEEN :data_inicio AND :data_fim
"""

QUERY_DAILY_CASES_30D = """
SELECT
    dt_notific,
    COUNT(*) as casos
FROM srag.srag_cases
WHERE caso_confirmado = true
AND dt_notific BETWEEN :data_ref - INTERVAL '30 days' AND :data_ref
GROUP BY dt_notific
ORDER BY dt_notific
"""

QUERY_MONTHLY_CASES_12M = """
SELECT
    DATE_TRUNC('month', dt_notific) as mes,
    COUNT(*) as casos
FROM srag.srag_cases
WHERE caso_confirmado = true
AND dt_notific BETWEEN :data_ref - INTERVAL '12 months' AND :data_ref
GROUP BY DATE_TRUNC('month', dt_notific)
ORDER BY mes
"""


def get_data_ref_query() -> str:
    """Return query to get the maximum notification date for data_ref."""
    return "SELECT MAX(dt_notific) FROM srag.srag_cases"


METRIC_QUERIES = {
    "case_increase_rate": QUERY_CASE_INCREASE_RATE,
    "mortality_rate": QUERY_MORTALITY_RATE,
    "icu_rate": QUERY_ICU_RATE,
    "vaccination_rate": QUERY_VACCINATION_RATE,
    "daily_cases_30d": QUERY_DAILY_CASES_30D,
    "monthly_cases_12m": QUERY_MONTHLY_CASES_12M,
}
