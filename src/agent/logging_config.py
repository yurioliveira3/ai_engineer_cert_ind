"""Audit logging and runtime guardrails configuration."""

import json
import logging
import uuid
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from sqlalchemy import text

# Project package-root logger. Every module uses logging.getLogger(__name__),
# i.e. "src.*", so configuring "src" makes all of them inherit these handlers.
_APP_LOGGER = "src"

# Third-party loggers that are noisy at INFO and add no value to the agent trace.
_NOISY_LOGGERS = ("sentence_transformers", "transformers", "httpx", "httpcore", "urllib3")


def setup_logger(name: str = _APP_LOGGER, level: int = logging.INFO) -> logging.Logger:
    """Configure the project logger with console + daily rotating file output.

    Configures the package-root logger ("src") so every module logger inherits
    the handlers. Idempotent. Sets ``propagate = False`` so records do not bubble
    up to the root logger (which avoids duplicated lines under Streamlit, whose
    own root handler would otherwise re-emit every message).
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:  # already configured: only refresh the level
        for handler in logger.handlers:
            handler.setLevel(
                level if not isinstance(handler, TimedRotatingFileHandler) else logging.DEBUG
            )
        return logger

    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        log_dir / "srag_agent.log",
        when="midnight",
        backupCount=30,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # Keep noisy third-party libraries from drowning the agent trace.
    for noisy in _NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger.info(
        "Logger configurado (nivel=%s, arquivo=%s)",
        logging.getLevelName(level),
        file_handler.baseFilename,
    )
    return logger


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
        self._log = logging.getLogger("src.agent.audit")

    def start_session(self) -> str:
        """Start a new audit session, insert into audit.agent_sessions."""
        session_id = str(uuid.uuid4())
        self.session_id = session_id
        self._log.info(
            "Sessao iniciada: id=%s provider=%s model=%s",
            session_id,
            self.llm_provider,
            self.llm_model,
        )
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
        self._log.info(
            "Sessao finalizada: id=%s status=%s%s",
            self.session_id,
            status,
            f" erro={error}" if error else "",
        )
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
        self._log.info(
            "[tool-call] step=%s tool=%s status=%s duracao=%dms | entrada=%s | saida=%s",
            step,
            tool,
            "ok" if success else "falha",
            duration_ms,
            input_summary,
            output_summary,
        )
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
        self._log.info(
            "[llm-call] prompt=%s hash=%s tokens_in=%d tokens_out=%d duracao=%dms | resposta=%r",
            prompt_name,
            prompt_hash[:12] if prompt_hash else "-",
            tokens_in,
            tokens_out,
            duration_ms,
            (response_summary or "")[:120],
        )
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
        result: dict[str, Any] = {"session_id": sid}
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
