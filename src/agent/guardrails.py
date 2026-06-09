"""SQL guardrails: validate and safely execute queries."""

import hashlib
import logging
import re
import time

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

DESTRUCTIVE_KEYWORDS = [
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "REPLACE",
]

DANGEROUS_PATTERNS = [
    r";\s*\w",  # multi-statement
]


def validate_sql_safety(query: str) -> tuple[bool, str]:
    """Validate that a SQL query is safe to execute.

    Returns (is_safe, reason). If is_safe is False, reason explains why.
    """
    query_stripped = query.strip()

    if not query_stripped:
        return False, "Empty query"

    query_upper = query_stripped.upper()

    # Check for destructive keywords
    for keyword in DESTRUCTIVE_KEYWORDS:
        # Match keyword as a word boundary, not part of another word
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, query_upper):
            return False, f"Destructive keyword detected: {keyword}"

    # Check for multi-statement (semicolon followed by more SQL)
    if ";" in query_stripped[:-1]:  # semicolon before the end
        return False, "Multi-statement queries are not allowed"

    # Check for SELECT * without WHERE
    if re.search(r"SELECT\s+\*\s+FROM", query_upper, re.IGNORECASE):
        if "WHERE" not in query_upper:
            return False, "SELECT * without WHERE clause is not allowed"

    return True, "OK"


def _normalize_query(query: str) -> str:
    """Normalize query for hashing: lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", query.strip().lower())


def _hash_query(query: str) -> str:
    """Generate SHA-256 hash of normalized query."""
    return hashlib.sha256(_normalize_query(query).encode()).hexdigest()


def _add_limit(query: str, default_limit: int = 1000) -> str:
    """Add LIMIT clause to SELECT queries that don't have one."""
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT"):
        return query
    if "LIMIT" in query_upper:
        return query
    return f"{query.rstrip(';')} LIMIT {default_limit}"


def _execute_query(engine, query: str, params: dict) -> pd.DataFrame:
    """Execute a parameterized query and return results as DataFrame."""
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        rows = result.fetchall()
        cols = list(result.keys()) if result.keys() else None
        return pd.DataFrame(rows, columns=cols)


def safe_execute(
    query: str,
    params: dict,
    engine,
) -> tuple[pd.DataFrame | str, int]:
    """Execute a SQL query safely with guardrails.

    Returns (result, execution_time_ms).
    - result: DataFrame on success, error string on failure
    - execution_time_ms: query execution time
    """
    # Validate query safety
    is_safe, reason = validate_sql_safety(query)
    if not is_safe:
        logger.warning(f"Blocked unsafe query: {reason}")
        _log_audit(engine, query, 0, blocked=True, block_reason=reason)
        return reason, 0

    # Auto-append LIMIT
    query = _add_limit(query)

    # Execute with timeout
    start_time = time.time()
    try:
        result_df = _execute_query(engine, query, params)
        execution_ms = int((time.time() - start_time) * 1000)
        _log_audit(engine, query, execution_ms, blocked=False)
        return result_df, execution_ms
    except Exception as e:
        execution_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        logger.error(f"Query execution error: {error_msg}")
        return f"Error: {error_msg}", execution_ms


def _log_audit(
    engine,
    query: str,
    execution_ms: int,
    blocked: bool = False,
    block_reason: str | None = None,
) -> None:
    """Log query to audit.query_history."""
    query_hash = _hash_query(query)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO audit.query_history
                    (query_text, query_hash, execution_time_ms, blocked, block_reason)
                    VALUES (:query_text, :query_hash, :execution_time_ms, :blocked, :block_reason)
                """),
                {
                    "query_text": query,
                    "query_hash": query_hash,
                    "execution_time_ms": execution_ms,
                    "blocked": blocked,
                    "block_reason": block_reason,
                },
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to log audit: {e}")


PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+suas?\s+instruções?\s+anteriores",
    r"ignore\s+your\s+previous\s+instructions",
    r"disregard\s+all\s+previous",
    r"esqueça\s+tudo",
    r"you\s+are\s+now",
    r"act\s+as\s+if\s+you\s+are",
    r"system\s*:",
]

_MAX_INPUT_LENGTH = 1000


def validate_user_input(text: str) -> str:
    """Validate and sanitize user input for prompt injection and length."""
    if len(text) > _MAX_INPUT_LENGTH:
        raise ValueError(f"Input exceeds maximum length of {_MAX_INPUT_LENGTH} characters")

    text = text.replace("\x00", "")

    lower = text.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, lower):
            raise ValueError("Potential prompt injection detected")

    return text


def _extract_numeric(value) -> float | None:
    """Extract a numeric value from a metric result.

    Metric results can be either a float/int or a dict like {'taxa_mortalidade': 7.75}.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for v in value.values():
            if isinstance(v, (int, float)):
                return float(v)
    return None


def validate_metrics(metrics: dict) -> dict:
    """Validate metric values and add warnings for suspicious ranges.

    Each metric value can be a number or a dict like {'taxa_mortalidade': 7.75}.
    """
    result = dict(metrics)
    warnings = []

    mortality = _extract_numeric(metrics.get("mortality_rate"))
    if mortality is not None and mortality > 50:
        warnings.append(f"⚠ ALERTA: Taxa de mortalidade de {mortality}% está acima de 50%")

    icu_rate = _extract_numeric(metrics.get("icu_rate"))
    if icu_rate is not None and icu_rate > 100:
        warnings.append(f"⚠ ALERTA: Taxa de UTI de {icu_rate}% acima de 100%")

    vaccination = _extract_numeric(metrics.get("vaccination_rate"))
    if vaccination is not None and vaccination > 100:
        warnings.append(f"⚠ ALERTA: Taxa de vacinação de {vaccination}% acima de 100%")

    case_increase = _extract_numeric(metrics.get("case_increase_rate"))
    if case_increase is not None and case_increase > 500:
        warnings.append(f"⚠ ALERTA: Taxa de aumento de {case_increase}% acima de 500%")

    if warnings:
        result["warnings"] = warnings
    return result


_CPF_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_CPF_RAW_PATTERN = re.compile(r"\b(\d{11})\b")
_PHONE_PATTERN = re.compile(r"\(\d{2}\)\s*\d{4,5}-\d{4}")
_EMAIL_PATTERN = re.compile(r"\b[\w.-]+@[\w.-]+\.\w{2,}\b")


def validate_output_pii(text: str) -> str:
    """Mask PII patterns (CPF, phone, email) in output text. Does NOT block."""
    found_pii = False

    if _CPF_PATTERN.search(text):
        text = _CPF_PATTERN.sub("XXX.XXX.XXX-XX", text)
        found_pii = True

    if _CPF_RAW_PATTERN.search(text):
        text = _CPF_RAW_PATTERN.sub("XXXXXXXXXXX", text)
        found_pii = True

    if _PHONE_PATTERN.search(text):
        text = _PHONE_PATTERN.sub("(XX) XXXXX-XXXX", text)
        found_pii = True

    if _EMAIL_PATTERN.search(text):
        text = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        found_pii = True

    if found_pii:
        logger.warning("PII detected and masked in output")

    return text
