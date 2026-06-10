"""SQL Tool for the SRAG Agent: execute pre-defined metric queries with guardrails."""

import logging

from sqlalchemy import create_engine, text

from src.agent.guardrails import safe_execute
from src.config import Settings
from src.data.queries import METRIC_QUERIES, get_data_ref_query

logger = logging.getLogger(__name__)


def _get_engine(settings: Settings = None):
    """Create a SQLAlchemy engine from settings."""
    if settings is None:
        settings = Settings()
    return create_engine(settings.database_url)


def _resolve_params(params: dict, engine) -> dict:
    """Ensure data_ref is populated if not provided."""
    if "data_ref" not in params or params["data_ref"] is None:
        with engine.connect() as conn:
            result = conn.execute(text(get_data_ref_query()))
            params["data_ref"] = result.scalar()
            logger.info(f"Resolved data_ref: {params['data_ref']}")

    if "data_inicio" not in params:
        data_ref = params["data_ref"]
        if hasattr(data_ref, "replace"):
            params["data_inicio"] = data_ref.replace(year=data_ref.year - 1)
        else:
            params["data_inicio"] = data_ref

    if "data_fim" not in params:
        params["data_fim"] = params["data_ref"]

    return params


def get_data_ref(settings: Settings = None) -> str:
    """Return MAX(dt_notific) from srag_cases as a formatted string."""
    engine = _get_engine(settings)
    with engine.connect() as conn:
        val = conn.execute(text(get_data_ref_query())).scalar()
    return val.strftime("%Y-%m-%d") if val else ""


def execute_tabular_query(
    metric_name: str,
    params: dict | None = None,
    settings: Settings = None,
) -> list[dict]:
    """Execute a metric query and return rows as a list of dicts (raw values).

    Unlike execute_metric_query (which returns a formatted string for the LLM),
    this preserves column structure for chart generation.
    """
    if metric_name not in METRIC_QUERIES:
        return []

    if params is None:
        params = {}

    engine = _get_engine(settings)
    query = METRIC_QUERIES[metric_name]
    params = _resolve_params(params, engine)

    result, _ = safe_execute(query, params, engine)
    if isinstance(result, str) or result.empty:
        return []

    return result.to_dict(orient="records")


def execute_metric_query(
    metric_name: str,
    params: dict | None = None,
    settings: Settings = None,
) -> str:
    """Execute a pre-defined metric query and return formatted results.

    Args:
        metric_name: One of the keys in METRIC_QUERIES.
        params: Optional dict with data_ref, data_inicio, data_fim, uf.
        settings: Optional Settings instance.

    Returns:
        Formatted string with query results.
    """
    if metric_name not in METRIC_QUERIES:
        return f"Unknown metric: {metric_name}. Available: {', '.join(METRIC_QUERIES.keys())}"

    if params is None:
        params = {}

    engine = _get_engine(settings)
    query = METRIC_QUERIES[metric_name]

    # Resolve data_ref from DB if not provided
    params = _resolve_params(params, engine)

    # Execute safely
    result, exec_time = safe_execute(query, params, engine)

    if isinstance(result, str):
        logger.error(f"Metric query {metric_name} blocked or failed: {result}")
        return f"Error executing {metric_name}: {result}"

    if result.empty:
        return f"No data returned for {metric_name}"

    # Format results for LLM consumption
    formatted_lines = [f"Metric: {metric_name}"]
    for _, row in result.iterrows():
        for col in result.columns:
            formatted_lines.append(f"  {col}: {row[col]}")
    formatted_lines.append(f"  Execution time: {exec_time}ms")

    return "\n".join(formatted_lines)
