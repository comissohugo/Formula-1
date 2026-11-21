import pandas as pd

from f1dc import data


def _frames():
    races = pd.DataFrame(
        {
            "season": [2025, 2025],
            "round": [1, 2],
            "race_name": ["GP A", "GP B"],
            "date": ["2025-03-01", "2025-03-15"],
            "has_sprint": [0, 1],
            "circuit_id": ["c1", "c1"],
            "circuit_name": ["Circuito", "Circuito"],
            "circuit_locality": ["Cidade", "Cidade"],
            "circuit_country": ["País", "País"],
        }
    )
    drivers = pd.DataFrame(
        {
            "driver_id": ["a", "b"],
            "full_name": ["Piloto A", "Piloto B"],
            "code": ["AAA", "BBB"],
            "driver_nationality": ["BR", "BR"],
        }
    )
    constructors = pd.DataFrame(
        {
            "constructor_id": ["t1"],
            "name": ["Equipe 1"],
            "constructor_nationality": ["BR"],
        }
    )
    race_results = pd.DataFrame(
        {
            "season": [2025, 2025, 2025, 2025],
            "round": [1, 1, 2, 2],
            "driver_id": ["a", "b", "a", "b"],
            "constructor_id": ["t1"] * 4,
            "constructor_name": ["Equipe 1"] * 4,
            "full_name": ["Piloto A", "Piloto B", "Piloto A", "Piloto B"],
            "position": [1, 2, 1, 20],
            "position_text": ["1", "2", "1", "20"],
            "position_order": [1, 2, 1, 20],
            "points": [25.0, 18.0, 25.0, 0.0],
            "grid": [1, 2, 1, 2],
            "fastest_lap_rank": [1, None, None, None],
            "fastest_lap_time": ["1:20.000", None, None, None],
            "laps": [57, 57, 57, 44],
            "status": ["Finished", "Finished", "Finished", "Disqualified"],
        }
    )
    qualifying = pd.DataFrame(
        {
            "season": [2025, 2025, 2025, 2025],
            "round": [1, 1, 2, 2],
            "driver_id": ["a", "b", "b", "a"],
            "constructor_id": ["t1", "t1", "t1", "t1"],
            "full_name": ["Piloto A", "Piloto B", "Piloto B", "Piloto A"],
            "position": [1, 2, 1, 2],
        }
    )
    sprint_results = pd.DataFrame(
        {
            "season": [2025, 2025],
            "round": [2, 2],
            "driver_id": ["b", "a"],
            "constructor_id": ["t1", "t1"],
            "constructor_name": ["Equipe 1", "Equipe 1"],
            "points": [8.0, 7.0],
            "position_text": ["1", "2"],
            "position": [1, 2],
        }
    )
    driver_standings = pd.DataFrame(
        {
            "season": [2025, 2025],
            "round": [2, 2],
            "driver_id": ["a", "b"],
            "full_name": ["Piloto A", "Piloto B"],
            "position": [1, 2],
            "points": [57.0, 26.0],
            "wins": [2, 0],
            "constructor_ids": ["t1", "t1"],
        }
    )
    constructor_standings = pd.DataFrame(
        {
            "season": [2025],
            "round": [2],
            "constructor_id": ["t1"],
            "constructor_name": ["Equipe 1"],
            "position": [1],
            "points": [83.0],
            "wins": [2],
        }
    )
    return {
        "races": races,
        "drivers": drivers,
        "constructors": constructors,
        "race_results": race_results,
        "qualifying_results": qualifying,
        "sprint_results": sprint_results,
        "driver_standings": driver_standings,
        "constructor_standings": constructor_standings,
        "seasons": pd.DataFrame(
            [{"season": 2025, "races_count": 2, "champion_driver_id": "a"}]
        ),
        "circuits": pd.DataFrame(),
        "import_runs": pd.DataFrame(),
    }


def test_cumulative_points_includes_race_and_sprint():
    frames = _frames()
    cumulative = data.cumulative_points(frames, 2025)

    a = cumulative[cumulative["driver_id"] == "a"].set_index("round")["points"]
    b = cumulative[cumulative["driver_id"] == "b"].set_index("round")["points"]

    assert a.loc[1] == 25.0
    assert a.loc[2] == 57.0  # 25 + 25 corrida + 7 sprint
    assert b.loc[1] == 18.0
    assert b.loc[2] == 26.0  # 18 + 0 + 8 sprint


