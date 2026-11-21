import pytest

from f1dc import transform


def test_to_int_and_float_preserve_missing():
    assert transform.to_int("") is None
    assert transform.to_int(None) is None
    assert transform.to_int("12") == 12
    assert transform.to_float("") is None
    assert transform.to_float("0") == 0.0
    assert transform.to_float("12.5") == 12.5


def test_position_text_classification():
    assert transform.is_retired("R")
    assert transform.is_disqualified("D")
    assert transform.is_classified("1")
    assert transform.is_classified("R") is False
    assert transform.is_classified("D") is False
    assert transform.is_classified(None) is False


def test_disqualification_detected_by_status_only():
    # Caso real: Russell em Spa 2024 vem com positionText "20" e status Disqualified.
    assert transform.is_disqualified("20", "Disqualified")
    assert transform.is_classified("20", "Disqualified") is False
    assert transform.is_classified("20", "Finished") is True


def test_race_row_writes_official_name_for_aliased_round():
    race = {
        "season": "2026",
        "round": "7",
        "raceName": "Barcelona Grand Prix",
        "Circuit": {"circuitId": "catalunya"},
    }
    row = transform.race_row(race, False, "url", "now")
    assert row["race_name"] == "Barcelona-Catalunya Grand Prix"


def test_race_row_keeps_other_names_untouched():
    race = {
        "season": "2026",
        "round": "14",
        "raceName": "Spanish Grand Prix",
        "Circuit": {"circuitId": "madring"},
    }
    row = transform.race_row(race, False, "url", "now")
    assert row["race_name"] == "Spanish Grand Prix"


def test_race_result_row_without_fastest_lap():
    item = {
        "Driver": {"driverId": "norris", "givenName": "Lando", "familyName": "Norris"},
        "Constructor": {"constructorId": "mclaren", "name": "McLaren"},
        "number": "4",
        "grid": "2",
        "position": "1",
        "positionText": "1",
        "positionOrder": "1",
        "points": "25",
        "laps": "57",
        "status": "Finished",
        "statusId": "1",
        "Time": {"millis": "5000000", "time": "1:23:24.111"},
    }
    row = transform.race_result_row(2025, 1, item, "url", "2026-01-01T00:00:00+00:00")
    assert row["driver_id"] == "norris"
    assert row["constructor_id"] == "mclaren"
    assert row["position"] == 1
    assert row["grid"] == 2
    assert row["points"] == 25.0
    assert row["time_millis"] == 5000000
    # ausente continua ausente (não vira 0)
    assert row["fastest_lap_rank"] is None
    assert row["fastest_lap_time"] is None
    assert row["fastest_lap_speed"] is None


def test_qualifying_row_keeps_empty_sessions_as_none():
    item = {
        "Driver": {"driverId": "leclerc"},
        "Constructor": {"constructorId": "ferrari"},
        "number": "16",
        "position": "1",
        "Q1": "1:20.000",
        "Q2": "1:19.500",
    }
    row = transform.qualifying_row(2025, 1, item, "url", "now")
    assert row["q1"] == "1:20.000"
    assert row["q2"] == "1:19.500"
    assert row["q3"] is None


def test_driver_row_builds_full_name():
    row = transform.driver_row(
        {"driverId": "max_verstappen", "givenName": "Max", "familyName": "Verstappen"}
    )
    assert row["full_name"] == "Max Verstappen"
    assert row["driver_id"] == "max_verstappen"
