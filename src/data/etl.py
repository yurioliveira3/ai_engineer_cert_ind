"""SRAG ETL pipeline: load, clean, transform, and validate DATASUS data."""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SELECTED_COLUMNS = [
    "DT_NOTIFIC",
    "DT_SIN_PRI",
    "CLASSI_FIN",
    "EVOLUCAO",
    "DT_EVOLUCA",
    "UTI",
    "DT_ENTUTI",
    "DT_SAIDUTI",
    "VACINA_COV",
    "DOSE_1_COV",
    "DOSE_2_COV",
    "NU_IDADE_N",
    "CS_SEXO",
    "SG_UF_NOT",
    "SEM_NOT",
    "DT_INTERNA",
    "HOSPITAL",
]

PII_COLUMNS = ["NM_PACIENT", "NU_CPF", "NU_CNS", "NM_MAE_PAC", "END_*"]

DATE_COLUMNS = [
    "DT_NOTIFIC",
    "DT_SIN_PRI",
    "DT_EVOLUCA",
    "DT_ENTUTI",
    "DT_SAIDUTI",
    "DOSE_1_COV",
    "DOSE_2_COV",
    "DT_INTERNA",
]

LABEL_MAPS = {
    "EVOLUCAO": {1: "Cura", 2: "Obito SRAG", 3: "Obito outras causas", 9: "Ignorado"},
    "UTI": {1: "Sim", 2: "Nao", 9: "Ignorado"},
    "VACINA_COV": {1: "Sim", 2: "Nao", 9: "Ignorado"},
    "CS_SEXO": {"M": "Masculino", "F": "Feminino", "I": "Ignorado"},
}

CONFIRMED_CLASSI_FIN = [1, 2, 3, 4, 5]

ENCODINGS_TO_TRY = ["latin-1", "utf-8", "cp1252"]
SEPARATORS_TO_TRY = [";", ","]


def _detect_csv_config(filepath: str | Path) -> tuple[str, str]:
    """Detect encoding and separator for the SRAG CSV."""
    filepath = Path(filepath)
    for encoding in ENCODINGS_TO_TRY:
        try:
            with open(filepath, encoding=encoding) as f:
                first_line = f.readline()
            if ";" in first_line:
                return encoding, ";"
            if "," in first_line:
                return encoding, ","
        except (UnicodeDecodeError, UnicodeError):
            continue
    logger.warning("Could not detect CSV config, defaulting to latin-1/semicolon")
    return "latin-1", ";"


def load_srag_csv(filepath: str | Path) -> pd.DataFrame:
    """Load, clean, and transform SRAG CSV data.

    Steps:
    1. Detect encoding and separator
    2. Load CSV
    3. Select relevant columns
    4. Convert date columns
    5. Create label columns
    6. Remove PII columns
    7. Create derived columns (caso_confirmado, ano_notificacao)
    """
    filepath = Path(filepath)
    encoding, sep = _detect_csv_config(filepath)
    logger.info(f"Loading {filepath.name} with encoding={encoding}, sep='{sep}'")

    df = pd.read_csv(filepath, sep=sep, encoding=encoding, low_memory=False)
    logger.info(f"Raw CSV: {len(df)} rows, {len(df.columns)} columns")

    # Select relevant columns (only those that exist)
    available_cols = [c for c in SELECTED_COLUMNS if c in df.columns]
    missing = set(SELECTED_COLUMNS) - set(available_cols)
    if missing:
        logger.warning(f"Missing columns in CSV: {missing}")
    df = df[available_cols].copy()

    # Remove PII columns if present
    pii_found = [c for c in PII_COLUMNS if c in df.columns]
    if pii_found:
        logger.info(f"Removing PII columns: {pii_found}")
        df = df.drop(columns=pii_found)
    # Also check for END_* pattern
    end_cols = [c for c in df.columns if c.startswith("END_")]
    if end_cols:
        logger.info(f"Removing END_* columns: {end_cols}")
        df = df.drop(columns=end_cols)

    # Convert date columns
    for col in DATE_COLUMNS:
        if col in df.columns:
            col_lower = col.lower()
            df[col_lower] = pd.to_datetime(df[col], format="mixed", dayfirst=True, errors="coerce")
            non_null = df[col_lower].notna().sum()
            total = len(df)
            pct = non_null / total * 100 if total > 0 else 0
            logger.info(f"Date column {col}: {pct:.1f}% valid ({non_null}/{total})")
            # Drop original mixed-case column if we renamed
            if col != col_lower and col in df.columns:
                df = df.drop(columns=[col])

    # Normalize all column names to lowercase
    df.columns = [c.lower() for c in df.columns]

    # Convert numeric columns
    numeric_cols = [
        "evolucao",
        "uti",
        "vacina_cov",
        "nu_idade_n",
        "sem_not",
        "classi_fin",
        "hospital",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Create label columns (use uppercase keys in LABEL_MAPS, lowercase column names)
    label_maps_lower = {k.lower(): v for k, v in LABEL_MAPS.items()}
    for col, mapping in label_maps_lower.items():
        if col in df.columns:
            label_col = f"{col}_label" if col != "cs_sexo" else "cs_sexo_label"
            df[label_col] = df[col].map(mapping).fillna("Ignorado")

    # Create derived columns
    if "classi_fin" in df.columns:
        df["caso_confirmado"] = df["classi_fin"].isin(CONFIRMED_CLASSI_FIN)
    else:
        df["caso_confirmado"] = False

    if "dt_notific" in df.columns:
        df["ano_notificacao"] = df["dt_notific"].dt.year.astype("Int64")
    elif "DT_NOTIFIC" in df.columns:
        df["ano_notificacao"] = pd.to_datetime(df["DT_NOTIFIC"], errors="coerce").dt.year.astype(
            "Int64"
        )
    else:
        df["ano_notificacao"] = pd.NA

    # Log null percentages
    null_pct = (df.isnull().sum() / len(df) * 100).round(2)
    for col, pct in null_pct.items():
        if pct > 0:
            logger.info(f"Null % in {col}: {pct}%")

    # Log duplicate ratio
    dup_ratio = df.duplicated().sum() / len(df) * 100
    logger.info(f"Duplicate ratio: {dup_ratio:.2f}%")

    logger.info(f"Cleaned DataFrame: {len(df)} rows, {len(df.columns)} columns")
    return df
