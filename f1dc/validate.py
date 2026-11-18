"""Validação da base importada (Fase C do documento central).

Uso:
    python -m f1dc.validate
    python -m f1dc.validate --db data/f1.db
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from . import config, db

TOLERANCE = 1e-6

IN_PROGRESS_SEASONS = set(getattr(config, "IN_PROGRESS_SEASONS", set()))
CLOSED_SEASONS = [s for s in config.SEASONS if s not in IN_PROGRESS_SEASONS]
IN_PROGRESS_CALENDAR_RACES = getattr(config, "IN_PROGRESS_CALENDAR_RACES", {})
IN_PROGRESS_CALENDAR_SPRINTS = getattr(config, "IN_PROGRESS_CALENDAR_SPRINTS", {})
CLINCHED_CHAMPIONS = getattr(config, "CLINCHED_CHAMPIONS", {})
EXCLUDED_CONSTRUCTOR_CHAMPIONSHIPS = getattr(
    config, "EXCLUDED_CONSTRUCTOR_CHAMPIONSHIPS", set()
)


def _scalar(conn, sql: str, params: tuple = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _rows(conn, sql: str, params: tuple = ()) -> list[Any]:
    return conn.execute(sql, params).fetchall()


def _check(check_id: str, title: str, ok: bool, detail: str, data: Any = None) -> dict[str, Any]:
    return {"id": check_id, "title": title, "ok": bool(ok), "detail": detail, "data": data}


def validate(db_path: str | Path = config.DB_PATH) -> dict[str, Any]:
    conn = db.connect(db_path)
    try:
        checks: list[dict[str, Any]] = []

        # 1. Temporadas e contagem de GPs ---------------------------------
        season_rows = _rows(
            conn,
            "SELECT season, races_count, champion_driver_id, champion_constructor_id "
            "FROM seasons ORDER BY season",
        )
        found = {int(r["season"]): int(r["races_count"] or 0) for r in season_rows}
        stored_champions = {
            int(r["season"]): (r["champion_driver_id"], r["champion_constructor_id"])
            for r in season_rows
        }
        missing = [s for s in config.SEASONS if s not in found]
        wrong = {
            s: (found.get(s), expected)
            for s, expected in config.EXPECTED_RACES.items()
            if s in found and found.get(s) != expected
        }
        in_progress_counts = {
            s: found.get(s, 0) for s in config.SEASONS if s in IN_PROGRESS_SEASONS
        }
        in_progress_wrong = {
            s: (in_progress_counts.get(s), calendar)
            for s, calendar in IN_PROGRESS_CALENDAR_RACES.items()
            if s in IN_PROGRESS_SEASONS
            and not (0 < in_progress_counts.get(s, 0) <= calendar)
        }
        total_races = _scalar(conn, "SELECT COUNT(*) FROM races")
        expected_total = sum(config.EXPECTED_RACES.values()) + sum(
            in_progress_counts.values()
        )
        period_label = f"{min(config.SEASONS)}-{max(config.SEASONS)}"
        in_progress_detail = "; ".join(
            f"{s}: {in_progress_counts.get(s, 0)} de "
            f"{IN_PROGRESS_CALENDAR_RACES.get(s, '?')} GPs concluídos"
            for s in in_progress_counts
        ) or "nenhuma"
        checks.append(
            _check(
                "seasons",
                f"Temporadas {period_label} importadas com a contagem de GPs esperada",
                not missing
                and not wrong
                and not in_progress_wrong
                and total_races == expected_total,
                f"{len(found)} temporadas, {total_races} GPs no total "
                f"(esperado {expected_total}). Ausentes: {missing or 'nenhuma'}. "
                f"Divergentes: {wrong or 'nenhuma'}. "
                f"Em andamento: {in_progress_detail}.",
                {
                    "found": found,
                    "total_races": total_races,
                    "in_progress": in_progress_counts,
                },
            )
        )

        # 2. GPs sem resultado de corrida --------------------------------
        sem_resultado = _rows(
            conn,
            """
            SELECT r.season, r."round", r.race_name
            FROM races r
            LEFT JOIN race_results rr
              ON rr.season = r.season AND rr."round" = r."round"
            WHERE rr.driver_id IS NULL
            ORDER BY r.season, r."round"
            """,
        )
        checks.append(
            _check(
                "races_without_results",
                "Todos os GPs possuem resultado de corrida",
                not sem_resultado,
                "Nenhum GP sem resultado."
                if not sem_resultado
                else f"{len(sem_resultado)} GP(s) sem resultado.",
                [dict(r) for r in sem_resultado],
            )
        )

        # 3. GPs sem classificação --------------------------------------
        sem_quali = _rows(
            conn,
            """
            SELECT r.season, r."round", r.race_name
            FROM races r
            LEFT JOIN qualifying_results q
              ON q.season = r.season AND q."round" = r."round"
            WHERE q.driver_id IS NULL
            ORDER BY r.season, r."round"
            """,
        )
        checks.append(
            _check(
                "races_without_qualifying",
                "Cobertura de classificação completa (qualifying) — informativo",
                True,
                "Nenhum GP sem classificação."
                if not sem_quali
                else (
                    f"{len(sem_quali)} GP(s) sem classificação completa na fonte "
                    "primária (documentado; a pole de cada GP é verificada na "
                    "checagem de poles)."
                ),
                [dict(r) for r in sem_quali],
            )
        )

        # 3b. Pilotos classificados sem resultado / sem classificação ----
        quali_sem_corrida = _rows(
            conn,
            """
            SELECT q.season, q."round", r.race_name, q.driver_id, d.full_name
            FROM qualifying_results q
            JOIN races r ON r.season = q.season AND r."round" = q."round"
            LEFT JOIN drivers d ON d.driver_id = q.driver_id
            WHERE EXISTS (
                SELECT 1 FROM race_results y
                WHERE y.season = q.season AND y."round" = q."round")
              AND NOT EXISTS (
                SELECT 1 FROM race_results x
                WHERE x.season = q.season AND x."round" = q."round"
                  AND x.driver_id = q.driver_id)
            ORDER BY q.season, q."round"
            """,
        )
        checks.append(
            _check(
                "quali_without_race_result",
                "Classificados que não constam no resultado da corrida (DNS/fonte)",
                True,
                f"{len(quali_sem_corrida)} caso(s). A fonte simplesmente não retorna "
                "o piloto no resultado; nenhuma posição é inventada.",
                [dict(r) for r in quali_sem_corrida],
            )
        )

        corrida_sem_quali = _rows(
            conn,
            """
            SELECT x.season, x."round", r.race_name, x.driver_id, d.full_name, x.status
            FROM race_results x
            JOIN races r ON r.season = x.season AND r."round" = x."round"
            LEFT JOIN drivers d ON d.driver_id = x.driver_id
            WHERE EXISTS (
                SELECT 1 FROM qualifying_results q
                WHERE q.season = x.season AND q."round" = x."round")
              AND NOT EXISTS (
                SELECT 1 FROM qualifying_results q
                WHERE q.season = x.season AND q."round" = x."round"
                  AND q.driver_id = x.driver_id)
            ORDER BY x.season, x."round"
            """,
        )
        checks.append(
            _check(
                "race_without_quali",
                "Pilotos no resultado sem linha na classificação (fonte)",
                True,
                f"{len(corrida_sem_quali)} caso(s). Ausência real na classificação "
                "da fonte, mantida como ausente.",
                [dict(r) for r in corrida_sem_quali],
            )
        )

        # 4. Contagem de linhas por GP (documenta ausências da fonte) -----
        quali_counts = _rows(
            conn,
            """
            SELECT r.season, r."round", r.race_name,
                   (SELECT COUNT(*) FROM race_results rr
                     WHERE rr.season = r.season AND rr."round" = r."round") AS results,
                   (SELECT COUNT(*) FROM qualifying_results q
                     WHERE q.season = r.season AND q."round" = r."round") AS quali
            FROM races r
            ORDER BY r.season, r."round"
            """,
        )
        divergentes = [
            dict(r)
            for r in quali_counts
            if r["quali"] and r["quali"] != r["results"]
        ]
        checks.append(
            _check(
                "qualifying_row_counts",
                "Contagem de pilotos na classificação por GP (informativo)",
                True,
                f"{len(divergentes)} GP(s) com contagem de classificação diferente "
                "da contagem de resultado. Pode ser ausência real na fonte.",
                divergentes,
            )
        )

        # 5. Sprint ------------------------------------------------------
        sprint_rounds_db = {
            (int(r["season"]), int(r["round"]))
            for r in _rows(conn, "SELECT DISTINCT season, \"round\" FROM sprint_results")
        }
        sprint_flag = {
            (int(r["season"]), int(r["round"]))
            for r in _rows(conn, "SELECT season, \"round\" FROM races WHERE has_sprint = 1")
        }
        sprint_counts = {
            season: sum(1 for (s, _) in sprint_rounds_db if s == season)
            for season in config.SEASONS
        }
        sprint_ok = sprint_rounds_db == sprint_flag
        for season in CLOSED_SEASONS:
            sprint_ok = sprint_ok and (
                sprint_counts.get(season, 0) == config.EXPECTED_SPRINTS.get(season, 0)
            )
        # Temporadas em andamento: o esperado é o que está no calendário já
        # importado; a igualdade acima garante que toda sprint marcada tem
        # resultado carregado.
        expected_sprints_label = ", ".join(
            str(config.EXPECTED_SPRINTS.get(s, 0)) for s in CLOSED_SEASONS
        )
        if IN_PROGRESS_SEASONS:
            expected_sprints_label += " + em andamento"
        checks.append(
            _check(
                "sprints",
                f"Sprints separadas e completas ({expected_sprints_label})",
                sprint_ok,
                f"Sprints importadas por temporada: {sprint_counts}.",
                {"counts": sprint_counts},
            )
        )

        # 5. Classificação final oficial presente -------------------------
        final_standings = {
            int(r["season"]): dict(r)
            for r in _rows(conn, "SELECT * FROM driver_standings WHERE position = 1")
        }
        final_constructors = {
            int(r["season"]): dict(r)
            for r in _rows(conn, "SELECT * FROM constructor_standings WHERE position = 1")
        }
        champions = {
            season: (
                (final_standings.get(season) or {}).get("driver_id"),
                (final_constructors.get(season) or {}).get("constructor_id"),
            )
            for season in config.SEASONS
        }
        champion_ok = all(
            champions.get(s) == config.EXPECTED_CHAMPIONS.get(s)
            for s in CLOSED_SEASONS
        )
        # Em temporada em andamento não existe campeão: os campos da tabela
        # seasons precisam ficar vazios, mesmo que haja um líder na fonte.
        champion_ok = champion_ok and all(
            stored_champions.get(s, (None, None)) == (None, None)
            for s in IN_PROGRESS_SEASONS
        )
        champion_detail = [
            f"{s}: {d or '?'} / {c or '?'}"
            + (" (DIVERGE)" if (d, c) != config.EXPECTED_CHAMPIONS.get(s) else "")
            for s in CLOSED_SEASONS
            for d, c in [champions.get(s, (None, None))]
        ]
        for s in sorted(IN_PROGRESS_SEASONS):
            info = CLINCHED_CHAMPIONS.get(s, {})
            clinched_parts = []
            if info.get("driver"):
                clinched_parts.append(f"título matemático de pilotos: {info['driver']}")
            if info.get("constructor"):
                clinched_parts.append(
                    f"título matemático de construtores: {info['constructor']}"
                )
            status = (
                "; ".join(clinched_parts) + "; temporada em andamento"
                if clinched_parts
                else "sem campeão definido"
            )
            champion_detail.append(
                f"{s}: em andamento (líder atual: "
                f"{(final_standings.get(s) or {}).get('driver_id') or '?'} / "
                f"{(final_constructors.get(s) or {}).get('constructor_id') or '?'}; "
                f"{status})"
            )
        checks.append(
            _check(
                "champions",
                "Campeões de pilotos e construtores conferem com a fonte externa "
                "(temporadas encerradas)",
                champion_ok,
                "; ".join(champion_detail),
                {
                    "found": champions,
                    "expected": config.EXPECTED_CHAMPIONS,
                    "in_progress": sorted(IN_PROGRESS_SEASONS),
                },
            )
        )

        # 5b. Títulos matemáticos em temporadas em andamento --------------
        clinched_ok = True
        clinched_detail: list[str] = []
        for season, info in sorted(CLINCHED_CHAMPIONS.items()):
            calendar = IN_PROGRESS_CALENDAR_RACES.get(season)
            completed = found.get(season, 0)
            remaining_races = max((calendar or completed) - completed, 0)
            imported_sprints = sprint_counts.get(season, 0)
            calendar_sprints = IN_PROGRESS_CALENDAR_SPRINTS.get(
                season, imported_sprints
            )
            remaining_sprints = max(calendar_sprints - imported_sprints, 0)
            max_driver_points = remaining_races * 25 + remaining_sprints * 8
            max_team_points = remaining_races * 43 + remaining_sprints * 15

            driver_leader = final_standings.get(season) or {}
            team_leader = final_constructors.get(season) or {}
            second_driver = _rows(
                conn,
                "SELECT driver_id, points FROM driver_standings "
                "WHERE season = ? AND position = 2",
                (season,),
            )
            second_team = _rows(
                conn,
                "SELECT constructor_id, points FROM constructor_standings "
                "WHERE season = ? AND position = 2",
                (season,),
            )
            driver_gap = (
                float(driver_leader.get("points") or 0)
                - float(second_driver[0]["points"] or 0)
                if second_driver
                else None
            )
            team_gap = (
                float(team_leader.get("points") or 0)
                - float(second_team[0]["points"] or 0)
                if second_team
                else None
            )

            expected_driver = info.get("driver")
            expected_team = info.get("constructor")
            season_ok = (
                season in IN_PROGRESS_SEASONS
                and bool(expected_driver)
                and driver_leader.get("driver_id") == expected_driver
                and driver_gap is not None
                and driver_gap > max_driver_points
            )
            if expected_team:
                season_ok = (
                    season_ok
                    and team_leader.get("constructor_id") == expected_team
                    and team_gap is not None
                    and team_gap > max_team_points
                )
            clinched_ok = clinched_ok and season_ok

            detail = (
                f"{season}: pilotos {expected_driver or '—'} com "
                f"{driver_gap if driver_gap is not None else '?'} ponto(s) de "
                f"vantagem (máximo restante {max_driver_points})"
            )
            if expected_team:
                detail += (
                    f"; construtores {expected_team} com "
                    f"{team_gap if team_gap is not None else '?'} ponto(s) de "
                    f"vantagem (máximo restante {max_team_points})"
                )
            detail += (
                f"; {remaining_races} corrida(s) e {remaining_sprints} sprint(s) "
                "restantes; temporada em andamento"
            )
            clinched_detail.append(detail)

        checks.append(
            _check(
                "clinched_champions",
                "Títulos matemáticos em temporadas em andamento conferidos",
                clinched_ok,
                "; ".join(clinched_detail)
                or "Nenhum título matemático configurado.",
                {
                    "configured": CLINCHED_CHAMPIONS,
                    "in_progress": sorted(IN_PROGRESS_SEASONS),
                },
            )
        )

        # 6. Reconciliação de pontos (corrida + sprint x standings) -------
        computed = {
            (int(r["season"]), r["driver_id"]): float(r["pts"] or 0)
            for r in _rows(
                conn,
                """
                SELECT season, driver_id, SUM(COALESCE(points, 0)) AS pts
                FROM (
                    SELECT season, driver_id, points FROM race_results
                    UNION ALL
                    SELECT season, driver_id, points FROM sprint_results
                )
                GROUP BY season, driver_id
                """,
            )
        }
        official = {
            (int(r["season"]), r["driver_id"]): float(r["points"] or 0)
            for r in _rows(conn, "SELECT season, driver_id, points FROM driver_standings")
        }
        driver_mismatches = []
        for key, official_points in official.items():
            calculated = computed.get(key, 0.0)
            if abs(calculated - official_points) > TOLERANCE:
                driver_mismatches.append(
                    {
                        "season": key[0],
                        "driver_id": key[1],
                        "official": official_points,
                        "calculated": calculated,
                        "diff": round(calculated - official_points, 4),
                    }
                )
        checks.append(
            _check(
                "driver_points_reconciliation",
                "Pontos de corrida + sprint batem com a classificação oficial de pilotos",
                not driver_mismatches,
                "Todos os pilotos conferem."
                if not driver_mismatches
                else f"{len(driver_mismatches)} divergência(s) de pontos.",
                driver_mismatches[:50],
            )
        )

        computed_teams = {
            (int(r["season"]), r["constructor_id"]): float(r["pts"] or 0)
            for r in _rows(
                conn,
                """
                SELECT season, constructor_id, SUM(COALESCE(points, 0)) AS pts
                FROM (
                    SELECT season, constructor_id, points FROM race_results
                    UNION ALL
                    SELECT season, constructor_id, points FROM sprint_results
                )
                GROUP BY season, constructor_id
                """,
            )
        }
        official_teams = {
            (int(r["season"]), r["constructor_id"]): float(r["points"] or 0)
            for r in _rows(
                conn, "SELECT season, constructor_id, points FROM constructor_standings"
            )
        }
        team_mismatches = []
        team_adjustments = getattr(config, "CONSTRUCTOR_POINT_ADJUSTMENTS", {})
        for key, official_points in official_teams.items():
            if key in EXCLUDED_CONSTRUCTOR_CHAMPIONSHIPS:
                # Equipe excluída do campeonato pela fonte oficial: a soma dos
                # resultados não é reconciliada com o standings (posição nula).
                continue
            adjustment = team_adjustments.get(key, 0.0)
            calculated = computed_teams.get(key, 0.0) + adjustment
            if abs(calculated - official_points) > TOLERANCE:
                team_mismatches.append(
                    {
                        "season": key[0],
                        "constructor_id": key[1],
                        "official": official_points,
                        "calculated": calculated,
                        "diff": round(calculated - official_points, 4),
                    }
                )
        checks.append(
            _check(
                "constructor_points_reconciliation",
                "Pontos de corrida + sprint batem com a classificação oficial de construtores",
                not team_mismatches,
                (
                    "Todos os construtores conferem."
                    if not team_mismatches
                    else f"{len(team_mismatches)} divergência(s) de pontos."
                )
                + (
                    " Ajustes oficiais aplicados: "
                    + ", ".join(
                        f"{s} {c} ({a:+.0f})"
                        for (s, c), a in team_adjustments.items()
                        if (s, c) in official_teams
                    )
                    + "."
                    if team_adjustments
                    else ""
                )
                + (
                    " Equipes excluídas do campeonato (não reconciliadas): "
                    + ", ".join(
                        f"{s} {c}"
                        for (s, c) in sorted(EXCLUDED_CONSTRUCTOR_CHAMPIONSHIPS)
                        if (s, c) in official_teams
                    )
                    + "."
                    if EXCLUDED_CONSTRUCTOR_CHAMPIONSHIPS
                    else ""
                ),
                team_mismatches[:50],
            )
        )

        # 7. Volta mais rápida (fonte primária + complementar) ----------
        fl_por_temporada = {
            int(r["season"]): int(r["n"])
            for r in _rows(
                conn,
                """
                SELECT r.season, COUNT(*) AS n
                FROM races r
                WHERE EXISTS (
                        SELECT 1 FROM fastest_laps f
                        WHERE f.season = r.season AND f."round" = r."round"
                      )
                   OR EXISTS (
                        SELECT 1 FROM session_awards a
                        WHERE a.season = r.season AND a."round" = r."round"
                          AND a.award = 'fastest_lap'
                      )
                GROUP BY r.season ORDER BY r.season
                """,
            )
        }
        sem_fl = _rows(
            conn,
            """
            SELECT r.season, r."round", r.race_name
            FROM races r
            WHERE NOT EXISTS (
                    SELECT 1 FROM fastest_laps f
                    WHERE f.season = r.season AND f."round" = r."round"
                  )
              AND NOT EXISTS (
                    SELECT 1 FROM session_awards a
                    WHERE a.season = r.season AND a."round" = r."round"
                      AND a.award = 'fastest_lap'
                  )
            ORDER BY r.season, r."round"
            """,
        )
        documented_fl = getattr(config, "DOCUMENTED_FASTEST_LAP_ABSENCES", {})
        sem_fl_undocumented = [
            row
            for row in sem_fl
            if (int(row["season"]), int(row["round"])) not in documented_fl
        ]
        documented_missing = [
            dict(row)
            for row in sem_fl
            if (int(row["season"]), int(row["round"])) in documented_fl
        ]
        if sem_fl_undocumented:
            fl_detail = (
                f"{len(sem_fl_undocumented)} GP(s) sem volta mais rápida em "
                "nenhuma fonte."
            )
        elif documented_missing:
            fl_detail = (
                "Todos os GPs possuem volta mais rápida, exceto "
                f"{len(documented_missing)} ausência(s) real(is) documentada(s) "
                "na fonte."
            )
        else:
            fl_detail = "Todos os GPs possuem volta mais rápida."
        checks.append(
            _check(
                "fastest_laps",
                "Cada GP possui volta mais rápida (fonte primária ou complementar)",
                not sem_fl_undocumented,
                fl_detail,
                {
                    "por_temporada": fl_por_temporada,
                    "sem_volta_rapida": [
                        dict(row) for row in sem_fl_undocumented
                    ],
                    "ausencias_documentadas": documented_missing,
                },
            )
        )

        # 8. Pole position (P1 do qualifying ou fonte complementar) -----
        sem_pole = _rows(
            conn,
            """
            SELECT r.season, r."round", r.race_name
            FROM races r
            WHERE NOT EXISTS (
                    SELECT 1 FROM qualifying_results q
                    WHERE q.season = r.season AND q."round" = r."round"
                      AND q.position = 1
                  )
              AND NOT EXISTS (
                    SELECT 1 FROM session_awards a
                    WHERE a.season = r.season AND a."round" = r."round"
                      AND a.award = 'pole'
                  )
            ORDER BY r.season, r."round"
            """,
        )
        poles = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM races r
            WHERE EXISTS (
                    SELECT 1 FROM qualifying_results q
                    WHERE q.season = r.season AND q."round" = r."round"
                      AND q.position = 1
                  )
               OR EXISTS (
                    SELECT 1 FROM session_awards a
                    WHERE a.season = r.season AND a."round" = r."round"
                      AND a.award = 'pole'
                  )
            """,
        )
        total_races = _scalar(conn, "SELECT COUNT(*) FROM races")
        checks.append(
            _check(
                "poles",
                "Cada GP possui pole position (fonte primária ou complementar)",
                not sem_pole,
                "Todos os GPs possuem pole identificada."
                if not sem_pole
                else f"{len(sem_pole)} GP(s) sem pole em nenhuma fonte.",
                {
                    "poles": poles,
                    "races": total_races,
                    "sem_pole": [dict(r) for r in sem_pole],
                },
            )
        )

        # 8b. Conflitos entre fonte complementar e primária ------------
        conflitos_pole = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM session_awards a
            WHERE a.award = 'pole' AND EXISTS (
                SELECT 1 FROM qualifying_results q
                WHERE q.season = a.season AND q."round" = a."round"
                  AND q.position = 1 AND q.driver_id <> a.driver_id
            )
            """,
        )
        conflitos_fl = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM session_awards a
            WHERE a.award = 'fastest_lap' AND EXISTS (
                SELECT 1 FROM fastest_laps f
                WHERE f.season = a.season AND f."round" = a."round"
                  AND f.driver_id <> a.driver_id
            )
            """,
        )
        complementares = _scalar(conn, "SELECT COUNT(*) FROM session_awards")
        conflitos = int(conflitos_pole or 0) + int(conflitos_fl or 0)
        checks.append(
            _check(
                "complementary_conflicts",
                "Dados complementares coincidem com a fonte primária",
                conflitos == 0,
                f"{conflitos} conflito(s) em {complementares} registro(s) complementares.",
                {
                    "pole_conflicts": int(conflitos_pole or 0),
                    "fastest_lap_conflicts": int(conflitos_fl or 0),
                    "complementary_rows": int(complementares or 0),
                },
            )
        )

        # 8c. Rastreabilidade dos dados complementares ----------------
        sem_fonte = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM session_awards a
            WHERE a.source_url IS NULL OR a.fetched_at IS NULL
               OR NOT EXISTS (
                    SELECT 1 FROM races r
                    WHERE r.season = a.season AND r."round" = a."round"
                  )
            """,
        )
        checks.append(
            _check(
                "complementary_provenance",
                "Prêmios complementares possuem fonte, data e GP válido",
                sem_fonte == 0,
                "Todos os registros complementares têm fonte e data."
                if sem_fonte == 0
                else f"{sem_fonte} registro(s) complementar(es) sem fonte/data/GP.",
                {"sem_fonte": sem_fonte},
            )
        )

        # 9. Grid efetivo preservado ------------------------------------
        sem_grid = _scalar(
            conn, "SELECT COUNT(*) FROM race_results WHERE grid IS NULL"
        )
        checks.append(
            _check(
                "grid",
                "Grid efetivo de largada preservado em todos os resultados",
                sem_grid == 0,
                "Grid presente em todas as linhas."
                if sem_grid == 0
                else f"{sem_grid} linha(s) sem grid.",
                {"sem_grid": sem_grid},
            )
        )

        # 10. Integridade de status (DNS/DNF/DSQ) -----------------------
        invalid_positions = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM race_results
            WHERE position IS NULL AND position_text IS NULL
            """,
        )
        checks.append(
            _check(
                "status_integrity",
                "Status ausente não foi convertido em posição inventada",
                invalid_positions == 0,
                "Todas as linhas têm posição ou status textual."
                if invalid_positions == 0
                else f"{invalid_positions} linha(s) sem posição e sem status textual.",
                {"invalid": invalid_positions},
            )
        )

        # 11. Duplicatas ------------------------------------------------
        dup_race = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM (
                SELECT season, "round", driver_id, COUNT(*) c
                FROM race_results GROUP BY 1, 2, 3 HAVING c > 1
            )
            """,
        )
        checks.append(
            _check(
                "duplicates",
                "Sem registros duplicados",
                dup_race == 0,
                "Nenhuma duplicata." if dup_race == 0 else f"{dup_race} duplicata(s).",
                {"duplicates": dup_race},
            )
        )

        # 12. Amostra: vencedores por temporada -------------------------
        winners = {
            int(r["season"]): int(r["n"])
            for r in _rows(
                conn,
                """
                SELECT season, COUNT(*) n FROM race_results
                WHERE position = 1
                  AND (position_text IS NULL OR position_text != 'D')
                  AND (status IS NULL OR status NOT LIKE '%Disqualified%')
                GROUP BY season ORDER BY season
                """,
            )
        }
        winners_ok = all(
            winners.get(s, 0) == config.EXPECTED_RACES.get(s, 0)
            for s in CLOSED_SEASONS
        )
        # Em temporada em andamento, cada etapa importada precisa ter exatamente
        # um vencedor (a contagem esperada é a de GPs concluídos).
        winners_ok = winners_ok and all(
            winners.get(s, 0) == found.get(s, 0) for s in IN_PROGRESS_SEASONS
        )
        checks.append(
            _check(
                "winners_count",
                "Um vencedor por GP (contagem de vitórias por temporada)",
                winners_ok,
                f"Vencedores por temporada: {winners}. "
                f"Esperado nas encerradas: {config.EXPECTED_RACES}; "
                f"em andamento: {in_progress_counts}.",
                winners,
            )
        )

        # 13. Notas de ausências verificadas na fonte -------------------
        notes: list[dict[str, Any]] = []
        for s in sorted(IN_PROGRESS_SEASONS):
            count = in_progress_counts.get(s, 0)
            calendar = IN_PROGRESS_CALENDAR_RACES.get(s)
            leader_driver = (final_standings.get(s) or {}).get("driver_id")
            leader_constructor = (final_constructors.get(s) or {}).get("constructor_id")
            leader_name = (
                _scalar(
                    conn,
                    "SELECT full_name FROM drivers WHERE driver_id = ?",
                    (leader_driver,),
                )
                if leader_driver
                else None
            )
            leader_team = (
                _scalar(
                    conn,
                    "SELECT name FROM constructors WHERE constructor_id = ?",
                    (leader_constructor,),
                )
                if leader_constructor
                else None
            )
            info = CLINCHED_CHAMPIONS.get(s, {})
            clinched_parts = []
            if info.get("driver"):
                clinched_parts.append(
                    "O título de pilotos já está garantido matematicamente por "
                    f"{leader_name or leader_driver or info['driver']}."
                )
            if info.get("constructor"):
                clinched_parts.append(
                    "O título de construtores já está garantido matematicamente por "
                    f"{leader_team or leader_constructor or info['constructor']}."
                )
            if clinched_parts:
                closing = (
                    " ".join(clinched_parts)
                    + " A temporada continua em andamento; a classificação exibida "
                    "é a posição atual, não a final."
                )
            else:
                closing = (
                    "Nenhum campeão é declarado antes do encerramento da temporada."
                )
            notes.append(
                {
                    "season": s,
                    "round": None,
                    "race": f"Temporada {s} em andamento",
                    "note": (
                        f"{count} de {calendar or '?'} GPs concluídos; apenas etapas "
                        "com resultado na fonte entram no banco. A classificação atual "
                        f"(não final) é liderada por {leader_name or leader_driver or '—'}"
                        f" / {leader_team or leader_constructor or '—'}. {closing}"
                    ),
                }
            )
        for (season, constructor_id), adjustment in getattr(
            config, "CONSTRUCTOR_POINT_ADJUSTMENTS", {}
        ).items():
            if (season, constructor_id) not in official_teams:
                continue
            constructor_name = _scalar(
                conn,
                "SELECT name FROM constructors WHERE constructor_id = ?",
                (constructor_id,),
            )
            notes.append(
                {
                    "season": season,
                    "round": None,
                    "race": constructor_name or constructor_id,
                    "note": (
                        f"Ajuste oficial de {adjustment:+.0f} ponto(s) no campeonato "
                        "de construtores não aparece nos resultados individuais; o "
                        "valor oficial dos standings é mantido."
                    ),
                }
            )
        for (season_, round_), note_text in sorted(
            getattr(config, "DOCUMENTED_FASTEST_LAP_ABSENCES", {}).items()
        ):
            has_fastest = _scalar(
                conn,
                """
                SELECT COUNT(*) FROM races r
                WHERE r.season = ? AND r."round" = ?
                  AND (
                    EXISTS (
                        SELECT 1 FROM fastest_laps f
                        WHERE f.season = r.season AND f."round" = r."round"
                    )
                    OR EXISTS (
                        SELECT 1 FROM session_awards a
                        WHERE a.season = r.season AND a."round" = r."round"
                          AND a.award = 'fastest_lap'
                    )
                  )
                """,
                (season_, round_),
            )
            if not has_fastest:
                race_name = _scalar(
                    conn,
                    'SELECT race_name FROM races WHERE season = ? AND "round" = ?',
                    (season_, round_),
                )
                notes.append(
                    {
                        "season": season_,
                        "round": round_,
                        "race": race_name or f"R{round_}",
                        "note": note_text,
                    }
                )
        monaco_quali = _scalar(
            conn,
            'SELECT COUNT(*) FROM qualifying_results WHERE season = 2021 AND "round" = 5',
        )
        if monaco_quali == 19:
            notes.append(
                {
                    "season": 2021,
                    "round": 5,
                    "race": "Monaco Grand Prix",
                    "note": (
                        "Mick Schumacher não participou da classificação (acidente no "
                        "treino livre) e largou do pit lane. 19 pilotos na classificação "
                        "é o dado correto da fonte."
                    ),
                }
            )

        for row in quali_sem_corrida:
            notes.append(
                {
                    "season": int(row["season"]),
                    "round": int(row["round"]),
                    "race": row["race_name"],
                    "note": (
                        f"{row['full_name'] or row['driver_id']} fez a classificação "
                        "mas não consta no resultado da corrida (DNS ou ausência na "
                        "fonte). Nenhuma posição foi inventada."
                    ),
                }
            )
        for row in corrida_sem_quali:
            if (int(row["season"]), int(row["round"])) in {
                (n["season"], n["round"]) for n in notes
            }:
                continue  # já documentado acima com mais contexto
            notes.append(
                {
                    "season": int(row["season"]),
                    "round": int(row["round"]),
                    "race": row["race_name"],
                    "note": (
                        f"{row['full_name'] or row['driver_id']} consta no resultado "
                        f"(status: {row['status']}) mas não na classificação da fonte."
                    ),
                }
            )

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "db_path": str(db_path),
            "ok": all(c["ok"] for c in checks),
            "checks": checks,
            "notes": notes,
        }
        return report
    finally:
        conn.close()


def save_report(report: dict[str, Any], path: str | Path = config.REPORT_PATH) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def print_report(report: dict[str, Any]) -> None:
    print(f"Relatório gerado em {report['generated_at']}")
    print(f"Base: {report['db_path']}\n")
    for check in report["checks"]:
        mark = "OK  " if check["ok"] else "FALHA"
        print(f"[{mark}] {check['title']}")
        print(f"        {check['detail']}")
    if report.get("notes"):
        print("\nAusências verificadas na fonte:")
        for note in report["notes"]:
            where = f"R{note['round']} " if note.get("round") else ""
            print(f"  - {note['season']} {where}({note['race']}): {note['note']}")
    print("\nResultado geral:", "APROVADO" if report["ok"] else "COM PENDÊNCIAS")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida a base local da F1.")
    parser.add_argument("--db", default=str(config.DB_PATH))
    parser.add_argument("--report", default=str(config.REPORT_PATH))
    args = parser.parse_args(argv)

    report = validate(args.db)
    print_report(report)
    save_report(report, args.report)
    print(f"\nRelatório salvo em {args.report}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
