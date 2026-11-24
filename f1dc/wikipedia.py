"""Importa poles e voltas rápidas complementares da Wikipédia (pt).

A fonte primária (Jolpica/Ergast) não possui classificação completa antes de
2003 nem volta mais rápida antes de 2004. Para as temporadas antigas, a página
de temporada da Wikipédia em português traz uma tabela "Grandes Prêmios" com
pole position e volta mais rápida de cada GP. Em 1970 e 1971, cuja tabela em
português não traz essas colunas, a volta rápida é lida do infobox da página
do GP na Wikipédia em inglês.

Os dados são gravados na tabela ``session_awards`` com ``source_url`` e
``fetched_at``. Eles nunca sobrescrevem a fonte primária: o importador só grava
os prêmios que a fonte primária não possui, e o painel prefere
``qualifying_results``/``race_results`` quando ambos existem.

Uso:
    python -m f1dc.wikipedia
    python -m f1dc.wikipedia --seasons 2000,2001
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence

from . import config, db

log = logging.getLogger(__name__)

USER_AGENT = "f1-data-center/1.0 (base histórica; uso educacional)"
RAW_URL = (
    "https://pt.wikipedia.org/w/index.php?title="
    "Campeonato_Mundial_de_F%C3%B3rmula_1_de_{year}&action=raw"
)
PAGE_URL = (
    "https://pt.wikipedia.org/wiki/"
    "Campeonato_Mundial_de_F%C3%B3rmula_1_de_{year}"
)

# Em 1970 e 1971 a página de temporada em pt traz apenas o calendário, sem
# colunas de pole/volta rápida. Nesses dois anos a volta rápida complementar
# vem do infobox da página do GP na Wikipédia (en), sempre com source_url e
# fetched_at. A pole continua sendo o P1 do qualifying importado da própria
# página do GP, sem gravação duplicada em session_awards.
EN_RAW_URL = (
    "https://en.wikipedia.org/w/index.php?title="
    "{season}_{race}&action=raw"
)
EN_PAGE_URL = "https://en.wikipedia.org/wiki/{season}_{race}"
EN_FASTEST_LAP_SEASONS = {1970, 1971}

# Nomes que a Wikipédia usa de forma diferente do cadastro da fonte primária.
DRIVER_ALIASES: dict[str, str] = {
    "pedro de la rosa": "rosa",
    "pedro paulo diniz": "diniz",
    "alexander wurz": "wurz",
    "tomas enge": "enge",
    "juan pablo montoya": "montoya",
    # Grafia usada na página de 2004 da Wikipédia.
    "rubens barrichelo": "barrichello",
    # A Wikipédia usa "JJ Lehto"; a fonte primária registra "Jyrki Järvilehto".
    "jj lehto": "lehto",
    # Gimax é o nome de corrida de Carlo Franchi (1978, Itália).
    "carlo franchi": "gimax",
}

# Equipes que a Wikipédia (en) nomeia de forma diferente do cadastro da fonte
# primária, ou que nunca apareceram em um resultado e por isso não têm registro
# no banco. Usado apenas como último recurso para pilotos que não largaram.
CONSTRUCTOR_ALIASES: dict[str, str] = {
    "lotus": "team_lotus",
    "team lotus": "team_lotus",
    "venturi": "larrousse",  # Venturi Larrousse, mesmo time de 1992
    "coloni": "coloni",      # incluída como complemento documentado
    "pacific racing": "pacific",
    "scuderia ferrari": "ferrari",
    "benetton formula": "benetton",
    "williams grand prix engineering": "williams",
    "automobiles gonfaronnaises sportives": "ags",
    "footwork arrows": "footwork",
    "jordan grand prix": "jordan",
    "eurobrun": "eurobrun",
    "lola cars": "lola",
    "andrea moda": "moda",
    "tyrrell racing": "tyrrell",
    "equipe ligier": "ligier",
    "march engineering": "march",
    # 1973/1974: a Wikipédia escreve "Iso" ou "Iso-Marlboro"; o cadastro da
    # fonte primária usa "Iso Marlboro" (constructor_id iso_marlboro).
    "iso": "iso_marlboro",
    "iso marlboro": "iso_marlboro",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_name(value: str | None) -> str:
    """Normaliza nomes para comparação (acentos, caixa e pontuação)."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("\u2019", "'")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _first_link(cell: str) -> str | None:
    match = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", cell)
    if not match:
        return None
    return (match.group(2) or match.group(1)).strip()


def _all_links(cell: str) -> list[str]:
    return [
        (match.group(2) or match.group(1)).strip()
        for match in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", cell)
    ]


