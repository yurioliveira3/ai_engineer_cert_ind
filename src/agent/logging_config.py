"""Audit logging and runtime guardrails configuration."""

import functools
import json
import logging
import uuid
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from sqlalchemy import text

_loggers: dict[str, logging.Logger] = {}


def setup_logger(name: str = "srag_agent", level: int = logging.INFO) -> logging.Logger:
    """Configure daily rotating file logger + console output."""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(datetime.UTC).strftime("%Y%m%d")
    file_handler = TimedRotatingFileHandler(
        log_dir / f"srag_agent_{today}.log",
        when="midnight",
        backupCount=30,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console_handler)

    _loggers[name] = logger
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return existing logger or default."""
    if name and name in _loggers:
        return _loggers[name]
    if _loggers:
        return next(iter(_loggers.values()))
    return setup_logger()


class AgentAuditLogger:
    """Audit logger for agent sessions, decisions, queries and LLM calls."""

    def __init__(
        self,
        engine,
        llm_provider: str,
        llm_model: str,
        log_dir: str | None = None,
    ):
        self.engine = engine
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.log_dir = Path(log_dir) if log_dir else Path("data/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id: str | None = None

    def start_session(self) -> str:
        """Start a new audit session, insert into audit.agent_sessions."""
        session_id = str(uuid.uuid4())
        self.session_id = session_id
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO audit.agent_sessions
                        (id, llm_provider, llm_model, status)
                        VALUES (:id, :provider, :model, 'running')
                    """),
                    {
                        "id": session_id,
                        "provider": self.llm_provider,
                        "model": self.llm_model,
                    },
                )
                conn.commit()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to start audit session: {e}")
        return session_id

    def end_session(self, status: str, error: str | None = None) -> None:
        """End the current audit session."""
        if not self.session_id:
            return
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE audit.agent_sessions
                        SET finished_at = NOW(), status = :status, error_text = :error
                        WHERE id = :id
                    """),
                    {"id": self.session_id, "status": status, "error": error},
                )
                conn.commit()

            session_log = self.get_session_log()
            log_path = self.log_dir / f"session_{self.session_id}.json"
            with open(log_path, "w") as f:
                json.dump(session_log, f, indent=2, default=str)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to end audit session: {e}")

    def log_decision(
        self,
        step: str,
        tool: str,
        input_summary: str,
        output_summary: str,
        duration_ms: int,
        success: bool,
    ) -> None:
        """Log an agent decision step."""
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO audit.agent_decisions
                        (session_id, step_name, tool_name, input_summary,
                         output_summary, duration_ms, success)
                        VALUES (:sid, :step, :tool, :inp, :out, :dur, :ok)
                    """),
                    {
                        "sid": self.session_id,
                        "step": step,
                        "tool": tool,
                        "inp": input_summary,
                        "out": output_summary,
                        "dur": duration_ms,
                        "ok": success,
                    },
                )
                conn.commit()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to log decision: {e}")

    def log_query(
        self,
        query_text: str,
        query_hash: str,
        exec_ms: int,
        blocked: bool = False,
        reason: str | None = None,
    ) -> None:
        """Log a query to audit.query_history with session reference."""
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO audit.query_history
                        (session_id, query_text, query_hash, execution_time_ms,
                         blocked, block_reason)
                        VALUES (:sid, :qt, :qh, :ems, :blocked, :reason)
                    """),
                    {
                        "sid": self.session_id,
                        "qt": query_text,
                        "qh": query_hash,
                        "ems": exec_ms,
                        "blocked": blocked,
                        "reason": reason,
                    },
                )
                conn.commit()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to log query: {e}")

    def log_llm_call(
        self,
        prompt_name: str,
        prompt_file: str,
        prompt_hash: str,
        response_summary: str,
        tokens_in: int,
        tokens_out: int,
        duration_ms: int,
    ) -> None:
        """Log an LLM call to audit.llm_calls."""
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO audit.llm_calls
                        (session_id, prompt_name, prompt_file, prompt_hash,
                         response_summary, tokens_input, tokens_output, duration_ms)
                        VALUES (:sid, :pn, :pf, :ph, :rs, :ti, :to, :dm)
                    """),
                    {
                        "sid": self.session_id,
                        "pn": prompt_name,
                        "pf": prompt_file,
                        "ph": prompt_hash,
                        "rs": response_summary,
                        "ti": tokens_in,
                        "to": tokens_out,
                        "dm": duration_ms,
                    },
                )
                conn.commit()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to log LLM call: {e}")

    def get_session_log(self, session_id: str | None = None) -> dict:
        """Retrieve session log as a dict."""
        sid = session_id or self.session_id
        if not sid:
            return {}
        result = {"session_id": sid, "decisions": [], "queries": [], "llm_calls": []}
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM audit.agent_sessions WHERE id = :id"),
                    {"id": sid},
                ).fetchone()
                if row:
                    result["session"] = dict(row._mapping)
        except Exception:
            pass
        return result


def audit_step(step_name: str):
    """Decorator that wraps node functions and logs decision via audit_logger kwarg."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            audit_logger = kwargs.get("audit_logger")
            import time

            start = time.time()
            success = True
            output_summary = ""
            try:
                result = func(*args, **kwargs)
                output_summary = str(result)[:200]
                return result
            except Exception as e:
                success = False
                output_summary = str(e)[:200]
                raise
            finally:
                if audit_logger:
                    duration_ms = int((time.time() - start) * 1000)
                    audit_logger.log_decision(
                        step=step_name,
                        tool=func.__name__,
                        input_summary="",
                        output_summary=output_summary,
                        duration_ms=duration_ms,
                        success=success,
                    )

        return wrapper

    return decorator
