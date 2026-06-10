"""Pre-defined SQL query templates for SRAG metrics.

All queries use :data_ref and :data_inicio/:data_fim as parameters.
:data_ref defaults to MAX(dt_notific) from the dataset.
An optional :uf parameter filters by notifying state (sg_uf_not); when it is
NULL the whole country is considered.
"""

QUERY_CASE_INCREASE_RATE = """
WITH semana_atual AS (
    SELECT COUNT(*) as casos FROM srag.srag_cases
    WHERE dt_notific BETWEEN :data_ref - INTERVAL '7 days' AND :data_ref
    AND caso_confirmado = true
    AND (:uf IS NULL OR sg_uf_not = :uf)
),
semana_anterior AS (
    SELECT COUNT(*) as casos FROM srag.srag_cases
    WHERE dt_notific BETWEEN :data_ref - INTERVAL '14 days' AND :data_ref - INTERVAL '7 days'
    AND caso_confirmado = true
    AND (:uf IS NULL OR sg_uf_not = :uf)
)
SELECT sa.casos as casos_semana_atual, sp.casos as casos_semana_anterior,
    CASE
        WHEN sp.casos = 0 AND sa.casos = 0 THEN 0
        WHEN sp.casos = 0 THEN NULL
        ELSE ROUND(100.0 * (sa.casos - sp.casos) / sp.casos, 2)
    END as taxa_aumento
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
AND (:uf IS NULL OR sg_uf_not = :uf)
"""

QUERY_ICU_RATE = """
SELECT
    COUNT(*) FILTER (WHERE uti = 1) as internados_uti,
    COUNT(*) as total_internados,
    ROUND(100.0 * COUNT(*) FILTER (WHERE uti = 1) / NULLIF(COUNT(*), 0), 2) as taxa_uti
FROM srag.srag_cases
WHERE caso_confirmado = true
AND dt_notific BETWEEN :data_inicio AND :data_fim
AND (:uf IS NULL OR sg_uf_not = :uf)
"""

QUERY_VACCINATION_RATE = """
SELECT
    COUNT(*) FILTER (WHERE vacina_cov = 1) as vacinados,
    COUNT(*) as total_casos,
    ROUND(100.0 * COUNT(*) FILTER (WHERE vacina_cov = 1) / NULLIF(COUNT(*), 0), 2) as taxa_vacinacao
FROM srag.srag_cases
WHERE caso_confirmado = true AND ano_notificacao >= 2021
AND dt_notific BETWEEN :data_inicio AND :data_fim
AND (:uf IS NULL OR sg_uf_not = :uf)
"""

QUERY_DAILY_CASES_30D = """
SELECT
    dt_notific,
    COUNT(*) as casos
FROM srag.srag_cases
WHERE caso_confirmado = true
AND dt_notific BETWEEN :data_ref - INTERVAL '30 days' AND :data_ref
AND (:uf IS NULL OR sg_uf_not = :uf)
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
AND (:uf IS NULL OR sg_uf_not = :uf)
GROUP BY DATE_TRUNC('month', dt_notific)
ORDER BY mes
"""


def get_data_ref_query() -> str:
    """Return query for the maximum notification date, optionally per state.

    Uses a :uf bind (NULL = whole country) so the reference date reflects the
    latest notification available for the selected scope.
    """
    return "SELECT MAX(dt_notific) FROM srag.srag_cases WHERE (:uf IS NULL OR sg_uf_not = :uf)"


METRIC_QUERIES = {
    "case_increase_rate": QUERY_CASE_INCREASE_RATE,
    "mortality_rate": QUERY_MORTALITY_RATE,
    "icu_rate": QUERY_ICU_RATE,
    "vaccination_rate": QUERY_VACCINATION_RATE,
    "daily_cases_30d": QUERY_DAILY_CASES_30D,
    "monthly_cases_12m": QUERY_MONTHLY_CASES_12M,
}
