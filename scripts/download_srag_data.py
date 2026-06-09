"""Download SRAG (SIVEP-Gripe) individual case data from DATASUS.

Usage:
    python scripts/download_srag_data.py [--years 2024 2025] [--all]

Downloads CSV files to data/raw/. Each file is ~50-290MB.
Default: downloads the most recent year (2025).
"""

import argparse
import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

S3_BASE = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG"

YEAR_FILES = {
    2019: f"{S3_BASE}/2019/INFLUD19-23-03-2026.csv",
    2020: f"{S3_BASE}/2020/INFLUD20-23-03-2026.csv",
    2021: f"{S3_BASE}/2021/INFLUD21-23-03-2026.csv",
    2022: f"{S3_BASE}/2022/INFLUD22-23-03-2026.csv",
    2023: f"{S3_BASE}/2023/INFLUD23-23-03-2026.csv",
    2024: f"{S3_BASE}/2024/INFLUD24-23-03-2026.csv",
    2025: f"{S3_BASE}/2025/INFLUD25-01-06-2026.csv",
    2026: f"{S3_BASE}/2026/INFLUD26-01-06-2026.csv",
}

DICIONARIO_URL = f"{S3_BASE}/dicionario-de-dados-2019-a-2025.pdf"


def download_file(url: str, dest: Path) -> bool:
    """Download a file with progress indicator."""
    logger.info(f"Downloading {url}...")
    logger.info(f"  → {dest}")
    try:
        urllib.request.urlretrieve(url, str(dest))
        size_mb = dest.stat().st_size / (1024 * 1024)
        logger.info(f"  ✓ Downloaded ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        logger.error(f"  ✗ Failed: {e}")
        if dest.exists():
            dest.unlink()
        return False


def main():
    parser = argparse.ArgumentParser(description="Download SRAG data from DATASUS")
    parser.add_argument("--years", nargs="+", type=int, help="Years to download (e.g., 2024 2025)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all available years (2019-2026)",
    )
    parser.add_argument(
        "--dicionario",
        action="store_true",
        help="Also download the data dictionary PDF",
    )
    args = parser.parse_args()

    if args.all:
        years = sorted(YEAR_FILES.keys())
    elif args.years:
        years = sorted(args.years)
    else:
        years = [2025]
        logger.info("No years specified. Defaulting to 2025 (most recent complete year).")
        logger.info("Use --all for all years, or --years 2024 2025 for specific years.")

    logger.info(f"Will download {len(years)} file(s): {years}")
    logger.info(f"Destination: {DATA_DIR.resolve()}")
    print()

    downloaded = 0
    failed = 0
    for year in years:
        if year not in YEAR_FILES:
            logger.warning(f"Year {year} not available. Available: {sorted(YEAR_FILES.keys())}")
            failed += 1
            continue

        url = YEAR_FILES[year]
        filename = url.split("/")[-1]
        dest = DATA_DIR / filename

        if dest.exists():
            logger.info(f"Already exists: {dest} (skipping)")
            downloaded += 1
            continue

        if download_file(url, dest):
            downloaded += 1
        else:
            failed += 1

    if args.dicionario:
        dest = DATA_DIR / "dicionario-de-dados-2019-a-2025.pdf"
        if not dest.exists():
            download_file(DICIONARIO_URL, dest)

    print()
    logger.info(f"Download complete: {downloaded} file(s) downloaded, {failed} failed")
    logger.info(f"Files in {DATA_DIR.resolve()}:")
    for f in sorted(DATA_DIR.glob("*.csv")):
        size_mb = f.stat().st_size / (1024 * 1024)
        logger.info(f"  {f.name} ({size_mb:.1f} MB)")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
