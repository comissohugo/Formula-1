"""Completa a classificação (qualifying) antiga com a Wikipédia (en).

A fonte primária (Jolpica/Ergast) não possui classificação completa em todas as
etapas de 1990–2002. As páginas de cada Grande Prêmio na Wikipédia em inglês
trazem a tabela de qualifying com posição, piloto, equipe e tempo, citando os
arquivos da FIA. Este módulo importa **apenas os GPs em que a fonte primária
não tem nenhuma linha de classificação**.

Regras de integridade:

* a fonte primária sempre tem prioridade: GPs com qualifying na fonte primária
  nunca são sobrescritos; quando possível, os dados da Wikipédia são usados
  apenas para conferência;
* cada linha gravada leva ``source_url`` e ``fetched_at``;
* pilotos que não se classificaram (DNQ) ou foram excluídos (EX) não recebem
  posição inventada — a linha é ignorada e registrada no resumo;
* a temporada é gravada de forma atômica: se qualquer GP falhar na conferência,
  nada é gravado;
* reimportar não duplica: as linhas complementares da temporada são apagadas e
  regravadas.

Uso:
    python -m f1dc.wikipedia_qualifying
    python -m f1dc.wikipedia_qualifying --seasons 2001,2002
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from . import config, db
from .wikipedia import (
    _constructor_for,
    _driver_lookup,
    _first_link,
    _iter_table_blocks,
    _resolve_driver,
    normalize_name,
)

log = logging.getLogger(__name__)

USER_AGENT = "f1-data-center/1.0 (base histórica; uso educacional)"
RAW_URL = (
    "https://en.wikipedia.org/w/index.php?title="
    "{season}_{race}&action=raw"
)
PAGE_URL = "https://en.wikipedia.org/wiki/{season}_{race}"

# Marcador usado para reconhecer as linhas complementares já gravadas.
WIKIPEDIA_MARKER = "wikipedia.org"

# Temporadas cujas páginas de GP usam o formato de tabela suportado por este
# importador (posição, piloto, equipe e tempo; grid quando existir). 1990–1994
# usam duas sessões (Q1/Q2) e às vezes uma tabela de pré-classificação antes da
# principal; 1996 usa coluna de tempo; 1998 usa ``Lap Time``; 2000 usa tabelas
# sem coluna de grid e predefinições {{sort}}/{{sortname}}; 2001 usa ``Lap``.
SUPPORTED_SEASONS = (
    1990, 1991, 1992, 1993, 1994,
    1996, 1997, 1998, 1999, 2000, 2001, 2002,
)

# Rótulos de coluna de tempo encontrados nas páginas antigas: ``Time`` (2000),
# ``Lap`` (2001), ``Lap Time`` (1998) e as duas sessões de 1990–1994, escritas
# de várias formas conforme a página: ``Q1``/``Q2``, ``Q1 Time``/``Q2 Time`` ou
# ``Friday Time``/``Saturday Time``.
TIME_LABELS = (
    "time", "lap", "lap time",
    "q1", "q2", "q1 time", "q2 time",
    "friday time", "saturday time",
)

MIN_CLASSIFIED = 10

# Divergências conhecidas entre a fonte primária e a Wikipédia em GPs que a
# fonte primária já cobre. A fonte primária é mantida (nunca sobrescrita) e a
# divergência vira aviso, sem bloquear o preenchimento dos demais GPs. Cada
# exceção precisa de justificativa e fonte externa de conferência.
PRIMARY_DIVERGENCE_EXCEPTIONS = {
    (1994, 1): (
        "Bernard (P20): primária 1:19.398, Wikipédia 1:19.396. "
        "Fonte primária mantida. "
        "https://en.wikipedia.org/wiki/1994_Brazilian_Grand_Prix"
    ),
    (1994, 3): (
        "Wikipédia marca Ratzenberger como WD e coloca Belmondo em P26; a "
        "primária registra Ratzenberger em P26 (1:27.584) e Belmondo em P27. "
        "Fonte primária mantida. "
        "https://en.wikipedia.org/wiki/1994_San_Marino_Grand_Prix"
    ),
    (1994, 12): (
        "Järvilehto (P20): Wikipédia escreve 26.384 sem o minuto; primária "
        "registra 1:26.384. Fonte primária mantida. "
        "https://en.wikipedia.org/wiki/1994_Italian_Grand_Prix"
    ),
    (1997, 2): (
        "Frentzen (P8): primária 1:16.971, Wikipédia 1:16.924. "
        "Fonte primária mantida. "
        "https://en.wikipedia.org/wiki/1997_Brazilian_Grand_Prix"
    ),
    (1997, 3): (
        "Diniz (P22): primária 1:28.696, Wikipédia 1:28.969. "
        "Fonte primária mantida. "
        "https://en.wikipedia.org/wiki/1997_Argentine_Grand_Prix"
    ),
    (1997, 8): (
        "P12/P13: primária Barrichello 12º e Nakano 13º (ambos 1:15.876); "
        "Wikipédia inverte (Nakano 1:15.857, Barrichello 1:15.876). "
        "Fonte primária mantida. "
        "https://en.wikipedia.org/wiki/1997_French_Grand_Prix"
    ),
    (1997, 9): (
        "P14–P22: primária registra Fontana em P22 sem tempo, deslocando "
        "os demais uma posição; Wikipédia dá 1:23.790 a Fontana em P14. "
        "Fonte primária mantida. "
        "https://en.wikipedia.org/wiki/1997_British_Grand_Prix"
    ),
    (1998, 3): (
        "Wurz (P8): primária 1:27.198, Wikipédia 1:27.196; Diniz (P18): "
        "primária 1:29.617, Wikipédia 1:30.022. Fonte primária mantida. "
        "https://en.wikipedia.org/wiki/1998_Argentine_Grand_Prix"
    ),
    (1999, 2): (
        "P16–P21: primária registra Villeneuve em P21 sem tempo, deslocando "
        "os demais uma posição; Wikipédia dá 1:19.377 a Villeneuve em P16. "
        "Fonte primária mantida. "
        "https://en.wikipedia.org/wiki/1999_Brazilian_Grand_Prix"
    ),
    (2000, 3): (
        "Barrichello (P4): fonte primária 1:25.871 (repetido de Ralf "
        "Schumacher); Wikipédia e formula1.com registram 1:25.242. "
        "Fonte primária mantida. "
        "https://www.formula1.com/en/results/2000/races/49/san-marino/qualifying/0"
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _expand_templates(text: str) -> str:
    """Expande predefinições de ordenação usadas nas tabelas de 2000."""
    def sort_repl(match: re.Match[str]) -> str:
        parts = [part.strip() for part in match.group(1).split("|")]
        return parts[-1]

    def sortname_repl(match: re.Match[str]) -> str:
        parts = [part.strip() for part in match.group(1).split("|")]
        return " ".join(part for part in parts[:2] if part)

    text = re.sub(r"\{\{[Ss]ort\|([^{}]*)\}\}", sort_repl, text)
    return re.sub(r"\{\{[Ss]ortname\|([^{}]*)\}\}", sortname_repl, text)


def _clean_cell(cell: str) -> str:
    """Remove referências, notas e predefinições de uma célula."""
    cell = _expand_templates(cell)
    cell = re.sub(r"<ref[^>]*/>", "", cell)
    cell = re.sub(r"<ref[^>]*>.*?</ref>", "", cell, flags=re.DOTALL)
    cell = cell.replace("&mdash;", "—").replace("&ndash;", "–")
    cell = cell.replace("&nbsp;", " ")
    cell = re.sub(r"\{\{.*?\}\}", "", cell)
    return cell.strip()


def _abbreviation(cell: str) -> str | None:
    match = re.search(r"\{\{[Aa]bbr\|([^|}]+)", cell)
    return match.group(1).strip() if match else None


def _strip_attributes(cell: str) -> str:
    """Remove ``scope="row"``, ``align="center"`` e afins de uma célula."""
    cell = cell.lstrip("!|").strip()
    separator = cell.find("|")
    if separator >= 0 and "=" in cell[:separator]:
        cell = cell[separator + 1 :].strip()
    return cell


def _header_label(line: str) -> str:
    label = _strip_attributes(line)
    # Predefinições de cabeçalho: usamos só o texto exibido. Em 2001, a coluna
    # de tempo aparece como ``Lap`` e o grid como ``{{Tooltip|Grid|...}}``.
    label = re.sub(
        r"\{\{(?:[Aa]bbr|[Tt]ooltip)\|([^|}]*)(?:\|[^}]*)?\}\}", r"\1", label
    )
    return normalize_name(re.sub(r"\{\{.*?\}\}", " ", label))


def _driver_name(cell: str) -> str | None:
    name = _first_link(_expand_templates(cell)) or _clean_cell(cell)
    if not name:
        return None
    # Remove desambiguação do tipo "Mark Webber (racing driver)".
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()


def _lap_time(cell: str) -> str | None:
    text = _clean_cell(cell)
    match = re.search(r"\b(\d+:\d{2}\.\d{3}|\d+\.\d{3})\b", text)
    return match.group(1) if match else None


def _time_seconds(value: str) -> float:
    """Converte ``1:15.962`` em segundos para escolher o melhor tempo."""
    minutes, seconds = value.split(":") if ":" in value else ("0", value)
    return int(minutes) * 60 + float(seconds)


def _split_rows(table: str) -> list[str]:
    """Separa as linhas de uma tabela, tolerando o separador malformado ``|-|``.

    Em Itália 1994 a Wikipédia usa ``|-|`` como separador de linha: o pipe
    extra é vazio, não uma célula de dados. Removê-lo evita deslocar todas as
    colunas e perder a posição 2 daquela classificação.
    """
    table = re.sub(r"(?m)^\|-\|[ \t]*$", "|-", table)
    return re.split(r"\n\|-", table)


def parse_qualifying_table(wikitext: str) -> dict[str, Any]:
    """Extrai a tabela de classificação de uma página de Grande Prêmio.

    Retorna ``{"rows": [...], "skipped": [...]}``. Só entram em ``rows`` os
    pilotos com posição numérica; DNQ/EX ficam em ``skipped`` com o motivo.
    """
    best: dict[str, Any] | None = None
    for candidate in _iter_table_blocks(wikitext):
        chunks = _split_rows(candidate)
        # Em algumas páginas (ex.: Japão 2000) o cabeçalho vem antes do
        # primeiro ``|-``; em outras, vem no segundo bloco.
        header_index = 0
        if not any(
            line.strip().startswith("!") for line in chunks[0].splitlines()
        ):
            header_index = 1
        header = chunks[header_index] if len(chunks) > header_index else ""
        candidate_labels: list[str] = []
        for line in header.splitlines():
            line = line.strip()
            if not line.startswith("!"):
                continue
            # Cabeçalhos compactos usam ``!!`` como separador (Austrália 2000).
            for piece in line.split("!!"):
                piece = piece.strip()
                if piece:
                    candidate_labels.append(
                        _header_label(piece if piece.startswith("!") else "!" + piece)
                    )
        if (
            "driver" in candidate_labels
            and "constructor" in candidate_labels
            and any(label in TIME_LABELS for label in candidate_labels)
        ):
            count = sum(
                1
                for chunk in chunks[header_index + 1:]
                if re.fullmatch(r"\d+", _clean_cell(_strip_attributes(
                    next(
                        (line for line in chunk.strip().splitlines() if line.strip()),
                        "",
                    )
                )).rstrip("*") or "")
            )
            if best is None or count > best["count"]:
                best = {
                    "table": candidate,
                    "labels": candidate_labels,
                    "data_start": header_index + 1,
                    "count": count,
                }
    if best is None:
        raise ValueError("tabela de classificação não encontrada")

    table = best["table"]
    labels: list[str] = best["labels"]
    data_start: int = best["data_start"]

    driver_idx = labels.index("driver")
    constructor_idx = labels.index("constructor")
    time_indices = [
        labels.index(label) for label in TIME_LABELS if label in labels
    ]
    position_idx = 0

    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for chunk in _split_rows(table)[data_start:]:
        lines = [line.strip() for line in chunk.strip().splitlines() if line.strip()]
        if not lines:
            continue
        cells = [_strip_attributes(line) for line in lines]
        if len(cells) <= max(driver_idx, constructor_idx, *time_indices):
            continue

        position_text = _abbreviation(cells[position_idx]) or _clean_cell(
            cells[position_idx]
        )
        # 1997 Bélgica usa ``6*`` para marcar nota de rodapé na posição.
        position_text = position_text.rstrip("*")
        position_match = re.fullmatch(r"\d+", position_text)
        name = _driver_name(cells[driver_idx])
        if position_match is None:
            if name:
                skipped.append({"reason": position_text or "sem posição", "driver": name})
            continue

        # 1990–1994 têm duas sessões (Q1/Q2). O tempo que representa o piloto é
        # o melhor (menor) delas; nenhum dos dois existindo, fica ausente.
        times = [
            _lap_time(cells[index])
            for index in time_indices
            if _lap_time(cells[index]) is not None
        ]
        best_time = min(times, key=_time_seconds) if times else None
        rows.append(
            {
                "position": int(position_match.group(0)),
                "driver": name,
                "constructor": _first_link(cells[constructor_idx]),
                "time": best_time,
            }
        )

    if not rows:
        raise ValueError("tabela de classificação sem linhas válidas")

    positions = [row["position"] for row in rows]
    if len(set(positions)) != len(positions):
        raise ValueError("posições duplicadas na tabela de classificação")
    if sorted(positions) != list(range(1, len(rows) + 1)):
        raise ValueError(f"posições não sequenciais: {sorted(positions)[:5]}...")
    if len(rows) < MIN_CLASSIFIED:
        raise ValueError(f"apenas {len(rows)} pilotos classificados")
    for row in rows:
        if not row["driver"]:
            raise ValueError(f"piloto ausente na posição {row['position']}")
    # A pole (P1) precisa de tempo: é dela que derivamos o prêmio. Nas demais
    # posições, um tempo em branco (ex.: Irvine em França 1996) é registrado
    # como ausente — nunca como zero — e segue para a base como NULL.
    if rows[0]["time"] is None:
        raise ValueError(
            f"tempo ausente para {rows[0]['driver']} (P1)"
        )
    return {"rows": rows, "skipped": skipped}


def fetch_wikitext(
    season: int,
    race: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
    attempts: int = 3,
    pause: float = 1.0,
) -> str:
    """Baixa o wikitexto bruto de um GP, com retentativas."""
    request = urllib.request.Request(
        RAW_URL.format(season=season, race=race.replace(" ", "_")),
        headers={"User-Agent": USER_AGENT},
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with opener(request, timeout=30) as response:
                return response.read().decode("utf-8")
        except Exception as exc:  # rede/HTTP: tenta de novo antes de desistir
            last_error = exc
            if attempt < attempts:
                time.sleep(pause)
    raise RuntimeError(f"não foi possível baixar {season} {race}: {last_error}")


def _seasons_with_gaps(conn) -> list[int]:
    rows = conn.execute(
        """
        SELECT DISTINCT r.season
        FROM races r
        WHERE NOT EXISTS (
            SELECT 1 FROM qualifying_results q
            WHERE q.season = r.season AND q."round" = r."round"
        )
        ORDER BY r.season
        """
    ).fetchall()
    return [int(row["season"]) for row in rows]


def _primary_rows(conn, season: int, round_: int) -> dict[int, tuple[str, str | None]]:
    return {
        int(row["position"]): (str(row["driver_id"]), row["q1"])
        for row in conn.execute(
            """
            SELECT position, driver_id, q1
            FROM qualifying_results
            WHERE season = ? AND "round" = ? AND position IS NOT NULL
              AND (source_url IS NULL OR source_url NOT LIKE '%wikipedia.org%')
            """,
            (season, round_),
        )
    }


def import_seasons(
    seasons: Sequence[int] | None = None,
    db_path: str = str(config.DB_PATH),
    fetcher: Callable[[int, str], str] = fetch_wikitext,
    now: str | None = None,
    log_fn: Callable[[str], None] = log.info,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Importa a classificação complementar dos GPs sem dado primário."""
    conn = db.connect(db_path)
    db.init_db(conn)
    if not seasons:
        seasons = [
            season
            for season in _seasons_with_gaps(conn)
            if season in SUPPORTED_SEASONS
        ]
    seasons = tuple(int(s) for s in seasons)
    fetched_at = now or _now()

    summary: dict[int, dict[str, Any]] = {}
    errors: list[str] = []

    try:
        for season in seasons:
            races = conn.execute(
                'SELECT "round", race_name FROM races WHERE season = ? ORDER BY "round"',
                (season,),
            ).fetchall()
            if not races:
                errors.append(f"{season}: temporada não existe no banco")
                continue

            lookup = _driver_lookup(conn)
            by_last_name: dict[str, list[str]] = {}
            for row in conn.execute("SELECT driver_id, full_name FROM drivers"):
                last = normalize_name(row["full_name"]).split()[-1]
                by_last_name.setdefault(last, []).append(row["driver_id"])

            rows_to_write: list[dict[str, Any]] = []
            season_errors: list[str] = []
            skipped_drivers: list[str] = []
            filled_rounds: list[int] = []
            confirmed_rounds: list[int] = []
            divergent_rounds: list[int] = []

            for race in races:
                round_ = int(race["round"])
                race_name = str(race["race_name"])
                primary = _primary_rows(conn, season, round_)
                try:
                    wikitext = fetcher(season, race_name)
                    parsed = parse_qualifying_table(wikitext)
                except Exception as exc:
                    if primary:
                        log_fn(
                            f"[{season} R{round_}] aviso: não foi possível conferir "
                            f"{race_name}: {exc}"
                        )
                        continue
                    season_errors.append(f"R{round_}: {exc}")
                    continue

                wiki_rows = parsed["rows"]
                skipped_drivers.extend(
                    f"R{round_}: {item['driver']} ({item['reason']})"
                    for item in parsed["skipped"]
                )

                # P1 da Wikipédia precisa concordar com a pole complementar (pt).
                pole = conn.execute(
                    """
                    SELECT driver_id FROM session_awards
                    WHERE season = ? AND "round" = ? AND award = 'pole'
                    """,
                    (season, round_),
                ).fetchone()
                wiki_pole = _resolve_driver(
                    wiki_rows[0]["driver"], lookup, by_last_name
                )
                if wiki_pole is None:
                    season_errors.append(
                        f"R{round_}: pole não mapeada ({wiki_rows[0]['driver']!r})"
                    )
                    continue
                if pole is not None and pole["driver_id"] != wiki_pole:
                    season_errors.append(
                        f"R{round_}: pole divergente (Wikipédia en={wiki_pole!r}, "
                        f"Wikipédia pt={pole['driver_id']!r})"
                    )
                    continue

                if primary:
                    # Fonte primária manda: só conferimos, nunca sobrescrevemos.
                    expected = _primary_rows(conn, season, round_)
                    # Linhas sem tempo são marcadores de DNQ/EX na primária
                    # (ex.: 1996 Brasil P21/P22). Não competem com a ordem
                    # dos pilotos que efetivamente classificaram.
                    expected = {
                        position: value
                        for position, value in expected.items()
                        if value[1] is not None
                    }
                    actual = {}
                    for row in wiki_rows:
                        if row["time"] is None:
                            continue
                        driver_id = _resolve_driver(
                            row["driver"], lookup, by_last_name
                        )
                        if driver_id is None:
                            season_errors.append(
                                f"R{round_}: piloto não mapeado "
                                f"({row['driver']!r})"
                            )
                            break
                        actual[int(row["position"])] = (driver_id, row["time"])
                    else:
                        if actual != expected:
                            divergences = [
                                position
                                for position in sorted(set(actual) | set(expected))
                                if actual.get(position) != expected.get(position)
                            ]
                            known = PRIMARY_DIVERGENCE_EXCEPTIONS.get(
                                (season, round_)
                            )
                            if known is not None:
                                divergent_rounds.append(round_)
                                log_fn(
                                    f"[{season} R{round_}] aviso: divergência "
                                    f"conhecida mantida na fonte primária "
                                    f"(posições {divergences[:5]}): {known}"
                                )
                                continue
                            season_errors.append(
                                f"R{round_}: conferência divergente em "
                                f"{len(divergences)} posição(ões) "
                                f"{divergences[:5]}"
                            )
                            continue
                        confirmed_rounds.append(round_)
                    continue

                round_rows: list[dict[str, Any]] = []
                for row in wiki_rows:
                    driver_id = _resolve_driver(
                        row["driver"], lookup, by_last_name
                    )
                    if driver_id is None:
                        season_errors.append(
                            f"R{round_}: piloto não mapeado ({row['driver']!r})"
                        )
                        break
                    constructor_id = _constructor_for(
                        conn, season, round_, driver_id, row["constructor"]
                    )
                    if constructor_id is None:
                        season_errors.append(
                            f"R{round_}: equipe não encontrada para {driver_id}"
                        )
                        break
                    number = conn.execute(
                        """
                        SELECT number FROM race_results
                        WHERE season = ? AND "round" = ? AND driver_id = ?
                        LIMIT 1
                        """,
                        (season, round_, driver_id),
                    ).fetchone()
                    round_rows.append(
                        {
                            "season": season,
                            "round": round_,
                            "driver_id": driver_id,
                            "constructor_id": constructor_id,
                            "number": number["number"] if number else None,
                            "position": int(row["position"]),
                            "q1": row["time"],
                            "q2": None,
                            "q3": None,
                            "source_url": PAGE_URL.format(
                                season=season, race=race_name.replace(" ", "_")
                            ),
                            "fetched_at": fetched_at,
                        }
                    )
                else:
                    rows_to_write.extend(round_rows)
                    filled_rounds.append(round_)

            if season_errors:
                errors.extend(f"{season}: {message}" for message in season_errors)
                log_fn(
                    f"[{season}] ERRO: {len(season_errors)} problema(s); "
                    "temporada não foi gravada para não gravar dado incerto."
                )
                continue

            if not dry_run:
                with conn:
                    conn.execute(
                        """
                        DELETE FROM qualifying_results
                        WHERE season = ? AND source_url LIKE ?
                        """,
                        (season, f"%{WIKIPEDIA_MARKER}%"),
                    )
                    db.upsert_rows(conn, "qualifying_results", rows_to_write)

            summary[season] = {
                "races": len(races),
                "filled_races": len(filled_rounds),
                "confirmed_primary": len(confirmed_rounds),
                "divergent_primary": divergent_rounds,
                "rows": len(rows_to_write),
                "skipped": skipped_drivers,
                "filled_rounds": filled_rounds,
                "source_url": (
                    f"https://en.wikipedia.org/wiki/"
                    f"{season}_Formula_One_World_Championship"
                ),
                "dry_run": dry_run,
            }
            log_fn(
                f"[{season}] {'simulação' if dry_run else 'gravado'}: "
                f"{len(filled_rounds)} GP(s) completado(s), "
                f"{len(rows_to_write)} linha(s); "
                f"{len(confirmed_rounds)} GP(s) conferido(s) contra a fonte primária; "
                f"{len(divergent_rounds)} divergência(s) conhecida(s) mantida(s) na "
                f"fonte primária; "
                f"{len(skipped_drivers)} piloto(s) sem posição (DNQ/EX)"
            )

        status = "ok" if not errors else "incomplete"
        return {
            "status": status,
            "seasons": summary,
            "errors": errors,
            "fetched_at": fetched_at,
        }
    finally:
        conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description=(
            "Completa a classificação (qualifying) ausente na fonte primária "
            "com as páginas de GP da Wikipédia (en)."
        )
    )
    parser.add_argument(
        "--seasons",
        default="",
        help=(
            "lista separada por vírgula; padrão: temporadas com GP sem "
            "classificação na fonte primária"
        ),
    )
    parser.add_argument("--db", default=str(config.DB_PATH), help="caminho do SQLite")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="baixa e confere tudo, mas não grava no banco",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    seasons = [int(item.strip()) for item in args.seasons.split(",") if item.strip()]
    result = import_seasons(
        seasons=seasons or None,
        db_path=args.db,
        dry_run=args.dry_run,
    )

    print("\n=== RESUMO (qualifying - Wikipédia en) ===")
    for season, info in result["seasons"].items():
        print(
            f"{season}: {info['races']} GPs | {info['filled_races']} completado(s) | "
            f"{info['rows']} linhas | {info['confirmed_primary']} conferido(s)"
        )
        for item in info["skipped"]:
            print(f"  sem posição: {item}")
    print(f"Status: {result['status']}")
    if result["errors"]:
        print("Erros:")
        for error in result["errors"]:
            print(f"  - {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
