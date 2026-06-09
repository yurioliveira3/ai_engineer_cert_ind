"""Validate SRAG data in the database with sanity checks.

Usage:
    python scripts/validate_data.py
"""

import logging

from sqlalchemy import create_engine, text

from src.config import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_data():
    """Run sanity checks against the populated database."""
    settings = Settings()
    engine = create_engine(settings.database_url)

    checks = {
        "total_rows": "SELECT COUNT(*) FROM srag.srag_cases",
        "distinct_years": "SELECT DISTINCT ano_notificacao FROM srag.srag_cases ORDER BY 1",
        "max_date": "SELECT MAX(dt_notific) FROM srag.srag_cases",
        "null_critical_cols": """
            SELECT
                COUNT(*) FILTER (WHERE dt_notific IS NULL) as null_dt_notific,
                COUNT(*) FILTER (WHERE evolucao IS NULL) as null_evolucao,
                COUNT(*) FILTER (WHERE classi_fin IS NULL) as null_classi_fin
            FROM srag.srag_cases
        """,
        "distribution_by_year": """
            SELECT ano_notificacao, COUNT(*) as count
            FROM srag.srag_cases
            GROUP BY ano_notificacao ORDER BY 1
        """,
        "mortality_rate": """
            SELECT
                ROUND(100.0 * COUNT(*) FILTER (WHERE evolucao = 2) /
                    NULLIF(COUNT(*) FILTER (WHERE evolucao IN (1,2,3)), 0), 2) as mortality_rate
            FROM srag.srag_cases
            WHERE caso_confirmado = true
        """,
        "icu_rate": """
            SELECT
                ROUND(100.0 * COUNT(*) FILTER (WHERE uti = 1) /
                    NULLIF(COUNT(*), 0), 2) as icu_rate
            FROM srag.srag_cases
            WHERE caso_confirmado = true
        """,
        "vaccination_rate": """
            SELECT
                ROUND(100.0 * COUNT(*) FILTER (WHERE vacina_cov = 1) /
                    NULLIF(COUNT(*), 0), 2) as vaccination_rate
            FROM srag.srag_cases
            WHERE caso_confirmado = true AND ano_notificacao >= 2021
        """,
    }

    print("=" * 70)
    print("SRAG Data Validation Report")
    print("=" * 70)

    with engine.connect() as conn:
        # Total rows
        total = conn.execute(text(checks["total_rows"])).scalar()
        print(f"\nTotal rows: {total:,}")
        if total < 100_000:
            print("  WARNING: Expected > 100K rows")

        # Distribution by year
        print("\nDistribution by year:")
        rows = conn.execute(text(checks["distribution_by_year"])).fetchall()
        for row in rows:
            print(f"  {row[0]}: {row[1]:,}")

        # Max date
        max_date = conn.execute(text(checks["max_date"])).scalar()
        print(f"\nMax dt_notific (data_ref): {max_date}")

        # Nulls on critical columns
        nulls = conn.execute(text(checks["null_critical_cols"])).fetchone()
        print("\nNull counts on critical columns:")
        print(f"  dt_notific: {nulls[0]:,}")
        print(f"  evolucao: {nulls[1]:,}")
        print(f"  classi_fin: {nulls[2]:,}")

        # Mortality rate
        mortality = conn.execute(text(checks["mortality_rate"])).scalar()
        print(f"\nMortality rate: {mortality}%")
        if mortality and (mortality < 15 or mortality > 25):
            print("  WARNING: Expected 15-25% range")

        # ICU rate
        icu = conn.execute(text(checks["icu_rate"])).scalar()
        print(f"ICU rate: {icu}%")
        if icu and (icu < 20 or icu > 40):
            print("  WARNING: Expected 20-40% range")

        # Vaccination rate
        vax = conn.execute(text(checks["vaccination_rate"])).scalar()
        print(f"Vaccination rate (2021+): {vax}%")

        # Distinct years
        years = conn.execute(text(checks["distinct_years"])).fetchall()
        print(f"\nDistinct years: {[y[0] for y in years]}")

    print("\n" + "=" * 70)
    print("Validation complete.")
    print(f"Save max_date ({max_date}) as your data_ref value.")
    print("=" * 70)


if __name__ == "__main__":
    validate_data()
