"""Cadastra pilotos/equipes que só aparecem na Wikipédia (1990–1992).

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
