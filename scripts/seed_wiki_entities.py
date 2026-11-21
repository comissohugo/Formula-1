"""Cadastra pilotos/equipes que só aparecem na Wikipédia (1980–1992).

A fonte primária (Jolpica) não registra classificação nesses anos e, por isso,
não chegou a criar cadastro para pilotos que apenas tentaram a classificação.
Este script completa o cadastro mínimo necessário para o importador de
qualifying da Wikipédia (en). Nenhuma estatística é inventada: apenas nome,
nacionalidade e a URL da página que serve de fonte. Cada linha de qualifying
gravada depois leva ``source_url`` e ``fetched_at`` próprios.

Uso:
    python scripts/seed_wiki_entities.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from f1dc import db  # noqa: E402

DRIVERS = [
    {
        "driver_id": "bartels",
        "given_name": "Michael",
        "family_name": "Bartels",
        "full_name": "Michael Bartels",
        "nationality": "German",
        "url": "https://en.wikipedia.org/wiki/Michael_Bartels",
    },
    {
        "driver_id": "amati",
        "given_name": "Giovanna",
        "family_name": "Amati",
        "full_name": "Giovanna Amati",
        "nationality": "Italian",
        "url": "https://en.wikipedia.org/wiki/Giovanna_Amati",
    },
    {
        "driver_id": "joachim_winkelhock",
        "given_name": "Joachim",
        "family_name": "Winkelhock",
        "full_name": "Joachim Winkelhock",
        "nationality": "German",
        "url": "https://en.wikipedia.org/wiki/Joachim_Winkelhock",
    },
    {
        "driver_id": "david_kennedy",
        "given_name": "David",
        "family_name": "Kennedy",
        "full_name": "David Kennedy",
        "nationality": "Irish",
        "url": "https://en.wikipedia.org/wiki/David_Kennedy_(racing_driver)",
    },
    {
        "driver_id": "harald_ertl",
        "given_name": "Harald",
        "family_name": "Ertl",
        "full_name": "Harald Ertl",
        "nationality": "Austrian",
        "url": "https://en.wikipedia.org/wiki/Harald_Ertl",
    },
    {
        "driver_id": "kevin_cogan",
        "given_name": "Kevin",
        "family_name": "Cogan",
        "full_name": "Kevin Cogan",
        "nationality": "American",
        "url": "https://en.wikipedia.org/wiki/Kevin_Cogan",
    },
    {
        "driver_id": "giorgio_francia",
        "given_name": "Giorgio",
        "family_name": "Francia",
        "full_name": "Giorgio Francia",
        "nationality": "Italian",
        "url": "https://en.wikipedia.org/wiki/Giorgio_Francia",
    },
    {
        "driver_id": "emilio_de_villota",
        "given_name": "Emilio",
        "family_name": "de Villota",
        "full_name": "Emilio de Villota",
        "nationality": "Spanish",
        "url": "https://en.wikipedia.org/wiki/Emilio_de_Villota",
    },
    {
        "driver_id": "stephen_south",
        "given_name": "Stephen",
        "family_name": "South",
        "full_name": "Stephen South",
        "nationality": "British",
        "url": "https://en.wikipedia.org/wiki/Stephen_South",
    },
]

CONSTRUCTORS = [
    {
        "constructor_id": "coloni",
        "name": "Coloni",
        "nationality": "Italian",
        "url": "https://en.wikipedia.org/wiki/Coloni_(Formula_One)",
    },
]


def main() -> None:
    conn = db.connect()
    try:
        for driver in DRIVERS:
            conn.execute(
                """
                INSERT OR IGNORE INTO drivers
                    (driver_id, given_name, family_name, full_name,
                     nationality, url)
                VALUES
                    (:driver_id, :given_name, :family_name, :full_name,
                     :nationality, :url)
                """,
                driver,
            )
        for constructor in CONSTRUCTORS:
            conn.execute(
                """
                INSERT OR IGNORE INTO constructors
                    (constructor_id, name, nationality, url)
                VALUES
                    (:constructor_id, :name, :nationality, :url)
                """,
                constructor,
            )
        conn.commit()
        print(
            f"Cadastro complementar pronto: {len(DRIVERS)} piloto(s), "
            f"{len(CONSTRUCTORS)} equipe(s)."
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