def _iter_table_blocks(wikitext: str):
    """Percorre os blocos ``{| ... |}`` do wikitexto, respeitando aninhamento."""
    index = 0
    while True:
        start = wikitext.find("{|", index)
        if start < 0:
            return
        depth = 0
        cursor = start
        while cursor < len(wikitext):
            if wikitext.startswith("{|", cursor):
                depth += 1
                cursor += 2
            elif wikitext.startswith("|}", cursor):
                depth -= 1
                cursor += 2
                if depth == 0:
                    break
            else:
                cursor += 1
        yield wikitext[start:cursor]
        index = cursor


def _header_label(line: str) -> str:
    label = line.lstrip("!").strip()
    if "|" in label:
        label = label.split("|", 1)[1]
    return normalize_name(label)


def parse_grand_prix_table(wikitext: str) -> list[dict[str, Any]]:
    """Extrai a tabela "Grandes Prêmios" do wikitexto da página de temporada.

    A tabela é localizada pelas colunas (Pole Position, Volta mais rápida,
    Vencedor e Equipe), não pela primeira menção ao título da seção. Isso evita
    pegar uma tabela de legenda quando o texto cita "Grandes Prêmios" antes.
    """
    block = None
    cell_labels: list[str] = []
    for candidate in _iter_table_blocks(wikitext):
        parts = candidate.split("|-")
        header = parts[1] if len(parts) > 1 else ""
        labels = [
            _header_label(line)
            for line in header.splitlines()
            if line.strip().startswith("!")
        ]
        # O primeiro cabeçalho ("GP") corresponde ao número da rodada.
        candidate_labels = labels[1:]
        if {
            "grande premio",
            "pole position",
            "volta mais rapida",
            "vencedor",
            "equipe",
        }.issubset(candidate_labels):
            block = candidate
            cell_labels = candidate_labels
            break
    if block is None:
        raise ValueError('tabela "Grandes Prêmios" não encontrada')

    rows: list[dict[str, Any]] = []
    for chunk in re.split(r"\n\|-", block)[1:]:
        lines = [line.strip() for line in chunk.strip().splitlines() if line.strip()]
        if not lines:
            continue
        # Em páginas recentes a rodada vem como ``! 1``; em 1985–1992 vem
        # como célula ``|align="center"| 1``.
        round_match = None
        for line in lines[:3]:
            normalized = re.sub(
                r'^(?:!|\|)\s*(?:[a-zA-Z-]+\s*=\s*"[^"]*"\s*)?(?:\|\s*)?',
                "",
                line.strip(),
            )
            match = re.match(r"^(\d+)", normalized)
            if match:
                round_match = match
                break
        if not round_match:
            continue
        cells = [line[1:].strip() for line in lines if line.startswith("|")]
        # Quando a rodada também é uma célula, remova-a para alinhar com os
        # rótulos (o primeiro, "GP", já foi descartado de cell_labels).
        if cells and re.sub(r"^.*\|\s*", "", cells[0]).strip().isdigit():
            cells = cells[1:]
        if len(cells) < len(cell_labels):
            continue

        def cell(label: str) -> str:
            return cells[cell_labels.index(label)]

        rows.append(
            {
                "round": int(round_match.group(1)),
                "gp": _first_link(cell("grande premio")),
                "pole": _first_link(cell("pole position")),
                "fastest_lap": _first_link(cell("volta mais rapida")),
                "winner": _first_link(cell("vencedor")),
                "team": "-".join(_all_links(cell("equipe"))),
            }
        )
    return rows


