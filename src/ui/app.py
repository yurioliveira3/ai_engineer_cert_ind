"""SRAG Agent — Streamlit Dashboard.

Epidemiological report generator with LLM analysis, charts, and news context.
"""

from __future__ import annotations

import os
from datetime import date

import streamlit as st

from src.agent.orchestrator import SRAGAgent, create_agent
from src.config import Settings

# ─── Metric labels (Portuguese) ──────────────────────────────────────────────

METRIC_LABELS = {
    "mortality_rate": "Taxa de Mortalidade",
    "icu_rate": "Taxa de UTI",
    "vaccination_rate": "Taxa de Vacinação",
    "case_increase_rate": "Aumento de Casos",
}

# ─── Helper functions ──────────────────────────────────────────────────────────


def format_metric_value(value) -> str:
    """Format a metric value for display.

    Handles float percentages, None (N/A), dicts with rate keys, and error dicts.
    """
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.2f}%"
    if isinstance(value, dict):
        if "error" in value:
            return "⚠️ Erro"
        # Try known rate keys
        for key in ["taxa_mortalidade", "taxa_uti", "taxa_vacinacao", "taxa_aumento"]:
            if key in value:
                return format_metric_value(value[key])
        # Fallback: return first numeric value found
        for v in value.values():
            if isinstance(v, (int, float)):
                return f"{v:.2f}%"
        return "N/A"
    return str(value)


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
            formatted = format_metric_value(value)
            cols[i].metric(label=metric_label, value=formatted)

    # ─── Charts ────────────────────────────────────────────────────────────
    charts = report.get("charts", {})
    if charts:
        st.subheader("📈 Gráficos")

        # Try to use Plotly figures directly from charts if available,
        # fallback to displaying PNG files
        daily_path = charts.get("daily", "")
        monthly_path = charts.get("monthly", "")

        chart_cols = st.columns(2)

        if daily_path and os.path.exists(daily_path):
            with chart_cols[0]:
                st.image(daily_path, caption="Casos diários — Últimos 30 dias")

        if monthly_path and os.path.exists(monthly_path):
            with chart_cols[1]:
                st.image(monthly_path, caption="Casos mensais — Últimos 12 meses")

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
