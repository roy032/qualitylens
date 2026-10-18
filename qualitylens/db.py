"""Read-only database access for data-integrity checks.

Tests only ever SELECT. Writing to the app's database directly would bypass the
application logic we are trying to test.
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from qualitylens.config import settings


class Database:
    def __init__(self, dsn: str = settings.db_dsn):
        self.conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    def query(self, sql: str, params: tuple | dict = ()) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def one(self, sql: str, params: tuple | dict = ()) -> dict | None:
        rows = self.query(sql, params)
        assert len(rows) <= 1, f"Expected at most one row, got {len(rows)}"
        return rows[0] if rows else None

    def close(self):
        self.conn.close()