def test_driver_stats_exclude_dsq_from_wins_and_podiums():
    frames = _frames()
    stats = data.driver_season_stats(frames, 2025, "b")

    assert stats["starts"] == 2
    assert stats["wins"] == 0
    assert stats["podiums"] == 1  # P2 no GP A; DSQ no GP B não conta
    assert stats["dsq"] == 1
    assert stats["points"] == 26.0
    assert stats["official_position"] == 2


def test_head_to_head_counts_only_shared_races():
    frames = _frames()
    h2h = data.head_to_head(frames, 2025, "a", "b")

    assert h2h["quali_a"] == 1
    assert h2h["quali_b"] == 1
    assert h2h["quali_rounds"] == 2
    # GP B tem DSQ do piloto b, então só o GP A entra na comparação de corrida
    assert h2h["race_rounds"] == 1
    assert h2h["race_a"] == 1


def test_teammate_ids():
    frames = _frames()
    assert data.teammate_ids(frames, 2025, "a") == ["b"]


def test_period_driver_rankings_sums_race_and_sprint():
    frames = _frames()
    rankings = data.period_driver_rankings(frames).set_index("driver_id")

    assert rankings.loc["a", "points"] == 57.0  # 50 corrida + 7 sprint
    assert rankings.loc["b", "points"] == 26.0  # 18 corrida + 8 sprint
    assert rankings.loc["a", "wins"] == 2
    assert rankings.loc["a", "podiums"] == 2
    assert rankings.loc["a", "poles"] == 1
    assert rankings.loc["b", "poles"] == 1
    assert rankings.loc["a", "fastest_laps"] == 1
    assert rankings.loc["b", "dsq"] == 1
    assert rankings.loc["a", "seasons"] == 1
    assert rankings.loc["a", "titles"] == 1
    assert rankings.loc["b", "titles"] == 0
    assert rankings.loc["a", "teams"] == "Equipe 1"


def test_champions_timeline_merges_driver_and_team():
    timeline = data.champions_timeline(_frames())

    assert len(timeline) == 1
    row = timeline.iloc[0]
    assert row["season"] == 2025
    assert row["full_name"] == "Piloto A"
    assert row["driver_points"] == 57.0
    assert row["constructor_name"] == "Equipe 1"
    assert row["team_points"] == 83.0


def test_in_progress_season_keeps_stats_but_does_not_count_title(monkeypatch):
    monkeypatch.setattr(data.config, "IN_PROGRESS_SEASONS", {2025})
    monkeypatch.setattr(data.config, "CLINCHED_CHAMPIONS", {})
    frames = _frames()

    rankings = data.period_driver_rankings(frames).set_index("driver_id")
    # Estatísticas da temporada em andamento entram no ranking...
    assert rankings.loc["a", "wins"] == 2
    assert rankings.loc["a", "starts"] == 2
    # ...mas o líder atual não é contado como campeão.
    assert rankings.loc["a", "titles"] == 0

    assert data.champions_timeline(frames).empty


def test_clinched_title_counts_in_ranking_and_timeline(monkeypatch):
    monkeypatch.setattr(data.config, "IN_PROGRESS_SEASONS", {2025})
    monkeypatch.setattr(
        data.config,
        "CLINCHED_CHAMPIONS",
        {2025: {"driver": "a", "constructor": "t1"}},
    )
    frames = _frames()

    rankings = data.period_driver_rankings(frames).set_index("driver_id")
    assert rankings.loc["a", "titles"] == 1
    assert rankings.loc["b", "titles"] == 0

    timeline = data.champions_timeline(frames)
    assert len(timeline) == 1
    row = timeline.iloc[0]
    assert row["season"] == 2025
    assert row["status"] == "em andamento (matemático)"
    assert row["full_name"] == "Piloto A"
    assert row["constructor_name"] == "Equipe 1"


def test_season_extras_counts_podiums_and_poles():
    frames = _frames()

    drivers = data.season_driver_extras(frames, 2025)
    assert drivers.loc["a", "podiums"] == 2
    assert drivers.loc["b", "podiums"] == 1  # R2 foi desclassificado
    assert drivers.loc["a", "poles"] == 1
    assert drivers.loc["b", "poles"] == 1

    teams = data.season_constructor_extras(frames, 2025)
    assert teams.loc["t1", "podiums"] == 3
    assert teams.loc["t1", "poles"] == 2


