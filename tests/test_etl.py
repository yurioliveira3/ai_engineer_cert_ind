import pandas as pd
import pytest

from src.data.etl import LABEL_MAPS, SELECTED_COLUMNS, load_srag_csv


class TestSelectedColumns:
    def test_selected_columns_exist(self, sample_srag_csv):
        df = load_srag_csv(sample_srag_csv)
        # After ETL, columns should be lowercase
        non_pii_columns = [
            c for c in SELECTED_COLUMNS if c not in ["NU_CPF", "NM_PACIENT", "NU_CNS", "NM_MAE_PAC"]
        ]
        for col in non_pii_columns:
            assert col.lower() in df.columns, f"Missing column: {col.lower()}"


class TestDateConversion:
    def test_date_conversion(self, sample_srag_csv):
        df = load_srag_csv(sample_srag_csv)
        # Check that dt_notific was converted
        assert "dt_notific" in df.columns
        # The column should contain datetime values (or NaT for empty strings)
        assert pd.api.types.is_datetime64_any_dtype(df["dt_notific"])


class TestPIIRemoval:
    def test_no_pii_columns(self, sample_srag_csv):
        df = load_srag_csv(sample_srag_csv)
        pii_columns = ["NM_PACIENT", "NU_CPF", "NU_CNS", "NM_MAE_PAC"]
        for col in pii_columns:
            assert col not in df.columns, f"PII column should be removed: {col}"


class TestNoDuplicates:
    def test_no_duplicates_below_threshold(self, sample_srag_csv):
        df = load_srag_csv(sample_srag_csv)
        dup_ratio = df.duplicated().sum() / len(df) if len(df) > 0 else 0
        assert dup_ratio < 0.01, f"Duplicate ratio {dup_ratio:.2%} exceeds 1% threshold"


class TestLabelColumns:
    def test_label_columns_created(self, sample_srag_csv):
        df = load_srag_csv(sample_srag_csv)
        assert "evolucao_label" in df.columns, "Missing evolucao_label"
        assert "caso_confirmado" in df.columns, "Missing caso_confirmado"
        assert "ano_notificacao" in df.columns, "Missing ano_notificacao"

    def test_label_values_correct(self, sample_srag_csv):
        df = load_srag_csv(sample_srag_csv)
        evolucao_map = LABEL_MAPS["EVOLUCAO"]
        # Columns are lowercase after ETL
        for code, label in evolucao_map.items():
            if code in df["evolucao"].values:
                mask = df["evolucao"] == code
                assert all(df.loc[mask, "evolucao_label"] == label), (
                    f"evolucao={code} should map to '{label}'"
                )


@pytest.mark.integration
class TestETLIntegration:
    def test_csv_loads_without_errors(self, data_raw_dir):
        """Requires real CSV in data/raw/."""
        import glob

        csv_files = glob.glob(str(data_raw_dir / "*.csv")) + glob.glob(
            str(data_raw_dir / "*.csv.gz")
        )
        assert len(csv_files) > 0, "No CSV files found in data/raw/"
        df = load_srag_csv(csv_files[0])
        assert len(df) > 0

    def test_row_count(self, data_raw_dir):
        """Requires real CSV in data/raw/."""
        import glob

        csv_files = glob.glob(str(data_raw_dir / "*.csv")) + glob.glob(
            str(data_raw_dir / "*..csv.gz")
        )
        if not csv_files:
            pytest.skip("No CSV files in data/raw/")
        df = load_srag_csv(csv_files[0])
        assert len(df) > 100_000, f"Expected > 100K rows, got {len(df)}"
