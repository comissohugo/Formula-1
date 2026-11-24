"""Cadastra pilotos/equipes que só aparecem na Wikipédia (1970–1992).

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
    # 1975–1979: pilotos que apenas tentaram a classificação e por isso não
    # aparecem nos resultados da fonte primária. Nomes/nacionalidades vêm das
    # páginas individuals da Wikipédia (en), sem qualquer estatística inferida.
    {
        "driver_id": "tony_trimmer",
        "given_name": "Tony",
        "family_name": "Trimmer",
        "full_name": "Tony Trimmer",
        "nationality": "British",
        "url": "https://en.wikipedia.org/wiki/Tony_Trimmer",
    },
    {
        "driver_id": "masami_kuwashima",
        "given_name": "Masami",
        "family_name": "Kuwashima",
        "full_name": "Masami Kuwashima",
        "nationality": "Japanese",
        "url": "https://en.wikipedia.org/wiki/Masami_Kuwashima",
    },
    {
        "driver_id": "bernard_de_dryver",
        "given_name": "Bernard",
        "family_name": "de Dryver",
        "full_name": "Bernard de Dryver",
        "nationality": "Belgian",
        "url": "https://en.wikipedia.org/wiki/Bernard_de_Dryver",
    },
    {
        "driver_id": "mikko_kozarowitzky",
        "given_name": "Mikko",
        "family_name": "Kozarowitzky",
        "full_name": "Mikko Kozarowitzky",
        "nationality": "Finnish",
        "url": "https://en.wikipedia.org/wiki/Mikko_Kozarowitzky",
    },
    {
        "driver_id": "hans_heyer",
        "given_name": "Hans",
        "family_name": "Heyer",
        "full_name": "Hans Heyer",
        "nationality": "German",
        "url": "https://en.wikipedia.org/wiki/Hans_Heyer",
    },
    {
        "driver_id": "teddy_pilette",
        "given_name": "Teddy",
        "family_name": "Pilette",
        "full_name": "Teddy Pilette",
        "nationality": "Belgian",
        "url": "https://en.wikipedia.org/wiki/Teddy_Pilette",
    },
    {
        "driver_id": "divina_galica",
        "given_name": "Divina",
        "family_name": "Galica",
        "full_name": "Divina Galica",
        "nationality": "British",
        "url": "https://en.wikipedia.org/wiki/Divina_Galica",
    },
    {
        "driver_id": "alberto_colombo",
        "given_name": "Alberto",
        "family_name": "Colombo",
        "full_name": "Alberto Colombo",
        "nationality": "Italian",
        "url": "https://en.wikipedia.org/wiki/Alberto_Colombo_(racing_driver)",
    },
    {
        "driver_id": "gimax",
        "given_name": "Carlo",
        "family_name": "Franchi",
        "full_name": "Gimax",
        "nationality": "Italian",
        "url": "https://en.wikipedia.org/wiki/Gimax",
    },
    # 1970–1974: pilotos que tentaram a classificação e por isso não aparecem
    # nos resultados da primária. Nacionalidade e nome vêm dos artigos da
    # Wikipédia (en) citados em ``url``, sem qualquer estatística inferida.
    {
        "driver_id": "william_ferguson",
        "given_name": "William",
        "family_name": "Ferguson",
        "full_name": "William Ferguson",
        "nationality": "South African",
        "url": "https://en.wikipedia.org/wiki/William_Ferguson_(racing_driver)",
    },
    {
        "driver_id": "carlo_facetti",
        "given_name": "Carlo",
        "family_name": "Facetti",
        "full_name": "Carlo Facetti",
        "nationality": "Italian",
        "url": "https://en.wikipedia.org/wiki/Carlo_Facetti",
    },
]

CONSTRUCTORS = [
    {
        "constructor_id": "coloni",
        "name": "Coloni",
        "nationality": "Italian",
        "url": "https://en.wikipedia.org/wiki/Coloni_(Formula_One)",
    },
    {
        # Equipe suíça de Loris Kessel, inscrita apenas no GP da Itália de 1977.
        "constructor_id": "apollon",
        "name": "Apollon",
        "nationality": "Swiss",
        "url": "https://en.wikipedia.org/wiki/Apollon_(Formula_One)",
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