def test_season_extras_empty_season_has_columns():
    extras = data.season_driver_extras(_frames(), 1999)
    assert extras.empty
    assert list(extras.columns) == ["podiums", "poles"]


def test_circuit_editions_lists_each_season():
    editions = data.circuit_editions(_frames(), "c1")

    assert list(editions["season"]) == [2025, 2025]
    assert list(editions["winner"]) == ["Piloto A", "Piloto A"]
    assert list(editions["pole"]) == ["Piloto A", "Piloto B"]
    assert editions.loc[0, "fastest_lap"] == "Piloto A"
    assert pd.isna(editions.loc[1, "fastest_lap"])


def test_period_head_to_head_excludes_dsq_from_race():
    h2h = data.period_head_to_head(_frames(), "a", "b")

    assert h2h["quali_rounds"] == 2
    assert h2h["quali_a"] == 1
    assert h2h["quali_b"] == 1
    assert h2h["race_rounds"] == 1  # GP B: b desclassificado
    assert h2h["race_a"] == 1
    assert h2h["race_b"] == 0


def test_constructor_points_by_season_sums_race_and_sprint():
    table = data.constructor_points_by_season(_frames())

    assert list(table["season"]) == [2025]
    assert table.loc[0, "Equipe 1"] == 83.0  # 68 corrida + 15 sprint


def _circuit_frames():
    """Três circuitos, vitórias repetidas, empate e um P1 desclassificado."""
    races = pd.DataFrame(
        {
            "season": [2023, 2024, 2024, 2024, 2025, 2025, 2025],
            "round": [1, 1, 2, 3, 1, 2, 3],
            "circuit_id": ["c3", "c1", "c2", "c1", "c1", "c2", "c3"],
            "circuit_name": [
                "Circuito 3", "Circuito 1", "Circuito 2", "Circuito 1",
                "Circuito 1", "Circuito 2", "Circuito 3",
            ],
            "circuit_country": ["US", "BR", "IT", "BR", "BR", "IT", "US"],
        }
    )
    drivers = pd.DataFrame(
        {
            "driver_id": ["a", "b"],
            "full_name": ["Piloto A", "Piloto B"],
        }
    )
    constructors = pd.DataFrame(
        {"constructor_id": ["t1"], "name": ["Equipe 1"]}
    )
    rows = [
        # temporada, rodada, vencedor, segundo, posição_texto do vencedor
        (2023, 1, "b", "a", "1"),
        (2024, 1, "a", "b", "1"),
        (2024, 2, "b", "a", "1"),
        (2024, 3, "a", "b", "D"),  # P1 desclassificado não é vitória
        (2025, 1, "a", "b", "1"),
        (2025, 2, "b", "a", "1"),
        (2025, 3, "b", "a", "1"),
    ]
    records = []
    for season, round_, winner, second, winner_text in rows:
        for driver_id, position, text in (
            (winner, 1, winner_text),
            (second, 2, "2"),
        ):
            records.append(
                {
                    "season": season,
                    "round": round_,
                    "driver_id": driver_id,
                    "constructor_id": "t1",
                    "constructor_name": "Equipe 1",
                    "full_name": "Piloto A" if driver_id == "a" else "Piloto B",
                    "position": position,
                    "position_text": text,
                    "position_order": position,
                    "points": 25.0 if position == 1 and text == "1" else 0.0,
                    "grid": position,
                    "fastest_lap_rank": None,
                    "laps": 50,
                    "status": "Disqualified" if text == "D" else "Finished",
                }
            )
    return {
        "races": races,
        "drivers": drivers,
        "constructors": constructors,
        "race_results": pd.DataFrame(records),
        "qualifying_results": pd.DataFrame(
            columns=["season", "round", "driver_id", "constructor_id", "position"]
        ),
        "sprint_results": pd.DataFrame(
            columns=["season", "round", "driver_id", "points"]
        ),
        "driver_standings": pd.DataFrame(
            {
                "season": [2023, 2024, 2025],
                "round": [1, 3, 3],
                "driver_id": ["b", "a", "b"],
                "position": [1, 1, 1],
            }
        ),
        "constructor_standings": pd.DataFrame(),
        "circuits": pd.DataFrame(),
    }


