"""Seed the SRAG database with cleaned CSV data.

Usage:
    python scripts/seed_db.py [path_to_csv ...]

If no paths are provided, loads all CSV files from data/raw/.
Multiple files are concatenated before insertion.
"""

import glob
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from src.config import Settings
from src.data.etl import load_srag_csv
from src.data.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_COLUMNS = [
    "dt_notific",
    "dt_sin_pri",
    "dt_interna",
    "evolucao",
    "evolucao_label",
    "dt_evoluca",
    "uti",
    "dt_entuti",
    "dt_saiduti",
    "vacine_cov",
    "vacina_cov",
    "dose_1_cov",
    "dose_2_cov",
    "nu_idade_n",
    "cs_sexo",
    "sg_uf_not",
    "classi_fin",
    "caso_confirmado",
    "sem_not",
    "ano_notificacao",
]


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Select and rename columns to match the SQLAlchemy model."""
    available = [c for c in MODEL_COLUMNS if c in df.columns]
    df = df[available].copy()

    # Drop rows with null dt_notific (invalid records)
    if "dt_notific" in df.columns:
        before = len(df)
        df = df.dropna(subset=["dt_notific"])
        dropped = before - len(df)
        if dropped > 0:
            logger.info(f"Dropped {dropped} rows with null dt_notific")

    return df


def seed_database(csv_paths: list[str] | None = None):
    """Load CSVs, transform, and insert into PostgreSQL."""
    settings = Settings()
    engine = create_engine(settings.database_url)

    # Find CSV files
    if csv_paths:
        files = [Path(p) for p in csv_paths]
    else:
        data_dir = Path("data/raw")
        files = sorted(
            Path(f)
            for f in glob.glob(str(data_dir / "*.csv")) + glob.glob(str(data_dir / "*.csv.gz"))
        )
        if not files:
            logger.error(
                "No CSV files found in data/raw/. Run: python scripts/download_srag_data.py"
            )
            sys.exit(1)

    logger.info(f"Found {len(files)} CSV file(s) to process")

    # Load and concatenate all CSVs
    dfs = []
    for filepath in files:
        logger.info(f"Loading: {filepath.name}")
        df = load_srag_csv(filepath)
        df = _prepare_df(df)
        dfs.append(df)
        logger.info(f"  {filepath.name}: {len(df)} rows after cleaning")

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"Total rows after concatenation: {len(combined)}")

    # Create tables
    Base.metadata.create_all(engine)
    logger.info("Tables created/verified")

    # Insert into database
    logger.info(f"Inserting {len(combined)} rows into srag.srag_cases...")
    combined.to_sql(
        "srag_cases",
        engine,
        schema="srag",
        if_exists="replace",
        index=False,
        chunksize=5000,
    )

    # Analyze table for query planning
    with engine.connect() as conn:
        conn.execute(text("ANALYZE srag.srag_cases;"))
        conn.commit()

    # Verify
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM srag.srag_cases")).scalar()
        max_date = conn.execute(text("SELECT MAX(dt_notific) FROM srag.srag_cases")).scalar()
        years = conn.execute(
            text("SELECT DISTINCT ano_notificacao FROM srag.srag_cases ORDER BY 1")
        ).fetchall()

    logger.info(f"Total rows: {count:,}")
    logger.info(f"Max dt_notific (data_ref): {max_date}")
    logger.info(f"Years: {[y[0] for y in years]}")
    logger.info("Seed complete!")


if __name__ == "__main__":
    paths = sys.argv[1:] if len(sys.argv) > 1 else None
    seed_database(paths)
