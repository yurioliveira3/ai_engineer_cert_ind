import os
from unittest.mock import patch

import plotly.graph_objects as go
import pytest

from src.agent.tools.chart_tool import generate_daily_cases_chart, generate_monthly_cases_chart


def _make_daily_data(n=30):
    from datetime import date, timedelta

    base = date(2024, 3, 1)
    return [
        {"dt_notific": (base + timedelta(days=i)).isoformat(), "casos": i + 1} for i in range(n)
    ]


def _make_monthly_data(n=12):
    from datetime import date

    return [
        {"dt_notific": date(2023, i + 1, 1).isoformat(), "casos": (i + 1) * 10} for i in range(n)
    ]


def _mock_write_image(self, path, **kwargs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 2048)


class TestGenerateDailyChartReturnsPath:
    def test_returns_path_to_existing_png(self, tmp_path):
        data = _make_daily_data()
        with patch.object(go.Figure, "write_image", _mock_write_image):
            path, _fig = generate_daily_cases_chart(data, output_dir=str(tmp_path))
        assert os.path.basename(path) == "daily_cases.png"
        assert os.path.exists(path)


class TestGenerateMonthlyChartReturnsPath:
    def test_returns_path_to_existing_png(self, tmp_path):
        data = _make_monthly_data()
        with patch.object(go.Figure, "write_image", _mock_write_image):
            path, _fig = generate_monthly_cases_chart(data, output_dir=str(tmp_path))
        assert os.path.basename(path) == "monthly_cases.png"
        assert os.path.exists(path)


class TestChartWithEmptyDataDoesNotCrash:
    def test_daily_empty_data(self, tmp_path):
        with patch.object(go.Figure, "write_image", _mock_write_image):
            path, fig = generate_daily_cases_chart([], output_dir=str(tmp_path))
        assert os.path.exists(path)
        annotations = fig.layout.annotations
        texts = [a.text for a in annotations] if annotations else []
        assert "Sem dados disponíveis" in texts

    def test_monthly_empty_data(self, tmp_path):
        with patch.object(go.Figure, "write_image", _mock_write_image):
            path, fig = generate_monthly_cases_chart([], output_dir=str(tmp_path))
        assert os.path.exists(path)
        annotations = fig.layout.annotations
        texts = [a.text for a in annotations] if annotations else []
        assert "Sem dados disponíveis" in texts


class TestPngExportHasContent:
    def test_generated_png_has_content(self, tmp_path):
        try:
            data = _make_daily_data(25)
            path, _fig = generate_daily_cases_chart(data, output_dir=str(tmp_path))
            assert os.path.getsize(path) > 1024
        except Exception as e:
            if "kaleido" in str(e).lower():
                pytest.skip("kaleido not available")
            raise
