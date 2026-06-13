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

_RATE_KEYS = ("taxa_mortalidade", "taxa_uti", "taxa_vacinacao", "taxa_aumento")


def metric_value_parts(value) -> tuple[str, str]:
    """Split a metric into ``(main, detail)`` for display.

    ``main`` is the headline figure (e.g. ``"7.47%"`` or ``"+127 casos"``);
    ``detail`` is an optional smaller note (e.g. ``"sem base p/ %"``) or ``""``.
    The UI renders ``detail`` below the value in a smaller font; the report
    joins both into a single line. Falls back to ``"0.00%"`` when no usable
    value is available.
    """
    if value is None or isinstance(value, bool):
        return "0.00%", ""
    if isinstance(value, (int, float)):
        return f"{value:.2f}%", ""
    if isinstance(value, dict):
        if "error" in value:
            return "Erro", ""
        for key in _RATE_KEYS:
            if key in value:
                rate = value[key]
                if rate is not None:
                    return f"{float(rate):.2f}%", ""
                # No percentage base (previous week = 0 cases): report the
                # absolute weekly variation plus an explanatory note.
                atual = value.get("casos_semana_atual")
                anterior = value.get("casos_semana_anterior")
                if atual is not None and anterior is not None:
                    delta = int(atual) - int(anterior)
                    return f"{delta:+d} casos", "sem base p/ %"
                return "0.00%", ""
        # Unknown dict shape: use the first numeric value if any.
        for v in value.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return f"{v:.2f}%", ""
        return "0.00%", ""
    return str(value), ""


