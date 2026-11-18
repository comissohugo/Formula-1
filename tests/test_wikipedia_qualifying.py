import pandas as pd

from f1dc import data, db, wikipedia_qualifying

DRIVERS = [f"Piloto {i}" for i in range(1, 12)]


def _wikitext(count: int = 10, dnq: bool = True) -> str:
    rows = []
    for position, name in enumerate(DRIVERS[:count], start=1):
        rows.append(
            "\n".join(
                [
                    "|-",
                    f'! scope="row" | {position}',
                    f'| align="center" | {position}',
                    f'| data-sort-value="P{position}" | {{{{flagicon|Brazil}}}} [[{name}]]',
                    "| [[Equipe Um|Equipe 1]]",
                    f"| 1:{20 + position:02d}.000",
                    f"| +0.{position:03d}",
                    f'| align="center" | {position}',
                ]
            )
        )
    if dnq:
        rows.append(
            "\n".join(
                [
                    "|-",
                    '! scope="row" data-sort-value="11" | '
                    "{{Abbr|DNQ|Did not qualify}}",
                    '| align="center" | 22',
                    "| {{flagicon|Malaysia}} [[Alex Yoong]]",
                    "| [[Minardi]]",
                    "| —",
                    "| —",
                    '| align="center" | 22',
                ]
            )
        )
    return (
        '{| class="wikitable sortable"\n'
        "|-\n"
        '! scope="col" | {{Abbr|Pos|Position}}\n'
        '! scope="col" | {{Abbr|No|Car number}}\n'
        '! scope="col" | Driver\n'
        '! scope="col" | Constructor\n'
        '! scope="col" | Time\n'
        '! scope="col" | {{Abbr|Gap|Gap to the fastest driver}}\n'
        '! scope="col" | {{Abbr|Grid|Final grid position}}\n'
        + "\n".join(rows)
        + "\n|}"
    )


def _wikitext_2001(count: int = 10) -> str:
    """Formato das páginas de 2001: coluna ``Lap`` e grid via Tooltip."""
    rows = []
    for position, name in enumerate(DRIVERS[:count], start=1):
        rows.append(
            "\n".join(
                [
                    "|-",
                    f'! scope="row" | {position}',
                    f'| align="center" | {position}',
                    f'| data-sort-value="P{position}" | {{{{flagicon|Brazil}}}} [[{name}]]',
                    "| [[Equipe Um|Equipe 1]]",
                    f"| 1:{20 + position:02d}.000",
                    f"| +0.{position:03d}",
                    f'| align="center" | {position}',
                ]
            )
        )
    return (
        '{| class="wikitable sortable"\n'
        "|-\n"
        '! scope="col" | {{Abbr|Pos|Position}}\n'
        '! scope="col" | {{Abbr|No.|Car number}}\n'
        '! scope="col" | Driver\n'
        '! scope="col" | Constructor\n'
        '! scope="col" | Lap\n'
        '! scope="col" | {{Abbr|Gap|Gap to the fastest driver}}\n'
        '! scope="col" | {{Tooltip|Grid|Final grid position}}\n'
        + "\n".join(rows)
        + "\n|}"
    )


def test_parse_qualifying_table_accepts_2001_lap_header():
    parsed = wikipedia_qualifying.parse_qualifying_table(_wikitext_2001())

    assert len(parsed["rows"]) == 10
    assert parsed["rows"][0]["time"] == "1:21.000"
    assert parsed["skipped"] == []


def test_parse_qualifying_table_ignores_race_table_with_laps():
    race_table = (
        '{| class="wikitable"\n'
        "|-\n"
        '! Pos !! Driver !! Constructor !! Laps !! Time/Retired !! Grid\n'
        "|-\n"
        "! 1\n"
        "| [[Piloto 1]] || [[Equipe Um|Equipe 1]] || 58 || 1:30:00.000 || 1\n"
        "|}"
    )
    parsed = wikipedia_qualifying.parse_qualifying_table(
        race_table + "\n\n" + _wikitext_2001()
    )

    assert parsed["rows"][0]["time"] == "1:21.000"


def _wikitext_2000(count: int = 10) -> str:
    """Formato de 2000: cabeçalho compacto, sem grid, com {{sort}}/{{sortname}}."""
    rows = []
    for position, name in enumerate(DRIVERS[:count], start=1):
        if position == 1:
            position_cell = "{{sort|01|1}}"
            driver_cell = "{{flagicon|Brazil}} {{sortname|Piloto|1}}"
        else:
            position_cell = str(position)
            driver_cell = f"{{{{flagicon|Brazil}}}} [[{name}]]"
        rows.append(
            "\n".join(
                [
                    "|-",
                    f"! {position_cell}",
                    f"| {position}",
                    f"| {driver_cell}",
                    "| [[Equipe Um|Equipe 1]]",
                    f"| 1:{20 + position:02d}.000",
                    f"| +0.{position:03d}",
                ]
            )
        )
    return (
        '{| class="wikitable sortable"\n'
        "! Pos !! No !! Driver !! Constructor !! Time !! Gap\n"
        + "\n".join(rows)
        + "\n|}"
    )


def test_parse_qualifying_table_accepts_2000_compact_header_without_grid():
    parsed = wikipedia_qualifying.parse_qualifying_table(_wikitext_2000())

    assert len(parsed["rows"]) == 10
    assert parsed["rows"][0]["position"] == 1
    assert parsed["rows"][0]["driver"] == "Piloto 1"
    assert parsed["rows"][0]["time"] == "1:21.000"
    assert parsed["skipped"] == []


