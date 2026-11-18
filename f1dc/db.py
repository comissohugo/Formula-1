"""Banco SQLite do F1 Data Center.

O esquema segue o modelo de dados sugerido no documento central (seção 4),
com duas adições de rastreabilidade exigidas pelas regras do projeto:
``source_url`` e ``fetched_at`` em cada tabela de resultados.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import config

SCHEMA_VERSION = "2"

DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS seasons (
    season                   INTEGER PRIMARY KEY,
    races_count              INTEGER,
    sprint_races             INTEGER,
    results_races            INTEGER,
    qualifying_races         INTEGER,
    champion_driver_id       TEXT,
    champion_constructor_id  TEXT,
    imported_at              TEXT,
    source_url               TEXT
);

CREATE TABLE IF NOT EXISTS circuits (
    circuit_id TEXT PRIMARY KEY,
    name       TEXT,
    locality   TEXT,
    country    TEXT,
    lat        REAL,
    lng        REAL,
    url        TEXT
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_id        TEXT PRIMARY KEY,
    code             TEXT,
    permanent_number TEXT,
    given_name       TEXT,
    family_name      TEXT,
    full_name        TEXT,
    nationality      TEXT,
    date_of_birth    TEXT,
    url              TEXT
);

CREATE TABLE IF NOT EXISTS constructors (
    constructor_id TEXT PRIMARY KEY,
    name           TEXT,
    nationality    TEXT,
    url            TEXT
);

CREATE TABLE IF NOT EXISTS races (
    season      INTEGER NOT NULL,
    "round"     INTEGER NOT NULL,
    race_name   TEXT,
    circuit_id  TEXT REFERENCES circuits(circuit_id),
    date        TEXT,
    time        TEXT,
    url         TEXT,
    has_sprint  INTEGER NOT NULL DEFAULT 0,
    source_url  TEXT,
    fetched_at  TEXT,
    PRIMARY KEY (season, "round")
);

CREATE TABLE IF NOT EXISTS race_results (
    season              INTEGER NOT NULL,
    "round"             INTEGER NOT NULL,
    driver_id           TEXT NOT NULL REFERENCES drivers(driver_id),
    constructor_id      TEXT NOT NULL REFERENCES constructors(constructor_id),
    number              TEXT,
    grid                INTEGER,
    position            INTEGER,
    position_text       TEXT,
    position_order      INTEGER,
    points              REAL,
    laps                INTEGER,
    status              TEXT,
    status_id           INTEGER,
    time_millis         INTEGER,
    time_text           TEXT,
    fastest_lap_rank    INTEGER,
    fastest_lap_number  INTEGER,
    fastest_lap_time    TEXT,
    fastest_lap_speed   REAL,
    source_url          TEXT,
    fetched_at          TEXT,
    PRIMARY KEY (season, "round", driver_id)
);

CREATE TABLE IF NOT EXISTS qualifying_results (
    season          INTEGER NOT NULL,
    "round"         INTEGER NOT NULL,
    driver_id       TEXT NOT NULL REFERENCES drivers(driver_id),
    constructor_id  TEXT NOT NULL REFERENCES constructors(constructor_id),
    number          TEXT,
    position        INTEGER,
    q1              TEXT,
    q2              TEXT,
    q3              TEXT,
    source_url      TEXT,
    fetched_at      TEXT,
    PRIMARY KEY (season, "round", driver_id)
);

-- Dados complementares de pole e volta mais rápida quando a fonte primária
-- (Jolpica/Ergast) não os fornece. Nunca sobrescreve a fonte primária: as
-- consultas do painel preferem qualifying_results/race_results e usam esta
-- tabela apenas para preencher lacunas documentadas.
CREATE TABLE IF NOT EXISTS session_awards (
    season          INTEGER NOT NULL,
    "round"         INTEGER NOT NULL,
    award           TEXT NOT NULL CHECK (award IN ('pole', 'fastest_lap')),
    driver_id       TEXT NOT NULL REFERENCES drivers(driver_id),
    constructor_id  TEXT NOT NULL REFERENCES constructors(constructor_id),
    source_url      TEXT,
    fetched_at      TEXT,
    PRIMARY KEY (season, "round", award)
);

CREATE TABLE IF NOT EXISTS sprint_results (
    season          INTEGER NOT NULL,
    "round"         INTEGER NOT NULL,
    driver_id       TEXT NOT NULL REFERENCES drivers(driver_id),
    constructor_id  TEXT NOT NULL REFERENCES constructors(constructor_id),
    number          TEXT,
    grid            INTEGER,
    position        INTEGER,
    position_text   TEXT,
    position_order  INTEGER,
    points          REAL,
    laps            INTEGER,
    status          TEXT,
    status_id       INTEGER,
    time_millis     INTEGER,
    time_text       TEXT,
    source_url      TEXT,
    fetched_at      TEXT,
    PRIMARY KEY (season, "round", driver_id)
);

CREATE TABLE IF NOT EXISTS driver_standings (
    season           INTEGER NOT NULL,
    "round"          INTEGER NOT NULL,
    driver_id        TEXT NOT NULL REFERENCES drivers(driver_id),
    position         INTEGER,
    position_text    TEXT,
    points           REAL,
    wins             INTEGER,
    constructor_ids  TEXT,
    source_url       TEXT,
    fetched_at       TEXT,
    PRIMARY KEY (season, "round", driver_id)
);

CREATE TABLE IF NOT EXISTS constructor_standings (
    season          INTEGER NOT NULL,
    "round"         INTEGER NOT NULL,
    constructor_id  TEXT NOT NULL REFERENCES constructors(constructor_id),
    position        INTEGER,
    position_text   TEXT,
    points          REAL,
    wins            INTEGER,
    source_url      TEXT,
    fetched_at      TEXT,
    PRIMARY KEY (season, "round", constructor_id)
);

CREATE TABLE IF NOT EXISTS import_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    seasons     TEXT,
    status      TEXT,
    requests    INTEGER,
    errors      TEXT
);

CREATE INDEX IF NOT EXISTS idx_race_results_driver ON race_results(driver_id);
CREATE INDEX IF NOT EXISTS idx_race_results_constructor ON race_results(constructor_id);
CREATE INDEX IF NOT EXISTS idx_qualifying_driver ON qualifying_results(driver_id);
CREATE INDEX IF NOT EXISTS idx_session_awards_driver ON session_awards(driver_id);
CREATE INDEX IF NOT EXISTS idx_sprint_driver ON sprint_results(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_standings_driver ON driver_standings(driver_id);

-- Volta mais rápida: derivada dos resultados (rank 1), sem duplicar dado.
CREATE VIEW IF NOT EXISTS fastest_laps AS
SELECT season, "round", driver_id, constructor_id,
       fastest_lap_number AS lap, fastest_lap_time AS time, fastest_lap_speed AS speed
FROM race_results
WHERE fastest_lap_rank = 1;
"""