def fetch_wikitext(
    year: int,
    opener: Callable[..., Any] = urllib.request.urlopen,
    attempts: int = 3,
    pause: float = 1.0,
) -> str:
    """Baixa o wikitexto bruto da página da temporada, com retentativas."""
    request = urllib.request.Request(
        RAW_URL.format(year=year), headers={"User-Agent": USER_AGENT}
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
    raise RuntimeError(f"não foi possível baixar a página de {year}: {last_error}")


def fetch_gp_wikitext(
    season: int,
    race: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
    attempts: int = 3,
    pause: float = 1.0,
) -> str:
    """Baixa o wikitexto bruto da página de um GP na Wikipédia (en)."""
    request = urllib.request.Request(
        EN_RAW_URL.format(season=season, race=race.replace(" ", "_")),
        headers={"User-Agent": USER_AGENT},
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with opener(request, timeout=30) as response:
                return response.read().decode("utf-8")
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(pause)
    raise RuntimeError(f"não foi possível baixar {season} {race}: {last_error}")


def parse_gp_infobox(wikitext: str) -> dict[str, str | None]:
    """Lê vencedor, pole e volta rápida do infobox de uma página de GP (en).

    Em 1970 África do Sul o infobox credita Jack Brabham pela volta rápida e
    uma nota diz que algumas fontes também creditam John Surtees. Mantemos o
    nome do infobox, sem transformar a nota em um registro de empate.

    https://en.wikipedia.org/wiki/1970_South_African_Grand_Prix
    """
    fields: dict[str, str] = {}
    for line in wikitext.splitlines():
        match = re.match(r"^\|\s*([A-Za-z_][A-Za-z0-9_ ]*?)\s*=\s*(.*)$", line)
        if match:
            fields[normalize_name(match.group(1))] = match.group(2).strip()

    def linked(key: str) -> str | None:
        value = fields.get(key)
        return _first_link(value) if value else None

    return {
        "winner": linked("first driver"),
        "pole": linked("pole driver"),
        "fastest_lap": linked("fast driver"),
        "fastest_team": linked("fast team"),
    }


def _driver_lookup(conn) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in conn.execute("SELECT driver_id, full_name FROM drivers"):
        lookup[normalize_name(row["full_name"])] = row["driver_id"]
    for normalized, driver_id in DRIVER_ALIASES.items():
        lookup.setdefault(normalized, driver_id)
    return lookup


def _resolve_driver(
    name: str | None,
    lookup: dict[str, str],
    drivers_by_last_name: dict[str, list[str]],
) -> str | None:
    if not name:
        return None
    normalized = normalize_name(name)
    if normalized in lookup:
        return lookup[normalized]
    last_name = normalized.split()[-1] if normalized else ""
    candidates = drivers_by_last_name.get(last_name, [])
    if len(candidates) == 1:
        return candidates[0]
    return None


def _constructor_for(
    conn,
    season: int,
    round_: int,
    driver_id: str,
    constructor_name: str | None = None,
) -> str | None:
    for table in ("race_results", "qualifying_results"):
        row = conn.execute(
            f'SELECT constructor_id FROM "{table}" '
            'WHERE season = ? AND "round" = ? AND driver_id = ? LIMIT 1',
            (season, round_, driver_id),
        ).fetchone()
        if row:
            return str(row["constructor_id"])
    # Piloto que não largou (DNS/DNQ) pode não aparecer no resultado deste GP
    # nem na classificação importada. A equipe é a mesma na temporada: busca
    # em qualquer etapa, em vez de inventar vínculo.
    row = conn.execute(
        'SELECT constructor_id FROM race_results '
        'WHERE season = ? AND driver_id = ? '
        'ORDER BY "round" LIMIT 1',
        (season, driver_id),
    ).fetchone()
    if row:
        return str(row["constructor_id"])
    # Alguns pilotos de 1985–1992 só tentaram a classificação: a fonte primária
    # não tem nenhum resultado para eles. Nesse caso a equipe vem da própria
    # tabela da Wikipédia, nunca de inferência sobre o piloto.
    if constructor_name:
        normalized = normalize_name(constructor_name)
        alias = CONSTRUCTOR_ALIASES.get(normalized)
        if alias:
            return alias
        known = {
            normalize_name(r["name"]): str(r["constructor_id"])
            for r in conn.execute("SELECT constructor_id, name FROM constructors")
        }
        return known.get(normalized)
    return None


def _seasons_with_gaps(conn) -> list[int]:
    rows = conn.execute(
        """
        SELECT DISTINCT r.season
        FROM races r
        WHERE NOT EXISTS (
                SELECT 1 FROM qualifying_results q
                WHERE q.season = r.season AND q."round" = r."round"
                  AND q.position = 1
              )
           OR NOT EXISTS (
                SELECT 1 FROM fastest_laps f
                WHERE f.season = r.season AND f."round" = r."round"
              )
        ORDER BY r.season
        """
    ).fetchall()
    return [int(row["season"]) for row in rows]


def import_seasons(
    seasons: Sequence[int] | None = None,
    db_path: str = str(config.DB_PATH),
    fetcher: Callable[[int], str] = fetch_wikitext,
    gp_fetcher: Callable[[int, str], str] = fetch_gp_wikitext,
    now: str | None = None,
    log_fn: Callable[[str], None] = log.info,
) -> dict[str, Any]:
    """Importa os prêmios complementares das temporadas informadas."""
    conn = db.connect(db_path)
    db.init_db(conn)
    if not seasons:
        seasons = _seasons_with_gaps(conn)
    seasons = tuple(int(s) for s in seasons)
    fetched_at = now or _now()

    summary: dict[int, dict[str, Any]] = {}
    errors: list[str] = []

    try:
        for season in seasons:
            expected = getattr(config, "EXPECTED_RACES", {}).get(season)
            lookup = _driver_lookup(conn)
            by_last_name: dict[str, list[str]] = {}
            for row in conn.execute("SELECT driver_id, full_name FROM drivers"):
                last = normalize_name(row["full_name"]).split()[-1]
                by_last_name.setdefault(last, []).append(row["driver_id"])

            award_rows: list[dict[str, Any]] = []
            season_errors: list[str] = []
            source_url = PAGE_URL.format(year=season)

            if season in EN_FASTEST_LAP_SEASONS:
                # A tabela de temporada em pt não traz pole/volta rápida nestes
                # dois anos. Cada GP é conferido pelo infobox da Wikipédia (en).
                db_races = conn.execute(
                    'SELECT "round", race_name FROM races '
                    'WHERE season = ? ORDER BY "round"',
                    (season,),
                ).fetchall()
                if expected is not None and len(db_races) != expected:
                    errors.append(
                        f"{season}: {len(db_races)} GPs no banco, esperado {expected}"
                    )
                    log_fn(f"[{season}] ERRO: contagem de GPs divergente; nada gravado")
                    continue
                source_url = EN_PAGE_URL.format(
                    season=season, race="Formula_One_World_Championship"
                )
                for db_race in db_races:
                    round_ = int(db_race["round"])
                    race_name = str(db_race["race_name"])
                    try:
                        info = parse_gp_infobox(gp_fetcher(season, race_name))
                    except Exception as exc:
                        season_errors.append(f"R{round_}: falha ao ler GP: {exc}")
                        continue

                    db_winner = conn.execute(
                        """
                        SELECT driver_id FROM race_results
                        WHERE season = ? AND "round" = ? AND position = 1
                        """,
                        (season, round_),
                    ).fetchone()
                    wiki_winner = _resolve_driver(info["winner"], lookup, by_last_name)
                    if db_winner is None or wiki_winner != db_winner["driver_id"]:
                        season_errors.append(
                            f"R{round_}: vencedor divergente "
                            f"(Wikipédia en={info['winner']!r}, "
                            f"banco={db_winner['driver_id'] if db_winner else None!r})"
                        )
                        continue

                    # A pole já vem do P1 do qualifying importado da Wikipédia
                    # (en). Aqui apenas conferimos que o infobox concorda, sem
                    # gravar uma segunda cópia em session_awards.
                    wiki_pole = _resolve_driver(info["pole"], lookup, by_last_name)
                    db_pole = conn.execute(
                        """
                        SELECT driver_id FROM qualifying_results
                        WHERE season = ? AND "round" = ? AND position = 1
                        LIMIT 1
                        """,
                        (season, round_),
                    ).fetchone()
                    if db_pole is None or wiki_pole != db_pole["driver_id"]:
                        season_errors.append(
                            f"R{round_}: pole divergente "
                            f"(infobox={info['pole']!r}, "
                            f"qualifying={db_pole['driver_id'] if db_pole else None!r})"
                        )
                        continue

                    primary = conn.execute(
                        """
                        SELECT 1 FROM fastest_laps
                        WHERE season = ? AND "round" = ? LIMIT 1
                        """,
                        (season, round_),
                    ).fetchone()
                    if primary is not None:
                        continue

                    driver_id = _resolve_driver(info["fastest_lap"], lookup, by_last_name)
                    if driver_id is None:
                        season_errors.append(
                            f"R{round_}: piloto não mapeado em volta rápida: "
                            f"{info['fastest_lap']!r}"
                        )
                        continue
                    constructor_id = _constructor_for(
                        conn, season, round_, driver_id, info["fastest_team"]
                    )
                    if constructor_id is None:
                        season_errors.append(
                            f"R{round_}: equipe não encontrada para {driver_id} "
                            "em volta rápida"
                        )
                        continue
                    award_rows.append(
                        {
                            "season": season,
                            "round": round_,
                            "award": "fastest_lap",
                            "driver_id": driver_id,
                            "constructor_id": constructor_id,
                            "source_url": EN_PAGE_URL.format(
                                season=season,
                                race=race_name.replace(" ", "_"),
                            ),
                            "fetched_at": fetched_at,
                        }
                    )
                rows_count = len(db_races)
            else:
                try:
                    wikitext = fetcher(season)
                    rows = parse_grand_prix_table(wikitext)
                except Exception as exc:
                    errors.append(f"{season}: falha ao obter/parsear a página: {exc}")
                    log_fn(f"[{season}] ERRO: {exc}")
                    continue

                if expected is not None and len(rows) != expected:
                    errors.append(
                        f"{season}: {len(rows)} GPs na Wikipédia, esperado {expected}"
                    )
                    log_fn(f"[{season}] ERRO: contagem de GPs divergente; nada gravado")
                    continue
                rows_count = len(rows)

                for row in rows:
                    round_ = int(row["round"])
                    race = conn.execute(
                        'SELECT race_name FROM races WHERE season = ? AND "round" = ?',
                        (season, round_),
                    ).fetchone()
                    if race is None:
                        season_errors.append(
                            f"R{round_}: GP não existe no banco ({row.get('gp')})"
                        )
                        continue

                    db_winner = conn.execute(
                        """
                        SELECT driver_id FROM race_results
                        WHERE season = ? AND "round" = ? AND position = 1
                        """,
                        (season, round_),
                    ).fetchone()
                    wiki_winner = _resolve_driver(
                        row["winner"], lookup, by_last_name
                    )
                    if db_winner is None or wiki_winner != db_winner["driver_id"]:
                        season_errors.append(
                            f"R{round_}: vencedor divergente "
                            f"(Wikipédia={row['winner']!r}, banco={db_winner['driver_id'] if db_winner else None!r})"
                        )
                        continue

                    for award, key in (("pole", "pole"), ("fastest_lap", "fastest_lap")):
                        # A fonte primária sempre tem prioridade: se ela já traz
                        # o prêmio deste GP, não gravamos uma cópia complementar.
                        if award == "pole":
                            primary = conn.execute(
                                """
                                SELECT 1 FROM qualifying_results
                                WHERE season = ? AND "round" = ? AND position = 1
                                LIMIT 1
                                """,
                                (season, round_),
                            ).fetchone()
                        else:
                            primary = conn.execute(
                                """
                                SELECT 1 FROM fastest_laps
                                WHERE season = ? AND "round" = ?
                                LIMIT 1
                                """,
                                (season, round_),
                            ).fetchone()
                        if primary is not None:
                            continue

                        driver_id = _resolve_driver(row[key], lookup, by_last_name)
                        if driver_id is None:
                            season_errors.append(
                                f"R{round_}: piloto não mapeado em {award}: {row[key]!r}"
                            )
                            continue
                        constructor_id = _constructor_for(conn, season, round_, driver_id)
                        if constructor_id is None:
                            season_errors.append(
                                f"R{round_}: equipe não encontrada para {driver_id} "
                                f"em {award}"
                            )
                            continue
                        award_rows.append(
                            {
                                "season": season,
                                "round": round_,
                                "award": award,
                                "driver_id": driver_id,
                                "constructor_id": constructor_id,
                                "source_url": PAGE_URL.format(year=season),
                                "fetched_at": fetched_at,
                            }
                        )

            if season_errors:
                errors.extend(f"{season}: {message}" for message in season_errors)
                log_fn(
                    f"[{season}] ERRO: {len(season_errors)} problema(s); "
                    "temporada não foi gravada para não gravar dado incerto."
                )
                continue

            with conn:
                conn.execute(
                    'DELETE FROM session_awards WHERE season = ?', (season,)
                )
                db.upsert_rows(conn, "session_awards", award_rows)

            poles = sum(1 for row in award_rows if row["award"] == "pole")
            fastest = sum(1 for row in award_rows if row["award"] == "fastest_lap")
            summary[season] = {
                "races": rows_count,
                "poles": poles,
                "fastest_laps": fastest,
                "source_url": source_url,
            }
            log_fn(
                f"[{season}] gravado: {poles} poles e {fastest} voltas rápidas "
                "complementares"
            )

        return {
            "status": "ok" if not errors else "incomplete",
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
        description="Importa poles e voltas rápidas complementares da Wikipédia (pt)."
    )
    parser.add_argument(
        "--seasons",
        default="",
        help=(
            "lista separada por vírgula; padrão: temporadas com lacuna de pole "
            "ou volta rápida na fonte primária"
        ),
    )
    parser.add_argument("--db", default=str(config.DB_PATH), help="caminho do SQLite")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    seasons = [int(item.strip()) for item in args.seasons.split(",") if item.strip()]
    result = import_seasons(
        seasons=seasons or None,
        db_path=args.db,
    )

    print("\n=== RESUMO (Wikipédia) ===")
    for season, info in result["seasons"].items():
        print(
            f"{season}: {info['races']} GPs | {info['poles']} poles | "
            f"{info['fastest_laps']} voltas rápidas | {info['source_url']}"
        )
    print(f"Status: {result['status']}")
    if result["errors"]:
        print("Erros:")
        for error in result["errors"]:
            print(f"  - {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