def test_parse_qualifying_table_extracts_positions_and_times():
    parsed = wikipedia_qualifying.parse_qualifying_table(_wikitext())

    assert len(parsed["rows"]) == 10
    assert parsed["rows"][0]["position"] == 1
    assert parsed["rows"][0]["driver"] == "Piloto 1"
    assert parsed["rows"][0]["time"] == "1:21.000"
    assert parsed["rows"][-1]["position"] == 10
    assert parsed["skipped"] == [{"reason": "DNQ", "driver": "Alex Yoong"}]


def test_parse_qualifying_table_rejects_missing_time():
    text = _wikitext().replace("1:21.000", "—")

    try:
        wikipedia_qualifying.parse_qualifying_table(text)
    except ValueError as exc:
        assert "tempo ausente" in str(exc)
    else:  # pragma: no cover - falha explícita
        raise AssertionError("esperava erro para tempo ausente")


def _seed_db(path, *, wrong_primary_time: bool = False):
    conn = db.connect(path)
    db.init_db(conn)
    conn.executemany(
        "INSERT INTO drivers(driver_id, full_name) VALUES (?, ?)",
        [(f"d{i}", name) for i, name in enumerate(DRIVERS[:10], start=1)],
    )
    conn.execute(
        "INSERT INTO constructors(constructor_id, name) VALUES ('t1', 'Equipe 1')"
    )
    conn.executemany(
        'INSERT INTO races(season, "round", race_name) VALUES (2099, ?, ?)',
        [(1, "GP Um"), (2, "GP Dois")],
    )
    results = []
    primaries = []
    for round_ in (1, 2):
        for position in range(1, 11):
            results.append((2099, round_, f"d{position}", "t1", position, str(position)))
            if round_ == 1:
                time = "9:99.999" if wrong_primary_time and position == 1 else (
                    f"1:{20 + position:02d}.000"
                )
                primaries.append(
                    (2099, 1, f"d{position}", "t1", str(position), position, time)
                )
    conn.executemany(
        """
        INSERT INTO race_results(
            season, "round", driver_id, constructor_id, number, position
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        results,
    )
    conn.executemany(
        """
        INSERT INTO qualifying_results(
            season, "round", driver_id, constructor_id, number, position, q1
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        primaries,
    )
    conn.commit()
    conn.close()


def _fetcher(season, race):
    assert season == 2099
    return _wikitext()


def test_import_fills_only_races_missing_primary_qualifying(tmp_path):
    path = str(tmp_path / "test.db")
    _seed_db(path)

    result = wikipedia_qualifying.import_seasons(
        seasons=[2099],
        db_path=path,
        fetcher=_fetcher,
        now="2026-11-10T00:00:00+00:00",
    )

    assert result["status"] == "ok"
    info = result["seasons"][2099]
    assert info["filled_races"] == 1
    assert info["confirmed_primary"] == 1
    assert info["rows"] == 10
    assert info["skipped"] == [
        "R1: Alex Yoong (DNQ)",
        "R2: Alex Yoong (DNQ)",
    ]

    conn = db.connect(path)
    r1 = conn.execute(
        'SELECT COUNT(*) AS n, SUM(source_url IS NOT NULL) AS sourced '
        'FROM qualifying_results WHERE season = 2099 AND "round" = 1'
    ).fetchone()
    r2 = conn.execute(
        'SELECT COUNT(*) AS n, SUM(source_url IS NOT NULL) AS sourced, '
        'SUM(q1 IS NOT NULL) AS times FROM qualifying_results '
        'WHERE season = 2099 AND "round" = 2'
    ).fetchone()
    conn.close()

    # R1 continua sendo a fonte primária, sem source_url e sem duplicar.
    assert (r1["n"], r1["sourced"]) == (10, 0)
    # R2 foi completada com proveniência e tempos.
    assert (r2["n"], r2["sourced"], r2["times"]) == (10, 10, 10)

    # Reimportar não duplica.
    wikipedia_qualifying.import_seasons(
        seasons=[2099],
        db_path=path,
        fetcher=_fetcher,
    )
    conn = db.connect(path)
    total = conn.execute("SELECT COUNT(*) FROM qualifying_results").fetchone()[0]
    conn.close()
    assert total == 20


def test_import_aborts_when_wikipedia_diverges_from_primary(tmp_path):
    path = str(tmp_path / "test.db")
    _seed_db(path, wrong_primary_time=True)

    result = wikipedia_qualifying.import_seasons(
        seasons=[2099],
        db_path=path,
        fetcher=_fetcher,
        now="2026-11-10T00:00:00+00:00",
    )

    assert result["status"] == "incomplete"
    assert any("conferência divergente" in error for error in result["errors"])
    conn = db.connect(path)
    r2 = conn.execute(
        'SELECT COUNT(*) FROM qualifying_results WHERE season = 2099 AND "round" = 2'
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM qualifying_results").fetchone()[0]
    conn.close()
    assert r2 == 0
    assert total == 10


def test_award_events_marks_wikipedia_qualifying_as_complementary():
    frames = {
        "drivers": pd.DataFrame(
            {"driver_id": ["a"], "full_name": ["Piloto A"]}
        ),
        "constructors": pd.DataFrame(
            {"constructor_id": ["t1"], "name": ["Equipe 1"]}
        ),
        "qualifying_results": pd.DataFrame(
            {
                "season": [2002],
                "round": [1],
                "driver_id": ["a"],
                "constructor_id": ["t1"],
                "position": [1],
                "source_url": ["https://en.wikipedia.org/wiki/2002_Australian_Grand_Prix"],
            }
        ),
    }

    poles = data.award_events(frames, "pole")

    assert poles.iloc[0]["source"] == "Wikipédia (en)"
    assert poles.iloc[0]["source_url"].endswith("2002_Australian_Grand_Prix")
