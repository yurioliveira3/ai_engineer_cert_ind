import os

import pandas as pd
import pytest
from sqlalchemy import create_engine

from src.config import Settings


@pytest.fixture(scope="session")
def test_settings():
    """Settings pointing to test database."""
    test_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://srag_app:srag_pass@localhost:5433/srag_test",
    )
    return Settings(database_url=test_url)


@pytest.fixture(scope="session")
def db_engine(test_settings):
    """SQLAlchemy engine for test database. Only used by integration tests."""
    engine = create_engine(test_settings.database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_connection(db_engine):
    """Provide a database connection with rollback for clean test state.

    Use this fixture only in tests that need a real database connection.
    Unit tests should not use this fixture.
    """
    conn = db_engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()


@pytest.fixture
def sample_srag_csv(tmp_path):
    """Generate a synthetic SRAG CSV with ~20 rows for unit testing."""
    data = {
        "DT_NOTIFIC": pd.date_range("2024-01-01", periods=20, freq="D").strftime("%d/%m/%Y"),
        "DT_SIN_PRI": pd.date_range("2023-12-28", periods=20, freq="D").strftime("%d/%m/%Y"),
        "CLASSI_FIN": [5] * 15 + [1] * 3 + [2] * 2,
        "EVOLUCAO": [1] * 10 + [2] * 4 + [3] * 2 + [9] * 4,
        "DT_EVOLUCA": (
            [""] * 10
            + pd.date_range("2024-01-15", periods=6, freq="D").strftime("%d/%m/%Y").tolist()
            + [""] * 4
        ),
        "UTI": [2] * 12 + [1] * 5 + [9] * 3,
        "DT_ENTUTI": [""] * 12
        + pd.date_range("2024-01-05", periods=5, freq="D").strftime("%d/%m/%Y").tolist()
        + [""] * 3,
        "DT_SAIDUTI": [""] * 12
        + pd.date_range("2024-01-10", periods=5, freq="D").strftime("%d/%m/%Y").tolist()
        + [""] * 3,
        "VACINA_COV": [2] * 8 + [1] * 8 + [9] * 4,
        "DOSE_1_COV": [""] * 8
        + pd.date_range("2023-06-01", periods=8, freq="D").strftime("%d/%m/%Y").tolist()
        + [""] * 4,
        "DOSE_2_COV": [""] * 10
        + pd.date_range("2023-09-01", periods=5, freq="D").strftime("%d/%m/%Y").tolist()
        + [""] * 5,
        "NU_IDADE_N": [
            25,
            30,
            45,
            60,
            70,
            35,
            50,
            65,
            80,
            55,
            40,
            75,
            28,
            62,
            48,
            33,
            58,
            72,
            42,
            67,
        ],
        "CS_SEXO": ["M", "F", "M", "F", "M", "F", "M", "F", "M", "F"] * 2,
        "SG_UF_NOT": ["SP"] * 8 + ["RJ"] * 6 + ["MG"] * 4 + ["RS"] * 2,
        "SEM_NOT": [1, 2, 3, 4] * 5,
        "DT_INTERNA": pd.date_range("2024-01-02", periods=20, freq="D").strftime("%d/%m/%Y"),
        "HOSPITAL": [1] * 15 + [2] * 5,
        "NU_CPF": [""] * 20,
        "NM_PACIENT": [""] * 20,
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "srag_test.csv"
    df.to_csv(csv_path, sep=";", encoding="latin-1", index=False)
    return csv_path
