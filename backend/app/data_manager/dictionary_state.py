"""Shared revision and export status for workers on the same host/data directory."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class DictionaryWriteCommittedError(RuntimeError):
    """SQL has committed; synchronization/read-back could not be confirmed."""


class DictionaryState:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "runtime" / "dictionary-state.sqlite3"

    @contextmanager
    def connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, "
                               "revision INTEGER NOT NULL, status TEXT NOT NULL)")
            connection.execute("INSERT OR IGNORE INTO state VALUES (1, 0, 'not_exported')")
            connection.commit()
            if write:
                # Serialize export snapshots across workers, so an older snapshot
                # cannot overwrite a newer export after concurrent SQL commits.
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def read(self) -> dict:
        with self.connection() as connection:
            revision, status = connection.execute(
                "SELECT revision, status FROM state WHERE id=1"
            ).fetchone()
        return {"revision": revision, "status": status}

    def bump(self) -> dict:
        try:
            with self.connection(write=True) as connection:
                status = connection.execute("SELECT status FROM state WHERE id=1").fetchone()[0]
                result = self.advance(connection, status)
        except (OSError, sqlite3.Error) as exc:
            raise DictionaryWriteCommittedError("SQL saved; shared revision unavailable") from exc
        return result

    @staticmethod
    def advance(connection: sqlite3.Connection, status: str) -> dict:
        connection.execute("UPDATE state SET revision=revision+1, status=? WHERE id=1", (status,))
        revision = connection.execute("SELECT revision FROM state WHERE id=1").fetchone()[0]
        return {"revision": revision, "status": status, "database_committed": True}
