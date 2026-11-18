import pandas as pd

from f1dc import data, db, wikipedia


WIKITEXT = """
== Grandes Prêmios ==
{| class="wikitable sortable"
|-
! GP
! Grande Prêmio
! Pole Position
! Volta mais rápida
! Vencedor
! Equipe
! Descrição
|-
! 1
| {{AUSb}} [[Grande Prêmio da Austrália|GP da Austrália]]
| {{FINb}} [[Piloto B]]
| {{GERb}} [[Piloto A]]
| {{GERb}} [[Piloto A]]
| {{ITAb}} [[Equipe 1]]
| [[Grande Prêmio da Austrália de 2099|Detalhes]]
|}
"""


def test_parse_grand_prix_table_extracts_awards():
    rows = wikipedia.parse_grand_prix_table(WIKITEXT)

    assert len(rows) == 1
    assert rows[0]["round"] == 1
    assert rows[0]["pole"] == "Piloto B"
    assert rows[0]["fastest_lap"] == "Piloto A"
    assert rows[0]["winner"] == "Piloto A"
    assert rows[0]["team"] == "Equipe 1"


WIKITEXT_WITH_LEGEND = """
Os Grandes Prêmios de 2005 foram disputados em vários países.

{| class="wikitable"
|-
|align="center"| '''Campeão'''
|align="center"| '''Vice-campeão'''
|}

== Resultados ==
=== Grandes Prêmios ===
{| class="wikitable sortable"
|-
! GP
! Grande Prêmio
! Pole Position
! Volta mais rápida
! Vencedor
! Equipe
! Descrição
|-
! 1
| {{AUSb}} [[Grande Prêmio da Austrália|GP da Austrália]]
| {{ITAb}} [[Piloto B]]
| {{SPAb}} [[Piloto A]]
| {{SPAb}} [[Piloto A]]
| {{FRAb}} [[Equipe 1]]
| [[Grande Prêmio da Austrália de 2005|Detalhes]]
|}
"""


def test_parse_skips_legend_table_before_grand_prix_table():
    rows = wikipedia.parse_grand_prix_table(WIKITEXT_WITH_LEGEND)

    assert len(rows) == 1
    assert rows[0]["round"] == 1
    assert rows[0]["pole"] == "Piloto B"
    assert rows[0]["fastest_lap"] == "Piloto A"
    assert rows[0]["winner"] == "Piloto A"
    assert rows[0]["team"] == "Equipe 1"


def test_normalize_name_ignores_accents_and_case():
    assert wikipedia.normalize_name("Mika Häkkinen") == "mika hakkinen"
    assert wikipedia.normalize_name("  Kimi   Räikkönen ") == "kimi raikkonen"


def _seed_db(path, *, primary_pole=False, primary_fastest_lap=False):
    conn = db.connect(path)
    db.init_db(conn)
    conn.executemany(
        "INSERT INTO drivers(driver_id, full_name) VALUES (?, ?)",
        [("a", "Piloto A"), ("b", "Piloto B")],
    )
    conn.execute(
        "INSERT INTO constructors(constructor_id, name) VALUES ('t1', 'Equipe 1')"
    )
    conn.execute(
        "INSERT INTO races(season, \"round\", race_name) VALUES (2099, 1, 'GP Teste')"
    )
    conn.executemany(
        """
        INSERT INTO race_results(
            season, "round", driver_id, constructor_id, position, fastest_lap_rank
        ) VALUES (2099, 1, ?, 't1', ?, ?)
        """,
        [("a", 1, 1 if primary_fastest_lap else None), ("b", 2, None)],
    )
    if primary_pole:
        conn.execute(
            """
            INSERT INTO qualifying_results(
                season, "round", driver_id, constructor_id, position
            ) VALUES (2099, 1, 'a', 't1', 1)
            """
        )
    conn.commit()
    conn.close()


