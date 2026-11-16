"""SQLite connection factory: commit/rollback and close when leaving a with block.

sqlite3.Connection.__exit__ only handles a transaction; it does not close the
file handle on Windows. Persistent open handles prevent cleanup of ephemeral
story.db files. This subclass explicitly closes while preserving transaction
semantics and propagating errors.
"""
from __future__ import annotations

import sqlite3


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()
