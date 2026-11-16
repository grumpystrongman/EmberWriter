"""SQLite file-handle lifecycle regression; particularly important on Windows."""
import sqlite3

import pytest

from app.sqlite_lifecycle import ClosingConnection


def test_context_closes_handle_after_commit(tmp_path):
    path = tmp_path / "sample.db"
    con = sqlite3.connect(path, factory=ClosingConnection)
    with con as opened:
        opened.execute("CREATE TABLE sample (id INTEGER)")
        opened.execute("INSERT INTO sample VALUES (1)")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        con.execute("SELECT 1")
    # The same file must be disposable immediately after transaction completion.
    with sqlite3.connect(path) as reader:
        assert reader.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 1
    reader.close()
    path.unlink()
    assert not path.exists()


def test_context_rolls_back_and_still_closes(tmp_path):
    path = tmp_path / "sample.db"
    with sqlite3.connect(path) as setup:
        setup.execute("CREATE TABLE sample (id INTEGER)")
    setup.close()
    con = sqlite3.connect(path, factory=ClosingConnection)
    with pytest.raises(RuntimeError, match="synthetic"), con as opened:
        opened.execute("INSERT INTO sample VALUES (2)")
        raise RuntimeError("synthetic failure")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        con.execute("SELECT 1")
    with sqlite3.connect(path) as reader:
        assert reader.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 0
    reader.close()
    path.unlink()
