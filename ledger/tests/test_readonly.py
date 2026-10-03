import sqlite3

import pytest

from ledger.store import Store


def test_readonly_projection_has_a_consistent_snapshot(tmp_path):
    path = tmp_path / "ledger.db"
    writer = Store(path)
    reader = Store(path, readonly=True)
    assert reader.db.execute("select count(*) from sources").fetchone()[0] == 0
    writer.db.execute("insert into sources values ('test', '{}')")
    writer.commit()
    assert reader.db.execute("select count(*) from sources").fetchone()[0] == 0
    with pytest.raises(sqlite3.OperationalError):
        reader.db.execute("delete from sources")
    reader.close()
    writer.close()
