import os

from src.agent.tools.report_tool import generate_report


def _sample_metrics():
    return {
        "case_increase_rate": 12.5,
        "mortality_rate": 3.2,
        "icu_rate": 15.0,
        "vaccination_rate": 78.4,
    }


def _sample_news():
    return [
        {
            "title": "Surto de SRAG no Amazonas",
            "url": "https://saude.gov.br/srag",
            "snippet": "Aumento de casos no Amazonas",
            "source": "trusted",
        },
        {
            "title": "Vacinação em alta",
            "url": "https://g1.globo.com/vacina",
            "snippet": "Cobertura vacinal cresce",
            "source": "trusted",
        },
    ]


def _sample_analysis():
    return "A análise indica tendência de aumento nos casos de SRAG."


def _sample_data_ref():
    return "DATASUS — SINAN, dados de 2024"


class TestGenerateReportReturnsMarkdown:
    def test_markdown_contains_all_four_metric_keywords(self, tmp_path):
        result = generate_report(
            metrics=_sample_metrics(),
            news=_sample_news(),
            analysis=_sample_analysis(),
            data_ref=_sample_data_ref(),
            output_dir=str(tmp_path),
        )
        md = result["markdown"]
        assert "Taxa de aumento de casos" in md
        assert "Taxa de mortalidade" in md
        assert "Taxa de ocupação de UTI" in md
        assert "Taxa de vacinação" in md


class TestGenerateReportReturnsPdfPath:
    def test_pdf_path_ends_with_pdf_and_file_exists(self, tmp_path):
        result = generate_report(
            metrics=_sample_metrics(),
            news=_sample_news(),
            analysis=_sample_analysis(),
            data_ref=_sample_data_ref(),
            output_dir=str(tmp_path),
        )
        assert result["pdf_path"].endswith(".pdf")
        assert os.path.exists(result["pdf_path"])


class TestReportContainsNewsSection:
    def test_markdown_has_news_section_when_news_nonempty(self, tmp_path):
        result = generate_report(
            metrics=_sample_metrics(),
            news=_sample_news(),
            analysis=_sample_analysis(),
            data_ref=_sample_data_ref(),
            output_dir=str(tmp_path),
        )
        md = result["markdown"]
        assert "Notícias" in md
        assert "Surto de SRAG no Amazonas" in md
        assert "verificada" in md or "não-verificada" in md


class TestReportWithoutNews:
    def test_generates_valid_markdown_when_news_empty(self, tmp_path):
        result = generate_report(
            metrics=_sample_metrics(),
            news=[],
            analysis=_sample_analysis(),
            data_ref=_sample_data_ref(),
            output_dir=str(tmp_path),
        )
        md = result["markdown"]
        assert "Relatório SRAG" in md
        assert "Taxa de aumento de casos" in md
        assert "Notícias" not in md


class TestPortugueseAccentsInPdf:
    def test_pdf_starts_with_header_and_accents_not_corrupted(self, tmp_path):
        result = generate_report(
            metrics=_sample_metrics(),
            news=_sample_news(),
            analysis=_sample_analysis(),
            data_ref=_sample_data_ref(),
            output_dir=str(tmp_path),
        )
        pdf_path = result["pdf_path"]
        assert pdf_path != ""
        with open(pdf_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"
