"""Encerra oficialmente uma temporada marcada como "em andamento".

O script só publica quando a Jolpica já traz:

1. o calendário completo (23 GPs e 6 sprints em 2026);
2. resultado da última etapa;
3. standings finais no último round, com os campeões que já estavam
   registrados como matemáticos em ``config.CLINCHED_CHAMPIONS``.

Nada é inferido nem inventado: se faltar qualquer pré-requisito, ele aborta
antes de tocar no banco ou no código. Se alguma etapa posterior falhar, os
arquivos originais são restaurados e nada é commitado.

Uso típico (Windows):

    .\\.venv\\Scripts\\python.exe scripts\\finalize_season.py
    .\\.venv\\Scripts\\python.exe scripts\\finalize_season.py --check-only

O modo ``--check-only`` apenas consulta a API e informa se já é seguro fechar.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from f1dc import config  # noqa: E402
from f1dc.api import JolpicaClient  # noqa: E402
from f1dc.transform import unique_races  # noqa: E402

CONFIG_PATH = ROOT / "f1dc" / "config.py"
DB_PATH = ROOT / "data" / "f1.db"
REPORT_PATH = ROOT / "data" / "validation_report.json"
LOG_PATH = ROOT / "logs" / "finalize_season.log"


def log(message: str) -> None:
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def run(command: list[str]) -> None:
    log("$ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def checkpoint_wal() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        log(f"WAL checkpoint: {result}")
    finally:
        conn.close()


def _leader(rows: list[tuple[str, str, dict[str, Any]]]) -> dict[str, Any] | None:
    candidates = [item for _, _, item in rows if str(item.get("position")) == "1"]
    return candidates[0] if len(candidates) == 1 else None


def preflight(
    client: JolpicaClient,
    season: int,
    calendar_races: int,
    calendar_sprints: int,
    expected_driver: str,
    expected_team: str,
) -> dict[str, Any]:
    """Consulta a fonte e devolve os fatos que autorizam (ou não) o fechamento."""
    problems: list[str] = []

    races = unique_races(client.races(season))
    rounds = sorted(int(r["round"]) for r in races)
    sprints = sorted(set(int(r) for r in client.sprint_rounds(season)))
    drivers = client.driver_standings(season)
    teams = client.constructor_standings(season)
    leader_driver = _leader(drivers)
    leader_team = _leader(teams)

    last_round = rounds[-1] if rounds else None
    final_results = (
        client.race_results(season, last_round) if last_round is not None else []
    )
    standings_rounds = sorted({int(round_) for _, round_, _ in [*drivers, *teams] if round_})

    if len(rounds) != calendar_races or rounds != list(range(1, calendar_races + 1)):
        problems.append(
            f"calendário da API tem {len(rounds)} etapa(s) ({rounds}), "
            f"esperado {calendar_races} (R1..R{calendar_races})"
        )
    if any(s < 1 or s > calendar_races for s in sprints):
        problems.append(f"sprints fora do calendário: {sprints}")
    if len(sprints) != calendar_sprints:
        problems.append(
            f"API traz {len(sprints)} sprint(s) ({sprints}), esperado {calendar_sprints}"
        )
    if not final_results:
        problems.append(f"sem resultado na API para R{last_round or '?'}")
    if standings_rounds != [calendar_races]:
        problems.append(
            f"standings da API são do(s) round(s) {standings_rounds or 'nenhum'}, "
            f"esperado apenas R{calendar_races}"
        )

    driver_id = (
        ((leader_driver or {}).get("Driver") or {}).get("driverId") if leader_driver else None
    )
    team_id = (
        ((leader_team or {}).get("Constructor") or {}).get("constructorId")
        if leader_team
        else None
    )
    if driver_id != expected_driver:
        problems.append(
            f"líder de pilotos na API é {driver_id or '?'}, esperado {expected_driver}"
        )
    if team_id != expected_team:
        problems.append(
            f"líder de construtores na API é {team_id or '?'}, esperado {expected_team}"
        )

    return {
        "ok": not problems,
        "problems": problems,
        "season": season,
        "rounds": rounds,
        "sprints": sprints,
        "standings_rounds": standings_rounds,
        "champion_driver": driver_id,
        "champion_constructor": team_id,
        "last_race_results": len(final_results),
    }


def _replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Trecho de config.py não encontrado uma única vez: {old!r}")
    return text.replace(old, new, 1)


def finalize_config_text(
    text: str,
    season: int,
    calendar_races: int,
    calendar_sprints: int,
    driver: str,
    constructor: str,
) -> str:
    """Transforma o config atual em um config de temporada encerrada."""
    result = text
    result = _replace_once(
        result,
        f"IN_PROGRESS_SEASONS = {{{season}}}",
        "IN_PROGRESS_SEASONS = set()",
    )
    result = _replace_once(
        result,
        f"IN_PROGRESS_CALENDAR_RACES = {{{season}: {calendar_races}}}",
        "IN_PROGRESS_CALENDAR_RACES = {}",
    )
    result = _replace_once(
        result,
        f"IN_PROGRESS_CALENDAR_SPRINTS = {{{season}: {calendar_sprints}}}",
        "IN_PROGRESS_CALENDAR_SPRINTS = {}",
    )
    result = _replace_once(
        result,
        f'CLINCHED_CHAMPIONS = {{\n    {season}: {{"driver": "{driver}", '
        f'"constructor": "{constructor}"}},\n}}',
        "CLINCHED_CHAMPIONS = {}",
    )

    # A temporada passa a fazer parte das expectativas de temporada fechada.
    result = _replace_once(
        result,
        "}\nEXPECTED_SPRINTS = {",
        f"    {season}: {calendar_races},\n}}\nEXPECTED_SPRINTS = {{",
    )
    result = _replace_once(
        result,
        "}\n\n# Conferência externa dos campeões (fontes oficiais).",
        f"    {season}: {calendar_sprints},\n}}\n\n"
        "# Conferência externa dos campeões (fontes oficiais).",
    )
    result = _replace_once(
        result,
        "}\n\n# Ajustes oficiais de pontos de construtores",
        f'    {season}: ("{driver}", "{constructor}"),\n}}\n\n'
        "# Ajustes oficiais de pontos de construtores",
    )
    return result


def restore(backups: dict[str, bytes]) -> None:
    git("reset")  # limpa o índice; não toca no working tree
    for path, content in backups.items():
        Path(path).write_bytes(content)
    log("Arquivos originais restaurados; nada foi publicado.")
    checkpoint_wal()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    season = args.season
    if season not in config.IN_PROGRESS_SEASONS:
        raise SystemExit(
            f"{season} não está marcada como em andamento; nada a encerrar."
        )
    calendar_races = config.IN_PROGRESS_CALENDAR_RACES.get(season)
    calendar_sprints = config.IN_PROGRESS_CALENDAR_SPRINTS.get(season)
    clinched = config.CLINCHED_CHAMPIONS.get(season, {})
    driver = clinched.get("driver")
    constructor = clinched.get("constructor")
    if not all([calendar_races, calendar_sprints is not None, driver, constructor]):
        raise SystemExit(
            f"Configuração insuficiente para {season}: "
            f"{calendar_races=}, {calendar_sprints=}, {clinched=}"
        )

    log(f"=== Encerramento de {season} ===")
    facts = preflight(
        JolpicaClient(), season, calendar_races, calendar_sprints, driver, constructor
    )
    for key in (
        "rounds",
        "sprints",
        "standings_rounds",
        "champion_driver",
        "champion_constructor",
        "last_race_results",
    ):
        log(f"{key}: {facts[key]}")
    if not facts["ok"]:
        for problem in facts["problems"]:
            log(f"PRÉ-REQUISITO FALTANDO: {problem}")
        log("Encerramento abortado; base e código intactos.")
        return 2
    log("Pré-requisitos conferidos na fonte primária.")
    if args.check_only:
        return 0

    if git("status", "--porcelain"):
        raise SystemExit(
            "Working tree com alterações; commite-as antes de encerrar a temporada."
        )

    checkpoint_wal()
    original_config = CONFIG_PATH.read_bytes()
    backups = {
        str(CONFIG_PATH): original_config,
        str(DB_PATH): DB_PATH.read_bytes(),
        str(REPORT_PATH): REPORT_PATH.read_bytes(),
    }
    success = False
    committed = False
    try:
        new_config = finalize_config_text(
            original_config.decode("utf-8"),
            season,
            calendar_races,
            calendar_sprints,
            driver,
            constructor,
        )
        with CONFIG_PATH.open("w", encoding="utf-8", newline="") as handle:
            handle.write(new_config)
        log("config.py atualizado: temporada passou para a lista de encerradas.")

        run([sys.executable, "-m", "f1dc.ingest", "--seasons", str(season)])
        run([sys.executable, "-m", "f1dc.validate"])
        checkpoint_wal()

        git("add", "f1dc/config.py", "data/f1.db", "data/validation_report.json")
        staged = git("diff", "--cached", "--name-only")
        if not staged:
            raise RuntimeError("Nenhuma alteração versionada após o fechamento.")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        git("commit", "-m", f"Encerra temporada {season} ({stamp})")
        committed = True
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        git("push", "origin", branch)
        success = True
        log("Publicado. O Streamlit Cloud deve redeployar automaticamente.")
        return 0
    finally:
        if not success:
            if committed:
                log(
                    "Commit local criado, mas a publicação falhou. Arquivos mantidos "
                    "para não perder trabalho: rode 'git push' ou faça rollback manual."
                )
            else:
                restore(backups)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"FALHA: {exc}")
        raise
