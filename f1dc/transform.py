"""Conversão das respostas da API em linhas prontas para o banco.

Regra do projeto: dado ausente vira ``None`` (NULL no SQLite), nunca 0.
"""

from __future__ import annotations

from typing import Any

from .api import dedupe

# Status textuais que a Ergast/Jolpica usa para resultados não classificados.
NON_CLASSIFIED = {"R", "D", "E", "W", "F", "N"}


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def driver_id(item: dict[str, Any]) -> str | None:
    return item.get("Driver", {}).get("driverId")


def constructor_id(item: dict[str, Any]) -> str | None:
    return item.get("Constructor", {}).get("constructorId")


def is_retired(position_text: str | None) -> bool:
    """Abandono segundo o positionText oficial (R = retired)."""
    return (position_text or "").upper() == "R"


DSQ_STATUSES = ("disqualified", "excluded", "withdrawn")


def is_disqualified(position_text: str | None, status: str | None = None) -> bool:
    """Desclassificação.

    A fonte é inconsistente: às vezes usa positionText ``D``, às vezes só
    ``status = "Disqualified"`` (ex.: Russell em Spa 2024, que aparece como
    P20 com status Disqualified). Os dois casos precisam ser tratados.
    """
    if (position_text or "").upper() == "D":
        return True
    status_text = (status or "").lower()
    return any(token in status_text for token in DSQ_STATUSES)


def is_classified(position_text: str | None, status: str | None = None) -> bool:
    """True quando o piloto recebeu posição de chegada (mesmo com +1 volta)."""
    text = (position_text or "").upper()
    if not text or text in NON_CLASSIFIED:
        return False
    return not is_disqualified(position_text, status)


# --- entidades ------------------------------------------------------------
def circuit_row(circuit: dict[str, Any]) -> dict[str, Any]:
    location = circuit.get("Location", {}) or {}
    return {
        "circuit_id": circuit.get("circuitId"),
        "name": circuit.get("circuitName"),
        "locality": location.get("locality"),
        "country": location.get("country"),
        "lat": to_float(location.get("lat")),
        "lng": to_float(location.get("long")),
        "url": circuit.get("url"),
    }


def race_row(race: dict[str, Any], has_sprint: bool, source_url: str, fetched_at: str) -> dict[str, Any]:
    return {
        "season": to_int(race.get("season")),
        "round": to_int(race.get("round")),
        "race_name": race.get("raceName"),
        "circuit_id": (race.get("Circuit") or {}).get("circuitId"),
        "date": race.get("date"),
        "time": race.get("time"),
        "url": race.get("url"),
        "has_sprint": 1 if has_sprint else 0,
        "source_url": source_url,
        "fetched_at": fetched_at,
    }


def driver_row(driver: dict[str, Any]) -> dict[str, Any]:
    given = driver.get("givenName") or ""
    family = driver.get("familyName") or ""
    return {
        "driver_id": driver.get("driverId"),
        "code": driver.get("code"),
        "permanent_number": driver.get("permanentNumber"),
        "given_name": given or None,
        "family_name": family or None,
        "full_name": f"{given} {family}".strip() or None,
        "nationality": driver.get("nationality"),
        "date_of_birth": driver.get("dateOfBirth"),
        "url": driver.get("url"),
    }


def constructor_row(constructor: dict[str, Any]) -> dict[str, Any]:
    return {
        "constructor_id": constructor.get("constructorId"),
        "name": constructor.get("name"),
        "nationality": constructor.get("nationality"),
        "url": constructor.get("url"),
    }


