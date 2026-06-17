"""Minimal Postgres adapter skeleton.

Phase 3 does not require a running database for unit tests. This is a thin,
honest skeleton: it builds a DSN from settings and lazily opens a psycopg
connection only when explicitly asked. No schema/migrations yet (later phases
persist documents and run logs). Importing this module has no side effects and
no DB requirement.
"""

from __future__ import annotations

from typing import Any

from packages.config.settings import Settings, get_settings


class PostgresAdapter:
    """Lazy connection holder over a psycopg connection."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._conn: Any | None = None

    @property
    def dsn(self) -> str:
        return self._settings.postgres_dsn

    def connect(self) -> Any:  # pragma: no cover - requires a running Postgres
        """Open (once) and return a psycopg connection."""

        if self._conn is not None:
            return self._conn
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("The 'psycopg' package is required to connect to Postgres.") from exc
        self._conn = psycopg.connect(self.dsn)
        return self._conn

    def close(self) -> None:  # pragma: no cover - requires a running Postgres
        if self._conn is not None:
            self._conn.close()
            self._conn = None
