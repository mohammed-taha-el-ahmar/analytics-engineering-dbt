"""FastAPI app: a single page where a recruiter or hiring manager can type
a question, see the SQL the agent generated, and see the result — the
fastest way to demonstrate the self-correction loop without reading code.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.catalog import load_catalog
from agent.config import AgentConfig
from agent.db_adapters.factory import build_adapter
from agent.groq_client import GroqAuthError, GroqRateLimitError
from agent.query_agent import QueryAgentError, ask

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="NL-to-SQL Agent over dbt Marts")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Loaded once at startup: the catalog and adapter don't change per-request,
# and re-parsing manifest.json on every question would be wasted work.
_cfg: AgentConfig | None = None
_catalog = None
_adapter = None


@app.on_event("startup")
def _startup() -> None:
    global _cfg, _catalog, _adapter
    _cfg = AgentConfig.from_env()
    _catalog = load_catalog(_cfg.manifest_path)
    _adapter = build_adapter(_cfg)
    logger.info(
        "Agent ready: db_target=%s marts=%d", _cfg.db_target, len(_catalog.marts)
    )


class AskRequest(BaseModel):
    question: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/catalog")
def get_catalog() -> JSONResponse:
    return JSONResponse(
        {
            "db_target": _cfg.db_target,
            "marts": [
                {"name": m.name, "description": m.description, "columns": [c.name for c in m.columns]}
                for m in _catalog.marts
            ],
        }
    )


@app.post("/api/ask")
def api_ask(req: AskRequest) -> JSONResponse:
    try:
        result = ask(req.question, _cfg, _catalog, _adapter)
    except QueryAgentError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    except GroqAuthError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)
    except GroqRateLimitError as exc:
        return JSONResponse({"error": str(exc)}, status_code=429)
    except Exception as exc:
        logger.exception("Unexpected error in /api/ask")
        return JSONResponse({"error": f"Internal error: {exc}"}, status_code=500)

    return JSONResponse(
        {
            "sql": result.sql,
            "explanation": result.explanation,
            "columns": result.columns,
            "rows": _serialize_rows(result.rows),
            "attempts": result.attempts,
            "history": [
                {"attempt": h.attempt, "status": h.status, "detail": h.detail}
                for h in result.history
            ],
        }
    )


def _serialize_rows(rows: list[tuple]) -> list[list]:
    """Convert DB rows to JSON-safe lists (handles Decimal, date, etc.)."""
    return [[_to_json_safe(v) for v in row] for row in rows]


def _to_json_safe(value):
    """Convert a single value to a JSON-serializable type."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
