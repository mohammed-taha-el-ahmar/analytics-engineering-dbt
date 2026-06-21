"""Shared interface every DB adapter implements."""
from __future__ import annotations

from typing import Protocol


class AdapterQueryError(RuntimeError):
    """Raised when the database rejects or fails to execute a query.

    The agent catches this, feeds the message back to the model, and
    retries — so the error text should be the raw driver message, not a
    sanitized one, since the model needs real detail to self-correct.
    """


class DBAdapter(Protocol):
    def execute(self, sql: str) -> tuple[list[str], list[tuple]]:
        """Run a validated SELECT and return (column_names, rows)."""
        ...
