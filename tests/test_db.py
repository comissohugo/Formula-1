import pytest

from f1dc import db


@pytest.fixture()
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    db.init_db(connection)
    yield connection
    connection.close()


def _race(season=2025, round_=1):
    return {
        "season": season,
        "round": round_,
        "race_name": "Test GP",
        "circuit_id": "test_circuit",
        "date": "2025-03-01",
        "time": None,
        "url": None,
        "has_sprint": 0,
        "source_url": "url",
        "fetched_at": "now",
    }


def test_upsert_is_idempotent(conn):
    conn.execute(
        "INSERT INTO circuits(circuit_id, name) VALUES ('test_circuit', 'Test')"
    )
    db.upsert_rows(conn, "races", [_race()])
    db.upsert_rows(conn, "races", [_race()])
    count = conn.execute("SELECT COUNT(*) FROM races").fetchone()[0]
    assert count == 1


def test_delete_season_removes_all_season_rows(conn):
    conn.execute("INSERT INTO circuits(circuit_id, name) VALUES ('test_circuit', 'Test')")
    conn.execute(
        "INSERT INTO drivers(driver_id, full_name) VALUES ('d1', 'Driver One')"
    )
    conn.execute(
        "INSERT INTO constructors(constructor_id, name) VALUES ('c1', 'Team One')"
    )
    db.upsert_rows(conn, "races", [_race()])
    db.upsert_rows(
        conn,
        "race_results",
        [
            {
                "season": 2025,
                "round": 1,
                "driver_id": "d1",
                "constructor_id": "c1",
                "position": 1,
                "points": 25.0,
            }
        ],
    )
    db.upsert_rows(
        conn,
        "seasons",
        [{"season": 2025, "races_count": 1}],
    )

    db.delete_season(conn, 2025)

    assert conn.execute("SELECT COUNT(*) FROM races").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM race_results").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0] == 0
    # entidades globais permanecem
    assert conn.execute("SELECT COUNT(*) FROM drivers").fetchone()[0] == 1


def test_foreign_key_blocks_orphan_result(conn):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO race_results(season, "round", driver_id, constructor_id)
            VALUES (2025, 1, 'ghost', 'ghost_team')
            """
        )