SEASON_TABLES = (
    "race_results",
    "qualifying_results",
    "session_awards",
    "sprint_results",
    "driver_standings",
    "constructor_standings",
    "races",
)


def connect(db_path: str | Path = config.DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,),
    )
    conn.commit()


def upsert_rows(
    conn: sqlite3.Connection, table: str, rows: Sequence[dict[str, Any]]
) -> int:
    """INSERT OR REPLACE idempotente (atualizar sem duplicar)."""
    if not rows:
        return 0
    columns = list(rows[0].keys())
    cols_sql = ", ".join(f'"{c}"' for c in columns)
    values_sql = ", ".join(f":{c}" for c in columns)
    sql = f'INSERT OR REPLACE INTO "{table}" ({cols_sql}) VALUES ({values_sql})'
    conn.executemany(sql, rows)
    return len(rows)


def delete_season(conn: sqlite3.Connection, season: int) -> None:
    """Remove a temporada antes de reimportar (evita registros obsoletos)."""
    for table in SEASON_TABLES:
        conn.execute(f'DELETE FROM "{table}" WHERE season = ?', (season,))
    conn.execute("DELETE FROM seasons WHERE season = ?", (season,))


def insert_run(
    conn: sqlite3.Connection, started_at: str, seasons: Iterable[int]
) -> int:
    cursor = conn.execute(
        "INSERT INTO import_runs(started_at, seasons, status) VALUES (?, ?, 'running')",
        (started_at, ",".join(str(s) for s in seasons)),
    )
    return int(cursor.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    finished_at: str,
    status: str,
    requests: int,
    errors: list[str],
) -> None:
    import json

    conn.execute(
        "UPDATE import_runs SET finished_at = ?, status = ?, requests = ?, errors = ? WHERE id = ?",
        (finished_at, status, requests, json.dumps(errors, ensure_ascii=False), run_id),
    )


def last_successful_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM import_runs WHERE status IN ('ok', 'incomplete') ORDER BY id DESC LIMIT 1"
    ).fetchone()