def test_driver_circuit_stats_counts_wins_and_starts():
    stats = data.driver_circuit_stats(_circuit_frames(), "a")

    c1 = stats[stats["circuit_id"] == "c1"].iloc[0]
    assert c1["wins"] == 2
    assert c1["starts"] == 3  # inclui o GP em que terminou em P1 desclassificado
    assert c1["win_pct"] == 66.7
    c2 = stats[stats["circuit_id"] == "c2"].iloc[0]
    assert c2["wins"] == 0


def test_driver_circuit_stats_unknown_driver_returns_empty():
    stats = data.driver_circuit_stats(_circuit_frames(), "inexistente")

    assert stats.empty
    assert "wins" in stats.columns


def test_favorite_circuit_picks_single_leader():
    favorite = data.favorite_circuit(_circuit_frames(), "a")

    assert favorite["wins"] == 2
    assert favorite["label"] == "Circuito 1 (BR)"
    assert favorite["others"] == []


def test_favorite_circuit_lists_ties_alphabetically():
    favorite = data.favorite_circuit(_circuit_frames(), "b")

    assert favorite["wins"] == 2
    assert favorite["label"] == "Circuito 2 (IT)"
    assert favorite["others"] == ["Circuito 3 (US)"]


def test_favorite_circuit_is_none_without_wins():
    assert data.favorite_circuit(_circuit_frames(), "inexistente") is None


def test_period_top_winners_orders_by_wins_and_maps_favorite():
    top = data.period_top_winners(_circuit_frames(), limit=10)

    assert list(top["driver_id"]) == ["b", "a"]
    assert top.loc[0, "wins"] == 4
    assert top.loc[0, "win_pct"] == 57.1
    assert top.loc[0, "favorite"] == "Circuito 2 (IT)"
    assert top.loc[0, "tied"] == ["Circuito 3 (US)"]
    assert top.loc[1, "favorite"] == "Circuito 1 (BR)"
    assert top.loc[1, "tied"] == []


def test_circuit_top_winners_limits_and_calculates_percentage():
    top = data.circuit_top_winners(_circuit_frames(), "c3", limit=5)

    assert list(top["driver_id"]) == ["b"]
    assert top.loc[0, "wins"] == 2
    assert top.loc[0, "starts"] == 2
    assert top.loc[0, "win_pct"] == 100.0


def test_circuit_top_winners_unknown_circuit_returns_empty():
    top = data.circuit_top_winners(_circuit_frames(), "inexistente")

    assert top.empty
    assert "wins" in top.columns


def _inactive_frames():
    """Circuitos que saíram, um que voltou e um com empate de vitórias."""
    circuitos = {
        "old": ("Antigo", "IT", ["GP Antigo", "GP Antigo"]),
        "rot": ("Rotativo", "FR", ["GP Rotativo", "GP Rotativo"]),
        "cur": ("Atual", "BR", ["GP Atual", "GP Atual"]),
        "tie": ("Empate", "US", ["GP Empate", "GP Empate"]),
    }
    # temporada, rodada, circuito, vencedor
    corridas = [
        (2020, 1, "old", "a"),
        (2021, 1, "old", "a"),
        (2020, 2, "rot", "b"),
        (2022, 1, "rot", "b"),
        (2020, 3, "cur", "a"),
        (2022, 2, "cur", "a"),
        (2019, 1, "tie", "a"),
        (2019, 2, "tie", "b"),
    ]
    races = pd.DataFrame(
        [
            {
                "season": season,
                "round": round_,
                "circuit_id": cid,
                "circuit_name": circuitos[cid][0],
                "circuit_country": circuitos[cid][1],
                "race_name": circuitos[cid][2][0],
            }
            for season, round_, cid, _ in corridas
        ]
    )
    drivers = pd.DataFrame(
        {
            "driver_id": ["a", "b"],
            "full_name": ["Piloto A", "Piloto B"],
        }
    )
    records = []
    for season, round_, cid, winner in corridas:
        for driver_id, position in ((winner, 1), ("b" if winner == "a" else "a", 2)):
            records.append(
                {
                    "season": season,
                    "round": round_,
                    "driver_id": driver_id,
                    "constructor_id": "t1",
                    "constructor_name": "Equipe 1",
                    "full_name": "Piloto A" if driver_id == "a" else "Piloto B",
                    "position": position,
                    "position_text": str(position),
                    "position_order": position,
                    "points": 25.0 if position == 1 else 18.0,
                    "grid": position,
                    "fastest_lap_rank": None,
                    "laps": 50,
                    "status": "Finished",
                }
            )
    return {
        "races": races,
        "drivers": drivers,
        "constructors": pd.DataFrame(
            {"constructor_id": ["t1"], "name": ["Equipe 1"]}
        ),
        "race_results": pd.DataFrame(records),
    }


