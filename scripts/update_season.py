"""Atualiza uma temporada em andamento e publica a mudança no GitHub.

Fluxo (idempotente):

1. consulta a Jolpica até o GP esperado ter resultado;
2. reimporta apenas a temporada informada;
3. valida a base inteira;
4. faz ``wal_checkpoint(TRUNCATE)``;
5. commita e faz push somente se algo mudou.

Uso típico (Windows):

    .\\.venv\\Scripts\\python.exe scripts\\update_season.py --round 21

O argumento ``--round`` é o número do GP que se espera que tenha sido
disputado. O script espera (até --timeout-minutes) o resultado aparecer na
API, em vez de assumir um horário fixo de término. Se ``--round`` for
omitido, apenas reimporta o que já estiver disponível.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from f1dc import config, validate  # noqa: E402
from f1dc.api import JolpicaClient  # noqa: E402
from f1dc.ingest import import_seasons  # noqa: E402

LOG_PATH = ROOT / "logs" / "update_season.log"
MAX_ATTEMPTS = 24
RETRY_WAIT_SECONDS = 15 * 60


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


def api_has_round(season: int, round_number: int) -> bool:
    rows = JolpicaClient().race_results(season, round_number)
    return bool(rows)


def wait_for_round(season: int, round_number: int, timeout_minutes: int) -> None:
    if round_number > 1 and not api_has_round(season, round_number - 1):
        raise RuntimeError(
            f"GP {round_number - 1} de {season} ainda sem resultado na API; "
            f"não vou pular etapas."
        )
    deadline = time.monotonic() + timeout_minutes * 60
    attempt = 0
    while True:
        attempt += 1
        try:
            if api_has_round(season, round_number):
                log(f"Resultado do GP {round_number} de {season} disponível na API.")
                return
        except Exception as exc:  # retry robusto: falha de rede não é corrida ausente
            log(f"Consulta à API falhou (tentativa {attempt}): {exc}")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"GP {round_number} de {season} não apareceu na Jolpica no prazo. "
                "Nada foi publicado."
            )
        wait = min(RETRY_WAIT_SECONDS, remaining)
        log(
            f"GP {round_number} ainda sem resultado; tentando de novo em "
            f"{wait / 60:.0f} minuto(s)."
        )
        time.sleep(wait)


def race_count(season: int) -> int:
    conn = sqlite3.connect(config.DB_PATH)
    try:
        return int(
            conn.execute("SELECT COUNT(*) FROM races WHERE season = ?", (season,)).fetchone()[0]
        )
    finally:
        conn.close()


def checkpoint_wal() -> None:
    conn = sqlite3.connect(config.DB_PATH)
    try:
        result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        log(f"WAL checkpoint: {result}")
    finally:
        conn.close()


def validation_ok() -> bool:
    """validate.main retorna 0 quando o relatório é APROVADO."""
    return validate.main(["--db", str(config.DB_PATH)]) == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--round", type=int, default=None)
    parser.add_argument("--timeout-minutes", type=int, default=360)
    args = parser.parse_args()

    season = args.season
    if season not in config.IN_PROGRESS_SEASONS:
        raise SystemExit(
            f"{season} não está marcada como em andamento; use o fluxo de encerramento."
        )
    log(f"=== Atualização de {season} ===")
    before = race_count(season)
    if args.round:
        wait_for_round(season, args.round, args.timeout_minutes)

    summary = import_seasons(
        seasons=[season], db_path=str(config.DB_PATH), log_fn=log, progress=lambda *_: None
    )
    log(f"Importação: {summary.get('ok')} — {summary.get('errors')}")
    after = race_count(season)
    if after < before:
        raise RuntimeError(
            f"Importação reduziu GPs de {season} de {before} para {after}; "
            "nada foi publicado."
        )

    log("Validando base...")
    if not validation_ok():
        raise RuntimeError("Validação falhou; nada foi publicado.")

    checkpoint_wal()

    git("add", "data/f1.db", "data/validation_report.json")
    staged = git("diff", "--cached", "--name-only")
    if not staged:
        log("Nenhuma alteração versionada; nada a publicar.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    git("commit", "-m", f"Atualiza temporada {season} ({stamp})")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    git("push", "origin", branch)
    log("Publicado. O Streamlit Cloud deve redeployar automaticamente.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"FALHA: {exc}")
        raise
