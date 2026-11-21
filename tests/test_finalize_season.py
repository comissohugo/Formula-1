from pathlib import Path

from scripts import finalize_season as fs


CONFIG_SOURCE = (
    Path(__file__).resolve().parents[1] / "f1dc" / "config.py"
).read_text(encoding="utf-8")


class FakeClient:
    """Fonte controlada para testar as barreiras de encerramento."""

    def __init__(self, final_round: int = 23, with_last_results: bool = True):
        self.final_round = final_round
        self.with_last_results = with_last_results

    def races(self, season):
        return [
            {"season": str(season), "round": str(r)} for r in range(1, 24)
        ]

    def sprint_rounds(self, season):
        return [6, 8, 14, 17, 20, 23]

    def driver_standings(self, season):
        return [
            (
                str(season),
                str(self.final_round),
                {"position": "1", "Driver": {"driverId": "antonelli"}},
            ),
            (
                str(season),
                str(self.final_round),
                {"position": "2", "Driver": {"driverId": "norris"}},
            ),
        ]

    def constructor_standings(self, season):
        return [
            (
                str(season),
                str(self.final_round),
                {"position": "1", "Constructor": {"constructorId": "mercedes"}},
            ),
            (
                str(season),
                str(self.final_round),
                {"position": "2", "Constructor": {"constructorId": "mclaren"}},
            ),
        ]

    def race_results(self, season, round_):
        if round_ == 23 and self.with_last_results:
            return [{"driverId": "antonelli"}]
        return []


def test_finalize_config_text_moves_season_to_closed_expectations():
    result = fs.finalize_config_text(CONFIG_SOURCE, 2026, 23, 6, "antonelli", "mercedes")

    assert "IN_PROGRESS_SEASONS = set()" in result
    assert "IN_PROGRESS_CALENDAR_RACES = {}" in result
    assert "IN_PROGRESS_CALENDAR_SPRINTS = {}" in result
    assert "CLINCHED_CHAMPIONS = {}" in result
    assert "2025: 24,\n    2026: 23,\n}\nEXPECTED_SPRINTS = {" in result
    assert "2025: 6,\n    2026: 6,\n}\n\n# Conferência externa" in result
    assert (
        '2025: ("norris", "mclaren"),\n'
        '    2026: ("antonelli", "mercedes"),\n}'
    ) in result
    compile(result, "config.py", "exec")  # sintaxe válida


def test_preflight_accepts_complete_source():
    facts = fs.preflight(FakeClient(), 2026, 23, 6, "antonelli", "mercedes")

    assert facts["ok"] is True
    assert facts["problems"] == []
    assert facts["rounds"] == list(range(1, 24))
    assert facts["sprints"] == [6, 8, 14, 17, 20, 23]
    assert facts["champion_driver"] == "antonelli"
    assert facts["champion_constructor"] == "mercedes"


def test_preflight_blocks_incomplete_source():
    facts = fs.preflight(
        FakeClient(final_round=22, with_last_results=False),
        2026,
        23,
        6,
        "antonelli",
        "mercedes",
    )

    assert facts["ok"] is False
    joined = " ".join(facts["problems"])
    assert "sem resultado na API para R23" in joined
    assert "standings da API são do(s) round(s) [22]" in joined