# --- resultados -----------------------------------------------------------
def race_result_row(
    season: int, round_: int, item: dict[str, Any], source_url: str, fetched_at: str
) -> dict[str, Any]:
    fastest = item.get("FastestLap") or {}
    average_speed = fastest.get("AverageSpeed") or {}
    result_time = item.get("Time") or {}
    return {
        "season": season,
        "round": round_,
        "driver_id": driver_id(item),
        "constructor_id": constructor_id(item),
        "number": to_text(item.get("number")),
        "grid": to_int(item.get("grid")),
        "position": to_int(item.get("position")),
        "position_text": to_text(item.get("positionText")),
        "position_order": to_int(item.get("positionOrder")),
        "points": to_float(item.get("points")),
        "laps": to_int(item.get("laps")),
        "status": to_text(item.get("status")),
        "status_id": to_int(item.get("statusId")),
        "time_millis": to_int(result_time.get("millis")),
        "time_text": to_text(result_time.get("time")),
        "fastest_lap_rank": to_int(fastest.get("rank")),
        "fastest_lap_number": to_int(fastest.get("lap")),
        "fastest_lap_time": to_text((fastest.get("Time") or {}).get("time")),
        "fastest_lap_speed": to_float(average_speed.get("speed")),
        "source_url": source_url,
        "fetched_at": fetched_at,
    }


def qualifying_row(
    season: int, round_: int, item: dict[str, Any], source_url: str, fetched_at: str
) -> dict[str, Any]:
    return {
        "season": season,
        "round": round_,
        "driver_id": driver_id(item),
        "constructor_id": constructor_id(item),
        "number": to_text(item.get("number")),
        "position": to_int(item.get("position")),
        "q1": to_text(item.get("Q1")),
        "q2": to_text(item.get("Q2")),
        "q3": to_text(item.get("Q3")),
        "source_url": source_url,
        "fetched_at": fetched_at,
    }


def sprint_result_row(
    season: int, round_: int, item: dict[str, Any], source_url: str, fetched_at: str
) -> dict[str, Any]:
    result_time = item.get("Time") or {}
    return {
        "season": season,
        "round": round_,
        "driver_id": driver_id(item),
        "constructor_id": constructor_id(item),
        "number": to_text(item.get("number")),
        "grid": to_int(item.get("grid")),
        "position": to_int(item.get("position")),
        "position_text": to_text(item.get("positionText")),
        "position_order": to_int(item.get("positionOrder")),
        "points": to_float(item.get("points")),
        "laps": to_int(item.get("laps")),
        "status": to_text(item.get("status")),
        "status_id": to_int(item.get("statusId")),
        "time_millis": to_int(result_time.get("millis")),
        "time_text": to_text(result_time.get("time")),
        "source_url": source_url,
        "fetched_at": fetched_at,
    }


# --- classificações -------------------------------------------------------
def driver_standing_row(
    season: str, round_: str, item: dict[str, Any], source_url: str, fetched_at: str
) -> dict[str, Any]:
    constructors = item.get("Constructors") or []
    return {
        "season": to_int(season),
        "round": to_int(round_),
        "driver_id": driver_id(item),
        "position": to_int(item.get("position")),
        "position_text": to_text(item.get("positionText")),
        "points": to_float(item.get("points")),
        "wins": to_int(item.get("wins")),
        "constructor_ids": ",".join(c.get("constructorId", "") for c in constructors) or None,
        "source_url": source_url,
        "fetched_at": fetched_at,
    }


def constructor_standing_row(
    season: str, round_: str, item: dict[str, Any], source_url: str, fetched_at: str
) -> dict[str, Any]:
    return {
        "season": to_int(season),
        "round": to_int(round_),
        "constructor_id": constructor_id(item),
        "position": to_int(item.get("position")),
        "position_text": to_text(item.get("positionText")),
        "points": to_float(item.get("points")),
        "wins": to_int(item.get("wins")),
        "source_url": source_url,
        "fetched_at": fetched_at,
    }


# --- utilitários de coleta ------------------------------------------------
def unique_races(races: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe(races, key=lambda r: (int(r["season"]), int(r["round"])))


def unique_drivers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe(items, key=lambda item: driver_id(item))


def unique_constructors(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe(items, key=lambda item: constructor_id(item))