def format_metric_value(value) -> str:
    """Single-line metric rendering for the report (markdown / PDF)."""
    main, detail = metric_value_parts(value)
    return f"{main} ({detail})" if detail else main


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
    """PDF report builder for SRAG analysis with Latin-1 fallback support."""

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.alias_nb_pages()
        self._font_loaded = False
        try:
            dejavu_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(dejavu_path):
                self.add_font("DejaVu", "", dejavu_path, uni=True)  # type: ignore[call-arg]
                self._font_loaded = True
        except Exception:
            logger.debug("DejaVu font not available, falling back to Helvetica")

    def _t(self, text: str) -> str:
        if not self._font_loaded:
            return _sanitize_for_latin1(text)
        return text

    def header(self):
        """Render the report header with title on every page."""
        if self._font_loaded:
            self.set_font("DejaVu", "", 14)
        else:
            self.set_font("Helvetica", "", 14)
        self.cell(0, 10, self._t("Relatório SRAG"), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        """Render the report footer with timestamp and page number on every page."""
        self.set_y(-15)
        if self._font_loaded:
            self.set_font("DejaVu", "", 8)
        else:
            self.set_font("Helvetica", "", 8)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        page_num = f"Página {self.page_no()} de {{nb}}"
        self.cell(0, 10, self._t(f"Gerado em: {timestamp} | {page_num}"), align="C")

    def _use_font(self, size: int):
        if self._font_loaded:
            self.set_font("DejaVu", "", size)
        else:
            self.set_font("Helvetica", "", size)

    def add_metrics(self, metrics: dict):
        """Add a metrics section to the PDF.

        Args:
            metrics: Dict mapping metric keys to numeric values.
        """
        self._use_font(11)
        self.cell(0, 8, self._t("Métricas"), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self._use_font(9)
        for key, label in METRIC_LABELS.items():
            value = format_metric_value(metrics.get(key))
            self.cell(0, 6, self._t(f"  {label}: {value}"), new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def add_analysis(self, analysis: str):
        """Add an executive summary section to the PDF.

        Args:
            analysis: Text content of the executive summary.
        """
        self._use_font(11)
        self.cell(0, 8, self._t("Resumo Executivo"), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self._use_font(9)
        self.multi_cell(0, 6, self._t(analysis))
        self.ln(4)

    def add_news(self, news: list[dict]):
        """Add a recent news section to the PDF.

        Args:
            news: List of dicts with "title" and "source" keys.
        """
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

    def add_charts(self, charts: dict):
        """Embed daily and monthly chart PNGs side by side into the PDF.

        Both charts are placed at the same y position (side by side). Captions
        appear below each image. The cursor is advanced past the images using
        ``rendered_height`` from fpdf2's ImageInfo return value, so no content
        overlaps the charts.

        Args:
            charts: Dict with keys ``"daily"`` and ``"monthly"``, each mapping
                to a sub-dict with a ``"path"`` key pointing to the PNG file.
        """
        daily_path = (
            charts.get("daily", {}).get("path", "") if isinstance(charts.get("daily"), dict) else ""
        )
        monthly_path = (
            charts.get("monthly", {}).get("path", "")
            if isinstance(charts.get("monthly"), dict)
            else ""
        )

        has_daily = bool(daily_path and os.path.exists(daily_path))
        has_monthly = bool(monthly_path and os.path.exists(monthly_path))

        if not has_daily and not has_monthly:
            return

        usable_w = self.w - self.l_margin - self.r_margin

        if has_daily and has_monthly:
            gap = 4  # mm between the two charts
            chart_w = (usable_w - gap) / 2
            y_img = self.get_y()

            # Place both images at the same y (side by side).
            # image() returns ImageInfo with rendered_height (fpdf2 >= 2.7.4).
            info_l = self.image(daily_path, x=self.l_margin, y=y_img, w=chart_w)
            info_r = self.image(
                monthly_path, x=self.l_margin + chart_w + gap, y=y_img, w=chart_w
            )

            # Advance cursor past the taller of the two images.
            h_l = getattr(info_l, "rendered_height", chart_w / 2)
            h_r = getattr(info_r, "rendered_height", chart_w / 2)
            y_below = y_img + max(h_l, h_r)

            # Captions centered below each image.
            self._use_font(8)
            self.set_xy(self.l_margin, y_below + 1)
            self.cell(chart_w, 5, self._t("Fig. 1 — Casos diários (30d)"), align="C")
            self.set_xy(self.l_margin + chart_w + gap, y_below + 1)
            self.cell(chart_w, 5, self._t("Fig. 2 — Casos mensais (12m)"), align="C")
            # Move cursor to below the captions before next section.
            self.set_y(y_below + 7)
            self.ln(4)
        else:
            path = daily_path if has_daily else monthly_path
            caption = (
                "Fig. 1 — Casos diários (últimos 30 dias)"
                if has_daily
                else "Fig. 2 — Casos mensais (últimos 12 meses)"
            )
            y_img = self.get_y()
            info = self.image(path, x=self.l_margin, y=y_img, w=usable_w)
            h = getattr(info, "rendered_height", usable_w / 2)
            y_below = y_img + h
            self._use_font(9)
            self.set_xy(self.l_margin, y_below + 1)
            self.cell(0, 5, self._t(caption), align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(4)

    def add_data_ref(self, data_ref: str):
        """Add a data sources reference line to the PDF.

        Args:
            data_ref: Description or URL of the data sources used.
        """
        self._use_font(9)
        self.cell(
            0,
            6,
            self._t(f"Fontes dos dados: DATASUS/SIVEP-Gripe (data de ref.: {data_ref})"),
            new_x="LMARGIN",
            new_y="NEXT",
        )


def _build_markdown(
    metrics: dict,
    news: list[dict],
    analysis: str,
    data_ref: str,
    charts: dict | None = None,
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
        lines.append(f"| {label} | {format_metric_value(metrics.get(key))} |")
    lines.append("")

    if charts:
        daily_path = (
            charts.get("daily", {}).get("path", "") if isinstance(charts.get("daily"), dict) else ""
        )
        monthly_path = (
            charts.get("monthly", {}).get("path", "")
            if isinstance(charts.get("monthly"), dict)
            else ""
        )
        if daily_path or monthly_path:
            lines.append("## Gráficos")
            lines.append("")
            if daily_path and os.path.exists(daily_path):
                lines.append("**Figura 1 — Casos diários (últimos 30 dias)**")
                lines.append("")
                lines.append(f"![Casos diários de SRAG]({daily_path})")
                lines.append("")
            if monthly_path and os.path.exists(monthly_path):
                lines.append("**Figura 2 — Casos mensais (últimos 12 meses)**")
                lines.append("")
                lines.append(f"![Casos mensais de SRAG]({monthly_path})")
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

    lines.append("## Fontes dos dados")
    lines.append("")
    lines.append(
        "Dados epidemiológicos: DATASUS / SIVEP-Gripe — "
        f"data de referência (última notificação): {data_ref}"
    )
    lines.append("")

    lines.append("---")
    lines.append(f"Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    return "\n".join(lines)


def generate_report(
    metrics: dict,
    news: list[dict],
    analysis: str,
    data_ref: str,
    charts: dict | None = None,
    output_dir: str | None = None,
) -> dict:
    """Generate the SRAG report in Markdown and PDF formats.

    Args:
        metrics: Dict of metric keys to their computed values.
        news: List of news item dicts (title, url, source, snippet).
        analysis: LLM-generated analytical text.
        data_ref: Reference date of the most recent data.
        charts: Optional dict with ``"daily"`` and ``"monthly"`` keys, each
            containing a sub-dict with ``"path"`` (PNG filepath) and
            ``"fig_json"`` (Plotly JSON). PNG files are embedded in the PDF
            and referenced in the Markdown when the files exist on disk.
        output_dir: Directory where the PDF will be saved. Defaults to
            ``data/reports``.
    """
    md = _build_markdown(metrics, news, analysis, data_ref, charts=charts)

    pdf_path = ""
    try:
        if output_dir is None:
            output_dir = "data/reports"
        os.makedirs(output_dir, exist_ok=True)

        pdf = _SRAGReport()
        pdf.add_page()
        if charts:
            pdf.add_charts(charts)
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
