"""Seed the SRAG database with cleaned CSV data.

Usage:
    python scripts/seed_db.py [path_to_csv]

If no path is provided, looks for CSV files in data/raw/.
"""

import glob
import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from src.config import Settings
from src.data.etl import load_srag_csv
from src.data.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_database(csv_path: str | None = None):
    """Load CSV, transform, and insert into PostgreSQL."""
    settings = Settings()
    engine = create_engine(settings.database_url)

    # Find CSV file
    if csv_path:
        filepath = Path(csv_path)
    else:
        data_dir = Path("data/raw")
        csv_files = sorted(
            glob.glob(str(data_dir / "*.csv")) + glob.glob(str(data_dir / "*.csv.gz"))
        )
        if not csv_files:
            logger.error("No CSV files found in data/raw/. Download SRAG data first.")
            sys.exit(1)
        filepath = Path(csv_files[0])

    logger.info(f"Loading CSV: {filepath}")

    # Clean and transform
    df = load_srag_csv(filepath)
    logger.info(f"DataFrame shape: {df.shape}")

    # Create tables
    Base.metadata.create_all(engine)
    logger.info("Tables created")

    # Rename columns to lowercase to match model
    column_map = {
        "DT_SIN_PRI": "dt_sin_pri",
        "DT_EVOLUCA": "dt_evoluca",
        "DT_ENTUTI": "dt_entuti",
        "DT_SAIDUTI": "dt_saiduti",
        "DOSE_1_COV": "dose_1_cov",
        "DOSE_2_COV": "dose_2_cov",
        "NU_IDADE_N": "nu_idade_n",
        "CS_SEXO": "cs_sexo",
        "SG_UF_NOT": "sg_uf_not",
        "CLASSI_FIN": "classi_fin",
        "EVOLUCAO": "evolucao",
        "VACINA_COV": "vacina_cov",
        "SEM_NOT": "sem_not",
        "HOSPITAL": "hospital",
    }
    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    # Select model columns that exist in the DataFrame
    model_columns = [
        "dt_notific",
        "dt_sin_pri",
        "dt_interna",
        "evolucao",
        "evolucao_label",
        "dt_evoluca",
        "uti",
        "dt_entuti",
        "dt_saiduti",
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
    available_model_cols = [c for c in model_columns if c in df.columns]
    df = df[available_model_cols]

    # Insert into database
    logger.info(f"Inserting {len(df)} rows into srag.srag_cases...")
    df.to_sql(
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

    logger.info(f"Total rows: {count}")
    logger.info(f"Max dt_notific: {max_date}")
    logger.info(f"Years: {[y[0] for y in years]}")
    logger.info("Seed complete!")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else None
    seed_database(csv_path)
