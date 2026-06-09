"""Report generation tool — Markdown + PDF output for SRAG analysis."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from fpdf import FPDF

logger = logging.getLogger(__name__)

METRIC_LABELS = {
    "case_increase_rate": "Taxa de aumento de casos",
    "mortality_rate": "Taxa de mortalidade",
    "icu_rate": "Taxa de ocupação de UTI",
    "vaccination_rate": "Taxa de vacinação",
}


_NON_LATIN1_REPLACEMENTS = {
    "\u2014": "-",  # em dash
    "\u2013": "-",  # en dash
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u2026": "...",  # ellipsis
}


def _sanitize_for_latin1(text: str) -> str:
    for char, replacement in _NON_LATIN1_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        text = text.encode("latin-1", errors="replace").decode("latin-1")
    return text


class _SRAGReport(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._font_loaded = False
        try:
            dejavu_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(dejavu_path):
                self.add_font("DejaVu", "", dejavu_path, uni=True)
                self._font_loaded = True
        except Exception:
            logger.debug("DejaVu font not available, falling back to Helvetica")

    def _t(self, text: str) -> str:
        if not self._font_loaded:
            return _sanitize_for_latin1(text)
        return text

    def header(self):
        if self._font_loaded:
            self.set_font("DejaVu", "", 14)
        else:
            self.set_font("Helvetica", "", 14)
        self.cell(0, 10, self._t("Relatório SRAG"), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        if self._font_loaded:
            self.set_font("DejaVu", "", 8)
        else:
            self.set_font("Helvetica", "", 8)
        self.cell(
            0, 10, self._t(f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), align="C"
        )

    def _use_font(self, size: int):
        if self._font_loaded:
            self.set_font("DejaVu", "", size)
        else:
            self.set_font("Helvetica", "", size)

    def add_metrics(self, metrics: dict):
        self._use_font(11)
        self.cell(0, 8, self._t("Métricas"), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self._use_font(9)
        for key, label in METRIC_LABELS.items():
            value = metrics.get(key, "N/A")
            self.cell(0, 6, self._t(f"  {label}: {value}"), new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def add_analysis(self, analysis: str):
        self._use_font(11)
        self.cell(0, 8, self._t("Resumo Executivo"), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self._use_font(9)
        self.multi_cell(0, 6, self._t(analysis))
        self.ln(4)

    def add_news(self, news: list[dict]):
        if not news:
            return
        self._use_font(11)
        self.cell(0, 8, self._t("Contexto - Notícias recentes"), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self._use_font(9)
        for item in news:
            source_tag = "verificada" if item.get("source") == "trusted" else "não-verificada"
            title = item.get("title", "Sem título")
            self.cell(0, 6, self._t(f"  [{source_tag}] {title}"), new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def add_data_ref(self, data_ref: str):
        self._use_font(9)
        self.cell(0, 6, self._t(f"Fontes: {data_ref}"), new_x="LMARGIN", new_y="NEXT")


def _build_markdown(
    metrics: dict,
    charts: dict,
    news: list[dict],
    analysis: str,
    data_ref: str,
) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = []
    lines.append(f"# Relatório SRAG — {date_str}")
    lines.append("")

    lines.append("## Resumo Executivo")
    lines.append("")
    lines.append(analysis)
    lines.append("")

    lines.append("## Métricas")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---|---|")
    for key, label in METRIC_LABELS.items():
        value = metrics.get(key, "N/A")
        lines.append(f"| {label} | {value} |")
    lines.append("")

    lines.append("## Charts")
    lines.append("")
    daily = charts.get("daily", "")
    monthly = charts.get("monthly", "")
    if daily:
        lines.append(f"![Daily cases]({daily})")
    if monthly:
        lines.append(f"![Monthly cases]({monthly})")
    lines.append("")

    if news:
        lines.append("## Contexto — Notícias recentes")
        lines.append("")
        for item in news:
            source_tag = "verificada" if item.get("source") == "trusted" else "não-verificada"
            title = item.get("title", "Sem título")
            url = item.get("url", "")
            lines.append(f"- [{source_tag}] {title} — {url}")
        lines.append("")

    lines.append("## Fontes")
    lines.append("")
    lines.append(data_ref)
    lines.append("")

    lines.append("---")
    lines.append(f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    return "\n".join(lines)


def generate_report(
    metrics: dict,
    charts: dict,
    news: list[dict],
    analysis: str,
    data_ref: str,
    output_dir: str | None = None,
) -> dict:
    md = _build_markdown(metrics, charts, news, analysis, data_ref)

    pdf_path = ""
    try:
        if output_dir is None:
            output_dir = "data/reports"
        os.makedirs(output_dir, exist_ok=True)

        pdf = _SRAGReport()
        pdf.add_page()
        pdf.add_analysis(analysis)
        pdf.add_metrics(metrics)
        pdf.add_news(news)
        pdf.add_data_ref(data_ref)

        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"srag_report_{date_str}.pdf"
        pdf_path = os.path.join(output_dir, filename)
        pdf.output(pdf_path)
    except Exception:
        logger.exception("PDF generation failed, falling back to markdown-only")
        pdf_path = ""

    return {"markdown": md, "pdf_path": pdf_path}
