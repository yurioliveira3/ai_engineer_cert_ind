"""SRAG Agent Orchestrator: LangGraph StateGraph with sequential node execution.

Nodes call audit_logger.log_decision() directly (rather than via a decorator):
LangGraph nodes receive (state, settings, audit_logger) and benefit from explicit
control over step/tool/input/output per node.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy import create_engine

from src.agent.guardrails import validate_metrics, validate_output_pii, validate_user_input
from src.agent.logging_config import AgentAuditLogger, setup_logger
from src.agent.prompts import render_prompt
from src.agent.tools.chart_tool import generate_daily_cases_chart, generate_monthly_cases_chart
from src.agent.tools.news_tool import search_and_index_news, semantic_search_news
from src.agent.tools.report_tool import generate_report
from src.agent.tools.sql_tool import execute_metric_query, execute_tabular_query, get_data_ref
from src.config import Settings
from src.llm.adapter import get_chat_model, get_token_usage, safe_invoke

logger = logging.getLogger(__name__)

METRIC_NAMES = [
    "case_increase_rate",
    "mortality_rate",
    "icu_rate",
    "vaccination_rate",
]

# UF code -> full state name, used to regionalise the news search term
# (web search works better with the full name than with the two-letter code).
UF_NAMES = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}


class AgentState(TypedDict):
    """State for the SRAG Agent LangGraph."""

    messages: Annotated[list, add_messages]
    metrics: dict
    charts: dict
    news: list
    news_semantic: list
    analysis: str
    report_markdown: str
    report_pdf_path: str
    error: str | None
    session_id: str
    # UI filters (optional): notifying state (UF) and reference date. When
    # absent, the agent uses the whole country and MAX(dt_notific).
    uf: str | None
    data_ref: str | None


def _filter_params(state: AgentState) -> dict:
    """Build SQL query params from the UI filters carried in the state.

    May contain ``uf`` (notifying state) and ``data_ref`` (reference date).
    Empty when no filter is active (whole country, latest available date).
    """
    params: dict = {}
    uf = state.get("uf")
    if uf and uf != "Todos":
        params["uf"] = uf
    data_ref = state.get("data_ref")
    if data_ref:
        params["data_ref"] = data_ref
    return params


def _news_query(state: AgentState) -> str:
    """Build the news search query.

    Regionalised by the UF filter when set (e.g. "SRAG São Paulo epidemiologia");
    otherwise derived from the user message (validated against prompt injection)
    with a national fallback.
    """
    uf = state.get("uf")
    if uf and uf != "Todos":
        return f"SRAG {UF_NAMES.get(uf, uf)} epidemiologia"

    user_msg = ""
    for msg in state.get("messages", []):
        if hasattr(msg, "type") and msg.type == "human":
            user_msg = msg.content
            break
        if isinstance(msg, tuple) and msg[0] == "user":
            user_msg = msg[1]
            break

    query = user_msg or "SRAG Brasil epidemiologia"
    try:
        return validate_user_input(query)
    except ValueError:
        return "SRAG Brasil epidemiologia"


def calculate_metrics(
    state: AgentState, settings: Settings, audit_logger: AgentAuditLogger
) -> dict:
    """Execute all 4 metric SQL queries and daily/monthly temporal queries."""
    metrics: dict[str, Any] = {}
    start = time.time()
    base_params = _filter_params(state)
    logger.info(
        "[node] calculate_metrics: %d queries de metricas (uf=%s, data_ref=%s)",
        len(METRIC_NAMES),
        base_params.get("uf", "Todos"),
        base_params.get("data_ref", "MAX(dt_notific)"),
    )

    for metric_name in METRIC_NAMES:
        try:
            result_text = execute_metric_query(
                metric_name, params=dict(base_params), settings=settings
            )
            metrics[metric_name] = _parse_metric_result(result_text)
        except Exception as e:
            logger.warning(f"Metric {metric_name} failed: {e}")
            metrics[metric_name] = {"error": str(e)[:200]}

    if base_params.get("data_ref"):
        metrics["data_ref"] = str(base_params["data_ref"])
    else:
        metrics["data_ref"] = get_data_ref(settings, uf=base_params.get("uf"))

    # Validate metric ranges
    validated = validate_metrics(metrics)

    duration_ms = int((time.time() - start) * 1000)
    audit_logger.log_decision(
        step="calculate_metrics",
        tool="sql_tool",
        input_summary=f"{len(METRIC_NAMES)} metric queries",
        output_summary="metrics retrieved" if "error" not in str(metrics) else "some errors",
        duration_ms=duration_ms,
        success=True,
    )

    return {"metrics": validated}


def generate_charts(state: AgentState, settings: Settings, audit_logger: AgentAuditLogger) -> dict:
    """Generate daily and monthly case charts."""
    charts = {}
    start = time.time()
    base_params = _filter_params(state)
    logger.info(
        "[node] generate_charts: graficos diario (30d) e mensal (12m) (uf=%s)",
        base_params.get("uf", "Todos"),
    )

    data_ref = str(state.get("metrics", {}).get("data_ref", ""))

    try:
        daily_data = execute_tabular_query(
            "daily_cases_30d", params=dict(base_params), settings=settings
        )
        daily_path, daily_fig = generate_daily_cases_chart(daily_data, data_ref=data_ref)
        charts["daily"] = {"path": daily_path, "fig_json": daily_fig.to_json()}
    except Exception as e:
        logger.warning(f"Daily chart failed: {e}")
        charts["daily"] = {"path": "", "fig_json": ""}

    try:
        monthly_raw = execute_tabular_query(
            "monthly_cases_12m", params=dict(base_params), settings=settings
        )
        # monthly query returns column "mes"; chart expects "dt_notific"
        monthly_data = [{"dt_notific": r.get("mes"), "casos": r.get("casos")} for r in monthly_raw]
        monthly_path, monthly_fig = generate_monthly_cases_chart(monthly_data, data_ref=data_ref)
        charts["monthly"] = {"path": monthly_path, "fig_json": monthly_fig.to_json()}
    except Exception as e:
        logger.warning(f"Monthly chart failed: {e}")
        charts["monthly"] = {"path": "", "fig_json": ""}

    duration_ms = int((time.time() - start) * 1000)
    audit_logger.log_decision(
        step="generate_charts",
        tool="chart_tool",
        input_summary="temporal queries + chart generation",
        output_summary=f"daily={bool(charts.get('daily'))}, monthly={bool(charts.get('monthly'))}",
        duration_ms=duration_ms,
        success=True,
    )

    return {"charts": charts}


def search_news_step(state: AgentState, settings: Settings, audit_logger: AgentAuditLogger) -> dict:
    """Search and index SRAG-related news from DuckDuckGo."""
    start = time.time()

    try:
        query = _news_query(state)
        # news_max_searches controls how many news items are fetched; clamp to the
        # guardrail limit (search_and_index_news rejects max_results > 5).
        max_results = min(settings.news_max_searches, 5)
        logger.info("[node] search_news: buscando noticias (query=%r, max=%d)", query, max_results)
        news = search_and_index_news(query, max_results=max_results, settings=settings)

        duration_ms = int((time.time() - start) * 1000)
        audit_logger.log_decision(
            step="search_news",
            tool="news_tool",
            input_summary=f"query='{query[:50]}'",
            output_summary=f"{len(news)} results",
            duration_ms=duration_ms,
            success=True,
        )

        return {"news": news}
    except Exception as e:
        logger.warning(f"News search failed: {e}")
        duration_ms = int((time.time() - start) * 1000)
        audit_logger.log_decision(
            step="search_news",
            tool="news_tool",
            input_summary="news search",
            output_summary=f"error: {str(e)[:100]}",
            duration_ms=duration_ms,
            success=False,
        )
        return {"news": []}


def retrieve_semantic(
    state: AgentState, settings: Settings, audit_logger: AgentAuditLogger
) -> dict:
    """Retrieve semantically similar news from pgvector index."""
    start = time.time()

    try:
        query = _news_query(state)
        logger.info("[node] retrieve_semantic: busca semantica no pgvector (k=3, query=%r)", query)
        news_semantic = semantic_search_news(query, k=3, settings=settings)

        duration_ms = int((time.time() - start) * 1000)
        audit_logger.log_decision(
            step="retrieve_semantic",
            tool="pgvector",
            input_summary="semantic search",
            output_summary=f"{len(news_semantic)} results",
            duration_ms=duration_ms,
            success=True,
        )

        return {"news_semantic": news_semantic}
    except Exception as e:
        logger.warning(f"Semantic retrieval failed: {e}")
        duration_ms = int((time.time() - start) * 1000)
        audit_logger.log_decision(
            step="retrieve_semantic",
            tool="pgvector",
            input_summary="semantic search",
            output_summary=f"error: {str(e)[:100]}",
            duration_ms=duration_ms,
            success=False,
        )
        return {"news_semantic": []}


def analyze(state: AgentState, settings: Settings, audit_logger: AgentAuditLogger) -> dict:
    """Use LLM to analyze metrics and generate insights."""
    start = time.time()
    logger.info("[node] analyze: invocando LLM para analise de metricas + noticias")

    try:
        metrics = state.get("metrics", {})
        news = state.get("news", [])
        news_consolidated = "\n".join(
            f"- {n.get('title', '')} ({n.get('source', 'unknown')}): {n.get('snippet', '')}"
            for n in news[:5]
        )

        data_ref = str(metrics.get("data_ref", ""))
        data_hora_consulta = time.strftime("%Y-%m-%d %H:%M:%S")

        prompt, prompt_hash = render_prompt(
            "analyze_metrics",
            payload=str(metrics),
            news_consolidated=news_consolidated,
            data_ref=data_ref,
            data_hora_consulta=data_hora_consulta,
        )

        model = get_chat_model(settings)
        response = safe_invoke(model, prompt)
        tokens_in, tokens_out = get_token_usage(response, prompt)

        # Log LLM call
        audit_logger.log_llm_call(
            prompt_name="analyze_metrics",
            prompt_file="analyze_metrics.txt",
            prompt_hash=prompt_hash,
            response_summary=response.content[:200],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=int((time.time() - start) * 1000),
        )

        analysis = validate_output_pii(response.content)

        duration_ms = int((time.time() - start) * 1000)
        audit_logger.log_decision(
            step="analyze",
            tool="llm",
            input_summary="metrics + news payload",
            output_summary=f"analysis {len(analysis)} chars",
            duration_ms=duration_ms,
            success=True,
        )

        return {"analysis": analysis}
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        duration_ms = int((time.time() - start) * 1000)
        audit_logger.log_decision(
            step="analyze",
            tool="llm",
            input_summary="metrics + news payload",
            output_summary=f"error: {str(e)[:100]}",
            duration_ms=duration_ms,
            success=False,
        )
        return {"analysis": f"Análise indisponível: erro durante processamento ({str(e)[:100]})"}


def compile_report(state: AgentState, settings: Settings, audit_logger: AgentAuditLogger) -> dict:
    """Compile the final report from all gathered data."""
    start = time.time()
    logger.info("[node] compile_report: compilando relatorio final (markdown + PDF)")

    try:
        metrics = state.get("metrics", {})
        news = state.get("news", [])
        analysis = state.get("analysis", "")
        data_ref = str(metrics.get("data_ref", ""))

        report = generate_report(
            metrics=metrics,
            news=news,
            analysis=analysis,
            data_ref=data_ref,
        )

        duration_ms = int((time.time() - start) * 1000)
        audit_logger.log_decision(
            step="compile_report",
            tool="report_tool",
            input_summary="all data",
            output_summary=f"report {len(report.get('markdown', ''))} chars",
            duration_ms=duration_ms,
            success=True,
        )

        return {
            "report_markdown": report["markdown"],
            "report_pdf_path": report["pdf_path"],
        }
    except Exception as e:
        logger.error(f"Report compilation failed: {e}")
        duration_ms = int((time.time() - start) * 1000)
        audit_logger.log_decision(
            step="compile_report",
            tool="report_tool",
            input_summary="all data",
            output_summary=f"error: {str(e)[:100]}",
            duration_ms=duration_ms,
            success=False,
        )
        return {
            "report_markdown": f"Erro ao gerar relatório: {e!s}",
            "report_pdf_path": "",
            "error": str(e),
        }


def _parse_metric_result(result_text: str) -> dict:
    """Parse the string output from execute_metric_query into a dict."""
    result: dict[str, Any] = {}
    for line in result_text.strip().split("\n"):
        if "Execution time" in line or line.startswith("Metric:"):
            continue
        if ":" in line:
            key, _, raw = line.strip().partition(":")
            key = key.strip()
            raw = raw.strip()
            if raw in ("None", "NaN", "null", ""):
                result[key] = None
                continue
            try:
                num = float(raw)
                if math.isnan(num) or math.isinf(num):
                    result[key] = None
                    continue
                result[key] = num
            except ValueError:
                result[key] = raw
    return result


def create_agent(settings: Settings | None = None):
    """Create and compile the SRAG Agent LangGraph.

    Args:
        settings: Optional Settings instance.

    Returns:
        Compiled LangGraph agent ready for .invoke().
        The agent is wrapped to start and end audit sessions automatically.
    """
    settings = settings or Settings()
    log_level = getattr(logging, str(settings.log_level).upper(), logging.INFO)
    setup_logger(level=log_level)
    logger.info(
        "Inicializando agente SRAG (provider=%s, model=%s)",
        settings.llm_provider,
        settings.llm_model,
    )

    engine = create_engine(settings.database_url)
    audit_logger = AgentAuditLogger(
        engine=engine,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
    )

    # Build the graph
    graph = StateGraph(AgentState)

    def _calculate_metrics(state):
        return calculate_metrics(state, settings, audit_logger)

    def _generate_charts(state):
        return generate_charts(state, settings, audit_logger)

    def _search_news(state):
        return search_news_step(state, settings, audit_logger)

    def _retrieve_semantic(state):
        return retrieve_semantic(state, settings, audit_logger)

    def _analyze(state):
        return analyze(state, settings, audit_logger)

    def _compile_report(state):
        return compile_report(state, settings, audit_logger)

    graph.add_node("calculate_metrics", _calculate_metrics)
    graph.add_node("generate_charts", _generate_charts)
    graph.add_node("search_news", _search_news)
    graph.add_node("retrieve_semantic", _retrieve_semantic)
    graph.add_node("analyze", _analyze)
    graph.add_node("compile_report", _compile_report)

    # Sequential edges
    graph.set_entry_point("calculate_metrics")
    graph.add_edge("calculate_metrics", "generate_charts")
    graph.add_edge("generate_charts", "search_news")
    graph.add_edge("search_news", "retrieve_semantic")
    graph.add_edge("retrieve_semantic", "analyze")
    graph.add_edge("analyze", "compile_report")
    graph.add_edge("compile_report", END)

    compiled = graph.compile()
    return SRAGAgent(compiled, audit_logger)


class SRAGAgent:
    """Wrapper around compiled LangGraph that manages audit sessions."""

    def __init__(self, graph, audit_logger: AgentAuditLogger):
        self.graph = graph
        self.audit_logger = audit_logger

    def invoke(self, input_data: dict) -> dict:
        """Start session, run the graph, end session, return result."""
        self.audit_logger.start_session()
        try:
            result = self.graph.invoke(input_data)
            self.audit_logger.end_session(status="success")
            return result
        except Exception as e:
            self.audit_logger.end_session(status="failed", error=str(e)[:500])
            raise
