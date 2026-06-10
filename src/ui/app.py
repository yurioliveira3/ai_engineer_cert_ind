"""SRAG Agent — Streamlit Dashboard.

Epidemiological report generator with LLM analysis, charts, and news context.
"""

from __future__ import annotations

import os
from datetime import date

import plotly.io as pio
import streamlit as st

from src.agent.orchestrator import SRAGAgent, create_agent
from src.agent.tools.report_tool import metric_value_parts
from src.config import Settings

# ─── Metric labels (Portuguese) ──────────────────────────────────────────────

METRIC_LABELS = {
    "mortality_rate": "Taxa de Mortalidade",
    "icu_rate": "Taxa de UTI",
    "vaccination_rate": "Taxa de Vacinação",
    "case_increase_rate": "Aumento de Casos",
}

# metric_value_parts is imported from report_tool so the UI and the generated
# report render metrics consistently (rates as %, absolute variation fallback).


def run_agent(settings: Settings) -> dict:
    """Create and run the SRAG agent, returning the full result state.

    Args:
        settings: Application settings for DB and LLM configuration.

    Returns:
        Dict with report_markdown, report_pdf_path, metrics, charts, etc.

    Raises:
        RuntimeError: If the agent fails to execute.
    """
    agent: SRAGAgent = create_agent(settings)
    result = agent.invoke({"messages": [("user", "Gere o relatório SRAG")]})
    return result


# ─── Page configuration ────────────────────────────────────────────────────────


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="SRAG Agent",
        page_icon="🦠",
        layout="wide",
    )

    st.title("🦠 SRAG Agent — Relatório Epidemiológico")
    st.markdown(
        "Gere relatórios automatizados de vigilância epidemiológica para SRAG "
        "com dados do DATASUS, análise via LLM e contexto de notícias."
    )

    # ─── Sidebar ───────────────────────────────────────────────────────────
    st.sidebar.header("⚙️ Configurações")

    llm_provider = st.sidebar.selectbox(
        "Provedor LLM",
        options=["gemini"],
        index=0,
        help="Provedor de modelo de linguagem. Atualmente apenas Gemini.",
    )

    llm_model = st.sidebar.selectbox(
        "Modelo",
        options=["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
        help="Modelo de linguagem para análise. Flash é mais rápido, Pro é mais preciso.",
    )

    uf = st.sidebar.selectbox(
        "UF (Unidade Federativa)",
        options=[
            "Todos",
            "AC",
            "AL",
            "AM",
            "AP",
            "BA",
            "CE",
            "DF",
            "ES",
            "GO",
            "MA",
            "MG",
            "MS",
            "MT",
            "PA",
            "PB",
            "PE",
            "PI",
            "PR",
            "RJ",
            "RN",
            "RO",
            "RR",
            "RS",
            "SC",
            "SE",
            "SP",
            "TO",
        ],
        index=0,
        help="Filtrar dados por estado. 'Todos' inclui todo o Brasil.",
    )

    data_ref = st.sidebar.date_input(
        "Data de referência",
        value=None,
        help="Deixe vazio para usar MAX(dt_notific) do dataset.",
    )

    # ─── Main content ────────────────────────────────────────────────────
    if st.sidebar.button("🚀 Gerar Relatório", type="primary", use_container_width=True):
        settings = Settings(
            llm_provider=llm_provider,
            llm_model=llm_model,
        )

        with st.spinner("Gerando relatório... Isso pode levar até 1 minuto."):
            try:
                result = run_agent(settings)
                st.session_state["report"] = result
                st.session_state["error"] = None
            except Exception as e:
                st.session_state["error"] = str(e)
                st.error(f"Erro ao gerar relatório: {e}")
                return

    # ─── Display results ──────────────────────────────────────────────────
    if st.session_state.get("error"):
        st.error(f"❌ Erro: {st.session_state['error']}")
        return

    report = st.session_state.get("report")
    if report is None:
        st.info("Clique em **Gerar Relatório** para começar.")
        return

    # ─── Metrics ───────────────────────────────────────────────────────────
    metrics = report.get("metrics", {})
    if metrics:
        st.subheader("📊 Métricas")
        cols = st.columns(4)
        for i, (metric_key, metric_label) in enumerate(METRIC_LABELS.items()):
            value = metrics.get(metric_key, {})
            main, detail = metric_value_parts(value)
            with cols[i]:
                st.metric(label=metric_label, value=main)
                # When there is no percentage base, show the explanatory note
                # below the value (smaller font) instead of truncating it.
                if detail:
                    st.caption(detail)

    # ─── Charts ────────────────────────────────────────────────────────────
    charts = report.get("charts", {})

    def _render_chart(col, info, caption):
        """Render a chart from fig_json (preferred) or PNG path (fallback)."""
        fig_json = info.get("fig_json", "") if isinstance(info, dict) else ""
        path = info.get("path", "") if isinstance(info, dict) else info
        with col:
            if fig_json:
                st.plotly_chart(pio.from_json(fig_json), use_container_width=True)
            elif path and os.path.exists(path):
                st.image(path, caption=caption)

    daily_info = charts.get("daily", {})
    monthly_info = charts.get("monthly", {})
    has_daily = bool(
        (isinstance(daily_info, dict) and (daily_info.get("fig_json") or daily_info.get("path")))
        or (isinstance(daily_info, str) and daily_info)
    )
    has_monthly = bool(
        (isinstance(monthly_info, dict) and (monthly_info.get("fig_json") or monthly_info.get("path")))
        or (isinstance(monthly_info, str) and monthly_info)
    )

    if has_daily or has_monthly:
        st.subheader("📈 Gráficos")
        chart_cols = st.columns(2)
        _render_chart(chart_cols[0], daily_info, "Casos diários — Últimos 30 dias")
        _render_chart(chart_cols[1], monthly_info, "Casos mensais — Últimos 12 meses")

    # ─── Report body ───────────────────────────────────────────────────────
    report_markdown = report.get("report_markdown", "")
    if report_markdown:
        st.subheader("📄 Relatório")
        st.markdown(report_markdown)

    # ─── PDF download ───────────────────────────────────────────────────────
    report_pdf_path = report.get("report_pdf_path", "")
    if report_pdf_path and os.path.exists(report_pdf_path):
        with open(report_pdf_path, "rb") as f:
            pdf_data = f.read()

        timestamp = date.today().isoformat()
        st.download_button(
            label="📥 Baixar relatório em PDF",
            data=pdf_data,
            file_name=f"relatorio_srag_{timestamp}.pdf",
            mime="application/pdf",
        )

    # ─── Audit expander ────────────────────────────────────────────────────
    with st.expander("🔍 Auditoria — Decisões do agente"):
        analysis = report.get("analysis", "")
        if analysis:
            st.markdown("### Análise LLM")
            st.markdown(analysis)

        news = report.get("news", [])
        if news:
            st.markdown("### Notícias recuperadas")
            for i, item in enumerate(news[:10], 1):
                title = item.get("title", "Sem título")
                url = item.get("url", "#")
                source = item.get("source", "Fonte desconhecida")
                st.markdown(f"{i}. [{title}]({url}) — _{source}_")

        st.markdown("### Configuração")
        st.json(
            {
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "uf": uf,
                "data_ref": str(data_ref) if data_ref else "MAX(dt_notific)",
            }
        )


if __name__ == "__main__":
    main()
