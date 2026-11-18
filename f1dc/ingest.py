"""Importação das temporadas para o SQLite.

Uso:
    python -m f1dc.ingest
    python -m f1dc.ingest --seasons 2024,2025
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence

from . import config, db, transform
from .api import ApiError, JolpicaClient

log = logging.getLogger(__name__)

ProgressFn = Callable[[float, str], None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _noop(fraction: float, message: str) -> None:
    return None


def import_seasons(
    seasons: Sequence[int] = config.SEASONS,
    db_path: str = str(config.DB_PATH),
    client: JolpicaClient | None = None,
    progress: ProgressFn | None = None,
    log_fn: Callable[[str], None] = log.info,
) -> dict[str, Any]:
    """Importa as temporadas informadas de forma idempotente.

    Cada temporada é reescrita por completo dentro de uma transação, então rodar
    de novo atualiza os dados sem duplicar registros.
    """
    seasons = tuple(int(s) for s in seasons)
    client = client or JolpicaClient()
    progress = progress or _noop
    started_at = _now()

    conn = db.connect(db_path)
    db.init_db(conn)
    run_id = db.insert_run(conn, started_at, seasons)
    conn.commit()

    errors: list[str] = []
    summary: dict[int, dict[str, Any]] = {}

    try:
        for index, season in enumerate(seasons):
            base = index / len(seasons)
            span = 1 / len(seasons)

            progress(base, f"{season}: buscando calendário...")
            try:
                races = transform.unique_races(client.races(season))
                sprint_rounds = set(client.sprint_rounds(season))
            except ApiError as exc:
                errors.append(f"{season}: calendário/sprint falhou: {exc}")
                log_fn(f"[{season}] ERRO no calendário: {exc}")
                continue

            if not races:
                errors.append(f"{season}: calendário vazio")
                continue

            log_fn(
                f"[{season}] {len(races)} GPs no calendário, "
                f"{len(sprint_rounds)} com sprint"
            )
            season_error_count = len(errors)

            drivers: list[dict[str, Any]] = []
            constructors: list[dict[str, Any]] = []
            circuits: list[dict[str, Any]] = []
            race_rows: list[dict[str, Any]] = []
            result_rows: list[dict[str, Any]] = []
            qualifying_rows: list[dict[str, Any]] = []
            sprint_rows: list[dict[str, Any]] = []
            results_races = 0
            qualifying_races = 0
            sprint_races = 0

            in_progress = season in config.IN_PROGRESS_SEASONS

            for position, race in enumerate(races, start=1):
                round_ = int(race["round"])
                fraction = base + span * (position / len(races)) * 0.85
                progress(fraction, f"{season}: GP {round_}/{len(races)} - {race.get('raceName', '')}")

                try:
                    results = client.race_results(season, round_)
                except ApiError as exc:
                    errors.append(f"{season} R{round_}: resultados falharam: {exc}")
                    results = []

                # Em temporada em andamento, etapas futuras ainda não têm
                # resultado. Elas não entram no banco: só as concluídas.
                if in_progress and not results:
                    log_fn(
                        f"[{season}] R{round_}: sem resultado na fonte; "
                        "etapa ainda não realizada, ignorada."
                    )
                    continue

                if race.get("Circuit"):
                    circuits.append(transform.circuit_row(race["Circuit"]))
                race_rows.append(
                    transform.race_row(
                        race,
                        has_sprint=round_ in sprint_rounds,
                        source_url=f"{config.BASE_URL}/{season}/races.json",
                        fetched_at=started_at,
                    )
                )

                if results:
                    results_races += 1
                for item in results:
                    if item.get("Driver"):
                        drivers.append(transform.driver_row(item["Driver"]))
                    if item.get("Constructor"):
                        constructors.append(transform.constructor_row(item["Constructor"]))
                    result_rows.append(
                        transform.race_result_row(
                            season,
                            round_,
                            item,
                            source_url=f"{config.BASE_URL}/{season}/{round_}/results.json",
                            fetched_at=started_at,
                        )
                    )

                try:
                    quali = client.qualifying(season, round_)
                except ApiError as exc:
                    errors.append(f"{season} R{round_}: classificação falhou: {exc}")
                    quali = []
                if quali:
                    qualifying_races += 1
                for item in quali:
                    if item.get("Driver"):
                        drivers.append(transform.driver_row(item["Driver"]))
                    if item.get("Constructor"):
                        constructors.append(transform.constructor_row(item["Constructor"]))
                    qualifying_rows.append(
                        transform.qualifying_row(
                            season,
                            round_,
                            item,
                            source_url=f"{config.BASE_URL}/{season}/{round_}/qualifying.json",
                            fetched_at=started_at,
                        )
                    )

                if round_ in sprint_rounds:
                    try:
                        sprint = client.sprint_results(season, round_)
                    except ApiError as exc:
                        errors.append(f"{season} R{round_}: sprint falhou: {exc}")
                        sprint = []
                    if sprint:
                        sprint_races += 1
                    for item in sprint:
                        if item.get("Driver"):
                            drivers.append(transform.driver_row(item["Driver"]))
                        if item.get("Constructor"):
                            constructors.append(transform.constructor_row(item["Constructor"]))
                        sprint_rows.append(
                            transform.sprint_result_row(
                                season,
                                round_,
                                item,
                                source_url=f"{config.BASE_URL}/{season}/{round_}/sprint.json",
                                fetched_at=started_at,
                            )
                        )

            progress(base + span * 0.88, f"{season}: buscando classificação oficial...")
            driver_standings: list[dict[str, Any]] = []
            constructor_standings: list[dict[str, Any]] = []
            try:
                for s, r, item in client.driver_standings(season):
                    if item.get("Driver"):
                        drivers.append(transform.driver_row(item["Driver"]))
                    for c in item.get("Constructors") or []:
                        constructors.append(transform.constructor_row(c))
                    driver_standings.append(
                        transform.driver_standing_row(
                            s,
                            r,
                            item,
                            source_url=f"{config.BASE_URL}/{season}/driverStandings.json",
                            fetched_at=started_at,
                        )
                    )
                for s, r, item in client.constructor_standings(season):
                    if item.get("Constructor"):
                        constructors.append(transform.constructor_row(item["Constructor"]))
                    constructor_standings.append(
                        transform.constructor_standing_row(
                            s,
                            r,
                            item,
                            source_url=f"{config.BASE_URL}/{season}/constructorStandings.json",
                            fetched_at=started_at,
                        )
                    )
            except ApiError as exc:
                errors.append(f"{season}: standings falharam: {exc}")

            if in_progress:
                # A classificação atual tem um líder, mas não um campeão.
                champion_driver = None
                champion_constructor = None
            else:
                champion_driver = next(
                    (r["driver_id"] for r in driver_standings if r["position"] == 1), None
                )
                champion_constructor = next(
                    (r["constructor_id"] for r in constructor_standings if r["position"] == 1),
                    None,
                )

            # Se uma temporada em andamento teve erro de rede, não reescreve a
            # temporada: é melhor manter os dados já importados do que perder
            # etapas concluídas por causa de uma falha passageira.
            if in_progress and len(errors) > season_error_count:
                log_fn(
                    f"[{season}] erros durante a importação; temporada em "
                    "andamento não foi reescrita para preservar os dados."
                )
                continue

            # --- gravação transacional -----------------------------------
            with conn:
                db.delete_season(conn, season)
                db.upsert_rows(conn, "circuits", _dedupe_dicts(circuits, "circuit_id"))
                db.upsert_rows(conn, "drivers", _dedupe_dicts(drivers, "driver_id"))
                db.upsert_rows(
                    conn, "constructors", _dedupe_dicts(constructors, "constructor_id")
                )
                db.upsert_rows(conn, "races", race_rows)
                db.upsert_rows(conn, "race_results", result_rows)
                db.upsert_rows(conn, "qualifying_results", qualifying_rows)
                db.upsert_rows(conn, "sprint_results", sprint_rows)
                db.upsert_rows(conn, "driver_standings", driver_standings)
                db.upsert_rows(conn, "constructor_standings", constructor_standings)
                db.upsert_rows(
                    conn,
                    "seasons",
                    [
                        {
                            "season": season,
                            "races_count": len(race_rows),
                            "sprint_races": sprint_races,
                            "results_races": results_races,
                            "qualifying_races": qualifying_races,
                            "champion_driver_id": champion_driver,
                            "champion_constructor_id": champion_constructor,
                            "imported_at": started_at,
                            "source_url": f"{config.BASE_URL}/{season}/races.json",
                        }
                    ],
                )

            summary[season] = {
                "races": len(race_rows),
                "results_races": results_races,
                "qualifying_races": qualifying_races,
                "sprint_races": sprint_races,
                "champion_driver": champion_driver,
                "champion_constructor": champion_constructor,
                "in_progress": in_progress,
            }
            log_fn(
                f"[{season}] gravado: {len(race_rows)} GPs, "
                f"{len(result_rows)} resultados, {len(qualifying_rows)} classificações, "
                f"{len(sprint_rows)} linhas de sprint"
                + (" (temporada em andamento)" if in_progress else "")
            )

        finished_at = _now()
        status = "ok" if not errors else "incomplete"
        db.finish_run(conn, run_id, finished_at, status, client.request_count, errors)
        conn.commit()
        progress(1.0, "Importação concluída")

        return {
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "requests": client.request_count,
            "seasons": summary,
            "errors": errors,
        }
    finally:
        conn.close()


def _dedupe_dicts(rows: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        value = row.get(key)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(row)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Importa temporadas da Jolpica F1 API.")
    parser.add_argument(
        "--seasons",
        default=",".join(str(s) for s in config.SEASONS),
        help="lista separada por vírgula (padrão: todas as temporadas configuradas)",
    )
    parser.add_argument("--db", default=str(config.DB_PATH), help="caminho do SQLite")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    seasons = [int(s.strip()) for s in args.seasons.split(",") if s.strip()]

    def show_progress(fraction: float, message: str) -> None:
        print(f"[{fraction * 100:5.1f}%] {message}", flush=True)

    result = import_seasons(seasons=seasons, db_path=args.db, progress=show_progress)
    print("\n=== RESUMO ===")
    for season, info in result["seasons"].items():
        mode = " (em andamento)" if info.get("in_progress") else ""
        champion = info["champion_driver"] or "—"
        constructor = info["champion_constructor"] or "—"
        print(
            f"{season}: {info['races']} GPs{mode} | {info['results_races']} com resultado | "
            f"{info['qualifying_races']} com classificação | {info['sprint_races']} sprints | "
            f"campeão: {champion} / {constructor}"
        )
    print(f"Requisições HTTP: {result['requests']}")
    print(f"Status: {result['status']}")
    if result["errors"]:
        print("Erros:")
        for error in result["errors"]:
            print(f"  - {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