def test_import_stores_complementary_awards_with_provenance(tmp_path):
    path = str(tmp_path / "test.db")
    _seed_db(path)
    result = wikipedia.import_seasons(
        seasons=[2099],
        db_path=path,
        fetcher=lambda year: WIKITEXT,
        now="2026-11-10T00:00:00+00:00",
    )

    assert result["status"] == "ok"
    assert result["seasons"][2099]["poles"] == 1
    assert result["seasons"][2099]["fastest_laps"] == 1

    conn = db.connect(path)
    rows = conn.execute(
        'SELECT award, driver_id, constructor_id, source_url, fetched_at '
        "FROM session_awards ORDER BY award"
    ).fetchall()
    conn.close()

    assert [row["award"] for row in rows] == ["fastest_lap", "pole"]
    assert rows[1]["driver_id"] == "b"
    assert all(row["constructor_id"] == "t1" for row in rows)
    assert all(row["source_url"] for row in rows)
    assert all(row["fetched_at"] == "2026-11-10T00:00:00+00:00" for row in rows)

    # Reimportar não duplica os registros.
    wikipedia.import_seasons(
        seasons=[2099],
        db_path=path,
        fetcher=lambda year: WIKITEXT,
    )
    conn = db.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM session_awards").fetchone()[0] == 2
    conn.close()


def test_import_skips_awards_already_present_in_primary_source(tmp_path):
    path = str(tmp_path / "test.db")
    _seed_db(path, primary_pole=True, primary_fastest_lap=True)

    result = wikipedia.import_seasons(
        seasons=[2099],
        db_path=path,
        fetcher=lambda year: WIKITEXT,
        now="2026-11-10T00:00:00+00:00",
    )

    assert result["status"] == "ok"
    assert result["seasons"][2099]["poles"] == 0
    assert result["seasons"][2099]["fastest_laps"] == 0

    conn = db.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM session_awards").fetchone()[0] == 0
    conn.close()


def test_award_events_prefers_primary_source_for_same_race():
    frames = {
        "drivers": pd.DataFrame(
            {"driver_id": ["a", "b"], "full_name": ["Piloto A", "Piloto B"]}
        ),
        "constructors": pd.DataFrame(
            {"constructor_id": ["t1"], "name": ["Equipe 1"]}
        ),
        "qualifying_results": pd.DataFrame(
            {
                "season": [2025],
                "round": [1],
                "driver_id": ["a"],
                "constructor_id": ["t1"],
                "position": [1],
            }
        ),
        "race_results": pd.DataFrame(
            {
                "season": [2025],
                "round": [1],
                "driver_id": ["a"],
                "constructor_id": ["t1"],
                "fastest_lap_rank": [1],
                "fastest_lap_number": [50],
                "fastest_lap_time": ["1:20.000"],
                "fastest_lap_speed": [210.5],
            }
        ),
        "session_awards": pd.DataFrame(
            {
                "season": [2025, 2025, 2025, 2025],
                "round": [1, 1, 2, 2],
                "award": ["pole", "fastest_lap", "pole", "fastest_lap"],
                "driver_id": ["b", "b", "b", "a"],
                "constructor_id": ["t1"] * 4,
                "source_url": ["https://wiki"] * 4,
                "fetched_at": ["2026-11-10"] * 4,
            }
        ),
    }

    poles = data.award_events(frames, "pole").set_index("round")
    # R1 existe nas duas fontes: vale a primária (piloto a).
    assert poles.loc[1, "driver_id"] == "a"
    assert poles.loc[1, "source"] == "Jolpica"
    # R2 só existe na fonte complementar.
    assert poles.loc[2, "driver_id"] == "b"
    assert poles.loc[2, "source"] == "Wikipédia"

    fastest = data.award_events(frames, "fastest_lap").set_index("round")
    assert fastest.loc[1, "driver_id"] == "a"
    assert fastest.loc[1, "time"] == "1:20.000"
    assert fastest.loc[2, "driver_id"] == "a"
    assert fastest.loc[2, "source"] == "Wikipédia"
