"""Explore SRAG CSV data: test encodings, separators, and report stats.

Usage:
    python scripts/explore_data.py [path_to_csv]
"""

import glob
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ENCODINGS = ["latin-1", "utf-8", "cp1252"]
SEPARATORS = [";", ","]


def explore_csv(filepath: str | Path):
    """Load and explore an SRAG CSV file."""
    filepath = Path(filepath)
    logger.info(f"Exploring: {filepath}")

    # Try encodings and separators
    for encoding in ENCODINGS:
        for sep in SEPARATORS:
            try:
                df = pd.read_csv(filepath, sep=sep, encoding=encoding, nrows=100, low_memory=False)
                if len(df.columns) > 5:
                    logger.info(f"SUCCESS: encoding={encoding}, sep='{sep}', shape={df.shape}")
                    logger.info(f"Columns ({len(df.columns)}): {df.columns.tolist()}")
                    break
            except (UnicodeDecodeError, pd.errors.ParserError) as e:
                logger.info(f"FAILED: encoding={encoding}, sep='{sep}' — {type(e).__name__}")
        else:
            continue
        break
    else:
        logger.error("Could not load CSV with any encoding/separator combination")
        sys.exit(1)

    # Full load for stats
    df_full = pd.read_csv(filepath, sep=sep, encoding=encoding, low_memory=False)

    print(f"\n{'=' * 60}")
    print(f"CSV Exploration Report: {filepath.name}")
    print(f"{'=' * 60}")
    print(f"Shape: {df_full.shape}")
    print(f"Encoding: {encoding}")
    print(f"Separator: '{sep}'")
    print(f"\nDtypes:\n{df_full.dtypes}")
    print(f"\nNull counts:\n{df_full.isnull().sum()}")
    if "DT_NOTIFIC" in df_full.columns:
        print(f"\nDT_NOTIFIC sample:\n{df_full['DT_NOTIFIC'].head(10)}")
    else:
        print("\nDT_NOTIFIC: N/A")

    if "EVOLUCAO" in df_full.columns:
        print(f"\nEVOLUCAO distribution:\n{df_full['EVOLUCAO'].value_counts()}")
    if "UTI" in df_full.columns:
        print(f"\nUTI distribution:\n{df_full['UTI'].value_counts()}")
    if "VACINA_COV" in df_full.columns:
        print(f"\nVACINA_COV distribution:\n{df_full['VACINA_COV'].value_counts()}")

    print(f"\nAll columns ({len(df_full.columns)}):")
    for col in sorted(df_full.columns):
        print(f"  {col}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        files = glob.glob("data/raw/*.csv") + glob.glob("data/raw/*.csv.gz")
        if not files:
            print("No CSV files found in data/raw/. Download SRAG data from:")
            print("  https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026")
            print("\nPlace the file(s) in data/raw/ and re-run this script.")
            sys.exit(1)
        path = sorted(files)[0]

    explore_csv(path)
