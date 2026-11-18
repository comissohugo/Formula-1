import sqlite3

from f1dc import ingest


def _driver(driver_id, name):
    return {
        "driverId": driver_id,
        "givenName": name,
        "familyName": "Test",
        "code": name[:3].upper(),
        "permanentNumber": "1",
        "nationality": "Test",
    }


DRIVERS = {"a": _driver("a", "Alpha"), "b": _driver("b", "Beta")}
TEAM = {"constructorId": "t1", "name": "Team One", "nationality": "Test"}


def _result(driver_id, position, points, grid, position_text=None):
    return {
        "Driver": DRIVERS[driver_id],
        "Constructor": TEAM,
        "number": "1",
        "grid": str(grid),
        "position": str(position),
        "positionText": position_text or str(position),
        "positionOrder": str(position),
        "points": str(points),
        "laps": "57",
        "status": "Finished",
        "statusId": "1",
        "Time": {"millis": "5000000", "time": "1:23:24.111"},
        "FastestLap": {
            "rank": "1",
            "lap": "50",
            "Time": {"time": "1:20.000"},
            "AverageSpeed": {"speed": "210.5", "units": "kph"},
        },
    }


RACES = [
    {
        "season": "2021",
        "round": "1",
        "raceName": "GP One",
        "date": "2021-03-28",
        "Circuit": {
            "circuitId": "c1",
            "circuitName": "Circuit One",
            "Location": {"locality": "City", "country": "Country", "lat": "1", "long": "2"},
        },
    },
    {
        "season": "2021",
        "round": "2",
        "raceName": "GP Two",
        "date": "2021-04-18",
        "Circuit": {
            "circuitId": "c1",
            "circuitName": "Circuit One",
            "Location": {"locality": "City", "country": "Country", "lat": "1", "long": "2"},
        },
    },
]


class FakeClient:
    """Substitui a API para testar a importação sem rede."""

    def __init__(self):
        self.request_count = 0

    def races(self, season):
        self.request_count += 1
        return RACES

    def sprint_rounds(self, season):
        self.request_count += 1
        return [2]

    def race_results(self, season, round_):
        self.request_count += 1
        return [_result("a", 1, 25, 1), _result("b", 2, 18, 2)]

    def qualifying(self, season, round_):
        self.request_count += 1
        return [
            {
                "Driver": DRIVERS["a"],
                "Constructor": TEAM,
                "number": "1",
                "position": "1",
                "Q1": "1:20.0",
                "Q2": "1:19.0",
                "Q3": "1:18.0",
            },
            {
                "Driver": DRIVERS["b"],
                "Constructor": TEAM,
                "number": "2",
                "position": "2",
                "Q1": "1:20.5",
                "Q2": "1:19.5",
            },
        ]

    def sprint_results(self, season, round_):
        self.request_count += 1
        return [_result("b", 1, 3, 1), _result("a", 2, 2, 2)]

    def driver_standings(self, season):
        self.request_count += 1
        return [
            ("2021", "2", {"Driver": DRIVERS["a"], "Constructors": [TEAM], "position": "1", "positionText": "1", "points": "50", "wins": "2"}),
            ("2021", "2", {"Driver": DRIVERS["b"], "Constructors": [TEAM], "position": "2", "positionText": "2", "points": "41", "wins": "0"}),
        ]

    def constructor_standings(self, season):
        self.request_count += 1
        return [
            ("2021", "2", {"Constructor": TEAM, "position": "1", "positionText": "1", "points": "91", "wins": "2"})
        ]


def test_import_writes_complete_season(tmp_path):
    db_path = tmp_path / "f1.db"
    result = ingest.import_seasons(
        seasons=[2021], db_path=str(db_path), client=FakeClient(), log_fn=lambda _: None
    )

    assert result["status"] == "ok"
    assert result["seasons"][2021]["races"] == 2
    assert result["seasons"][2021]["results_races"] == 2
    assert result["seasons"][2021]["qualifying_races"] == 2
    assert result["seasons"][2021]["sprint_races"] == 1
    assert result["seasons"][2021]["champion_driver"] == "a"

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM races").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM race_results").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM qualifying_results").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM sprint_results").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM fastest_laps").fetchone()[0] == 4
        has_sprint = conn.execute(
            'SELECT has_sprint FROM races WHERE "round" = 2'
        ).fetchone()[0]
        assert has_sprint == 1
        assert conn.execute("SELECT COUNT(*) FROM import_runs").fetchone()[0] == 1
    finally:
        conn.close()


def test_reimport_does_not_duplicate(tmp_path):
    db_path = tmp_path / "f1.db"
    for _ in range(2):
        ingest.import_seasons(
            seasons=[2021], db_path=str(db_path), client=FakeClient(), log_fn=lambda _: None
        )

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM races").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM race_results").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM import_runs").fetchone()[0] == 2
    finally:
        conn.close()


class PartialSeasonClient(FakeClient):
    """Simula temporada em andamento: a rodada 2 ainda não tem resultado."""

    def race_results(self, season, round_):
        self.request_count += 1
        if int(round_) == 2:
            return []
        return [_result("a", 1, 25, 1), _result("b", 2, 18, 2)]


def test_in_progress_import_keeps_only_completed_rounds(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest.config, "IN_PROGRESS_SEASONS", {2021})
    db_path = tmp_path / "f1.db"
    result = ingest.import_seasons(
        seasons=[2021],
        db_path=str(db_path),
        client=PartialSeasonClient(),
        log_fn=lambda _: None,
    )

    assert result["status"] == "ok"
    assert result["seasons"][2021]["races"] == 1
    assert result["seasons"][2021]["in_progress"] is True
    assert result["seasons"][2021]["champion_driver"] is None
    assert result["seasons"][2021]["champion_constructor"] is None

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM races").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM race_results").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM sprint_results").fetchone()[0] == 0
        champion = conn.execute(
            "SELECT champion_driver_id, champion_constructor_id FROM seasons"
        ).fetchone()
        assert champion == (None, None)
    finally:
        conn.close()


class FailingResultsClient(FakeClient):
    def race_results(self, season, round_):
        self.request_count += 1
        raise ingest.ApiError("falha simulada")


def test_in_progress_error_does_not_overwrite_existing_data(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest.config, "IN_PROGRESS_SEASONS", {2021})
    db_path = tmp_path / "f1.db"
    ingest.import_seasons(
        seasons=[2021],
        db_path=str(db_path),
        client=FakeClient(),
        log_fn=lambda _: None,
    )

    result = ingest.import_seasons(
        seasons=[2021],
        db_path=str(db_path),
        client=FailingResultsClient(),
        log_fn=lambda _: None,
    )

    assert result["status"] == "incomplete"
    assert 2021 not in result["seasons"]

    conn = sqlite3.connect(db_path)
    try:
        # A base anterior foi preservada.
        assert conn.execute("SELECT COUNT(*) FROM races").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM race_results").fetchone()[0] == 4
    finally:
        conn.close()