def test_inactive_circuits_lists_departures_and_ignores_current():
    table = data.inactive_circuits(_inactive_frames(), reference_season=2022)

    # "rot" está no calendário de 2022; "cur" também.
    assert list(table["circuit_id"]) == ["old", "tie"]
    antigo = table[table["circuit_id"] == "old"].iloc[0]
    assert antigo["last_season"] == 2021
    assert antigo["seasons_absent"] == 1
    assert antigo["editions"] == 2
    assert antigo["last_race_name"] == "GP Antigo"
    assert antigo["biggest_winner"] == "Piloto A"
    assert antigo["biggest_wins"] == 2
    assert antigo["tied"] == []


def test_inactive_circuits_min_seasons_absent_skips_recent_departure():
    table = data.inactive_circuits(
        _inactive_frames(), reference_season=2022, min_seasons_absent=2
    )

    assert list(table["circuit_id"]) == ["tie"]


def test_inactive_circuits_lists_tied_winners():
    table = data.inactive_circuits(_inactive_frames(), reference_season=2022)

    empate = table[table["circuit_id"] == "tie"].iloc[0]
    assert empate["biggest_winner"] == "Piloto A"
    assert empate["biggest_wins"] == 1
    assert empate["tied"] == ["Piloto B"]
    assert empate["seasons_absent"] == 3


def test_inactive_circuits_defaults_to_last_season_and_handles_empty():
    assert data.inactive_circuits(_inactive_frames())["seasons_absent"].min() == 1

    vazio = data.inactive_circuits(
        {"races": pd.DataFrame(columns=["season", "round"])}
    )
    assert vazio.empty
    assert "seasons_absent" in vazio.columns


def test_race_name_alias_uses_official_name_and_keeps_provenience(monkeypatch):
    alias = {
        (2026, 7): {
            "primary_name": "Barcelona Grand Prix",
            "official_name": "Barcelona-Catalunya Grand Prix",
            "source_url": "https://www.formula1.com/en/racing/2026/barcelona-catalunya",
            "verified_at": "2026-11-21",
        }
    }
    monkeypatch.setattr(data.config, "RACE_NAME_ALIASES", alias)
    races = pd.DataFrame(
        {
            "season": [2026, 2026],
            "round": [7, 14],
            "race_name": ["Barcelona Grand Prix", "Spanish Grand Prix"],
        }
    )

    result = data.apply_race_name_aliases(races)

    barcelona = result[result["round"] == 7].iloc[0]
    assert barcelona["race_name"] == "Barcelona-Catalunya Grand Prix"
    assert barcelona["race_name_source"] == "official"
    assert barcelona["race_name_source_url"] == alias[(2026, 7)]["source_url"]
    assert barcelona["race_name_verified_at"] == "2026-11-21"

    madrid = result[result["round"] == 14].iloc[0]
    assert madrid["race_name"] == "Spanish Grand Prix"
    assert madrid["race_name_source"] == "Jolpica"
    assert pd.isna(madrid["race_name_source_url"])
    assert races.loc[0, "race_name"] == "Barcelona Grand Prix"  # sem mutar a entrada


def test_race_name_alias_ignores_unexpected_primary_name(monkeypatch):
    alias = {
        (2026, 7): {
            "primary_name": "Barcelona Grand Prix",
            "official_name": "Barcelona-Catalunya Grand Prix",
            "source_url": "https://example.com",
            "verified_at": "2026-11-21",
        }
    }
    monkeypatch.setattr(data.config, "RACE_NAME_ALIASES", alias)
    races = pd.DataFrame(
        {"season": [2026], "round": [7], "race_name": ["Outro Nome na Primária"]}
    )

    result = data.apply_race_name_aliases(races)

    assert result.loc[0, "race_name"] == "Outro Nome na Primária"
    assert result.loc[0, "race_name_source"] == "Jolpica"
