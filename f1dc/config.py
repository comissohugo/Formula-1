"""Configuração central do F1 Data Center."""

from pathlib import Path

# --- Fonte de dados -------------------------------------------------------
BASE_URL = "https://api.jolpi.ca/ergast/f1"
SEASONS = (
    1970,
    1971,
    1972,
    1973,
    1974,
    1975,
    1976,
    1977,
    1978,
    1979,
    1980,
    1981,
    1982,
    1983,
    1984,
    1985,
    1986,
    1987,
    1988,
    1989,
    1990,
    1991,
    1992,
    1993,
    1994,
    1995,
    1996,
    1997,
    1998,
    1999,
    2000,
    2001,
    2002,
    2003,
    2004,
    2005,
    2006,
    2007,
    2008,
    2009,
    2010,
    2011,
    2012,
    2013,
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
    2024,
    2025,
    2026,
)

# Temporadas importadas em modo "em andamento": entram apenas as etapas que já
# têm resultado na fonte, e a validação não exige campeão final. Ao encerrar a
# temporada, basta remover o ano deste conjunto e reimportar.
IN_PROGRESS_SEASONS = {2026}

# Calendário previsto das temporadas em andamento. Usado apenas para exibição
# ("X de Y GPs concluídos") e para a validação conferir que nenhuma etapa já
# realizada ficou de fora. Não é usado para preencher resultados.
IN_PROGRESS_CALENDAR_RACES = {2026: 23}
IN_PROGRESS_CALENDAR_SPRINTS = {2026: 6}

# Títulos já garantidos matematicamente em temporadas em andamento. A conta é
# conferida pela validação: a vantagem sobre o 2º colocado precisa ser maior
# que o máximo de pontos ainda disponível (corridas restantes x 25 por piloto,
# x 43 por equipe, mais sprints restantes). O título é exibido como
# "matemático" e conta no ranking, mas a temporada continua em andamento até
# o encerramento oficial. Usado apenas para exibição/validação, nunca para
# preencher resultados.
CLINCHED_CHAMPIONS = {
    2026: {"driver": "antonelli", "constructor": "mercedes"},
}

# Divergências de nome entre a fonte primária (Jolpica) e a fonte oficial.
# O banco mantém o nome bruto da primária; estes aliases são aplicados apenas
# na exibição e na exportação, com URL e data da conferência. Em 2026 a etapa
# de Catalunya foi renomeada para "Barcelona-Catalunya Grand Prix" porque o
# "Spanish Grand Prix" passou para o Madring (R14).
RACE_NAME_ALIASES = {
    (2026, 7): {
        "primary_name": "Barcelona Grand Prix",
        "official_name": "Barcelona-Catalunya Grand Prix",
        "source_url": "https://www.formula1.com/en/racing/2026/barcelona-catalunya",
        "verified_at": "2026-11-21",
    },
}


def official_race_name(
    season: int, round_number: int, primary_name: str | None
) -> str | None:
    """Nome oficial conferido para uma etapa, quando a primária diverge.

    Usado na importação para gravar o nome corrigido já no banco. Assim o painel
    mostra o nome certo mesmo antes do redeploy do código, e as reimportações
    de 2026 não devolvem o nome antigo. Aplica-se somente se a primária trouxer
    exatamente o ``primary_name`` esperado.
    """
    alias = RACE_NAME_ALIASES.get((season, round_number))
    if alias and primary_name == alias["primary_name"]:
        return alias["official_name"]
    return primary_name


# --- Caminhos -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "f1.db"
REPORT_PATH = DATA_DIR / "validation_report.json"

# --- HTTP -----------------------------------------------------------------
# A Jolpica pede uso responsável da API. ~2 requisições por segundo é seguro;
# o cliente aumenta o intervalo automaticamente se receber HTTP 429.
REQUEST_INTERVAL = 0.50
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
PAGE_SIZE = 100

# --- Expectativas do projeto (documento central, seção 2) -----------------
EXPECTED_RACES = {
    1970: 13,
    1971: 11,
    1972: 12,
    1973: 15,
    1974: 15,
    1975: 14,
    1976: 16,
    1977: 17,
    1978: 16,
    1979: 15,
    1980: 14,
    1981: 15,
    1982: 16,
    1983: 15,
    1984: 16,
    1985: 16,
    1986: 16,
    1987: 16,
    1988: 16,
    1989: 16,
    1990: 16,
    1991: 16,
    1992: 16,
    1993: 16,
    1994: 16,
    1995: 17,
    1996: 16,
    1997: 17,
    1998: 16,
    1999: 16,
    2000: 17,
    2001: 17,
    2002: 17,
    2003: 16,
    2004: 18,
    2005: 19,
    2006: 18,
    2007: 17,
    2008: 18,
    2009: 17,
    2010: 19,
    2011: 19,
    2012: 20,
    2013: 19,
    2014: 19,
    2015: 19,
    2016: 21,
    2017: 20,
    2018: 21,
    2019: 21,
    2020: 17,
    2021: 22,
    2022: 22,
    2023: 22,
    2024: 24,
    2025: 24,
}
EXPECTED_SPRINTS = {
    1970: 0,
    1971: 0,
    1972: 0,
    1973: 0,
    1974: 0,
    1975: 0,
    1976: 0,
    1977: 0,
    1978: 0,
    1979: 0,
    1995: 0,
    1996: 0,
    1997: 0,
    1998: 0,
    1999: 0,
    2000: 0,
    2001: 0,
    2002: 0,
    2003: 0,
    2004: 0,
    2005: 0,
    2006: 0,
    2007: 0,
    2008: 0,
    2009: 0,
    2010: 0,
    2011: 0,
    2012: 0,
    2013: 0,
    2014: 0,
    2015: 0,
    2016: 0,
    2017: 0,
    2018: 0,
    2019: 0,
    2020: 0,
    2021: 3,
    2022: 3,
    2023: 6,
    2024: 6,
    2025: 6,
}

# Conferência externa dos campeões (fontes oficiais).
# Usada apenas para VALIDAR o que a API entregou, nunca para preencher dado.
EXPECTED_CHAMPIONS = {
    1970: ("rindt", "team_lotus"),
    1971: ("stewart", "tyrrell"),
    1972: ("emerson_fittipaldi", "team_lotus"),
    1973: ("stewart", "team_lotus"),
    1974: ("emerson_fittipaldi", "mclaren"),
    1975: ("lauda", "ferrari"),
    1976: ("hunt", "ferrari"),
    1977: ("lauda", "ferrari"),
    1978: ("mario_andretti", "team_lotus"),
    1979: ("scheckter", "ferrari"),
    1980: ("jones", "williams"),
    1981: ("piquet", "williams"),
    1982: ("keke_rosberg", "ferrari"),
    1983: ("piquet", "ferrari"),
    1984: ("lauda", "mclaren"),
    1985: ("prost", "mclaren"),
    1986: ("prost", "williams"),
    1987: ("piquet", "williams"),
    1988: ("senna", "mclaren"),
    1989: ("prost", "mclaren"),
    1990: ("senna", "mclaren"),
    1991: ("senna", "mclaren"),
    1992: ("mansell", "williams"),
    1993: ("prost", "williams"),
    1994: ("michael_schumacher", "williams"),
    1995: ("michael_schumacher", "benetton"),
    1996: ("damon_hill", "williams"),
    1997: ("villeneuve", "williams"),
    1998: ("hakkinen", "mclaren"),
    1999: ("hakkinen", "ferrari"),
    2000: ("michael_schumacher", "ferrari"),
    2001: ("michael_schumacher", "ferrari"),
    2002: ("michael_schumacher", "ferrari"),
    2003: ("michael_schumacher", "ferrari"),
    2004: ("michael_schumacher", "ferrari"),
    2005: ("alonso", "renault"),
    2006: ("alonso", "renault"),
    2007: ("raikkonen", "ferrari"),
    2008: ("hamilton", "ferrari"),
    2009: ("button", "brawn"),
    2010: ("vettel", "red_bull"),
    2011: ("vettel", "red_bull"),
    2012: ("vettel", "red_bull"),
    2013: ("vettel", "red_bull"),
    2014: ("hamilton", "mercedes"),
    2015: ("hamilton", "mercedes"),
    2016: ("rosberg", "mercedes"),
    2017: ("hamilton", "mercedes"),
    2018: ("hamilton", "mercedes"),
    2019: ("hamilton", "mercedes"),
    2020: ("hamilton", "mercedes"),
    2021: ("max_verstappen", "mercedes"),
    2022: ("max_verstappen", "red_bull"),
    2023: ("max_verstappen", "red_bull"),
    2024: ("max_verstappen", "mclaren"),
    2025: ("norris", "mclaren"),
}

# Ajustes oficiais de pontos de construtores que não aparecem nos resultados
# individuais de corrida/sprint. Usados apenas para reconciliar a soma dos
# resultados com o standings oficial, nunca para alterar os dados importados.
# 2020: Racing Point perdeu 15 pontos no campeonato de construtores por causa
# do protesto sobre os dutos de freio (decisão da FIA). Os pilotos não perderam
# pontos; apenas a equipe foi penalizada no campeonato.
CONSTRUCTOR_POINT_ADJUSTMENTS = {
    (2020, "racing_point"): -15.0,
    # 1975–1978: o campeonato de construtores só creditava o melhor carro de
    # cada equipe em cada GP (os pontos dos demais carros seguem registrados nos
    # resultados, mas não contavam para a taça) e aplicava descarte dos piores
    # resultados. Os valores abaixo são a diferença contábil entre a soma bruta
    # e o standings oficial da Jolpica — não alteram nenhum resultado importado.
    (1975, "ferrari"): -17.0,
    (1975, "brabham"): -7.0,
    (1975, "mclaren"): -12.0,
    (1975, "tyrrell"): -7.0,
    (1975, "march"): -1.5,
    (1976, "ferrari"): -16.0,
    (1976, "mclaren"): -14.0,
    (1976, "tyrrell"): -17.0,
    (1976, "team_lotus"): -3.0,
    (1976, "brabham-alfa_romeo"): -2.0,
    (1977, "ferrari"): -30.0,
    (1977, "team_lotus"): -5.0,
    (1977, "mclaren"): -9.0,
    (1977, "shadow"): -1.0,
    (1978, "team_lotus"): -30.0,
    (1978, "ferrari"): -7.0,
    (1978, "brabham"): -16.0,
    (1978, "tyrrell"): -3.0,
    (1978, "mclaren"): -1.0,
    # 1970–1974: o standings oficial de construtores não credita todos os
    # resultados brutos da equipe (vigência da regra do melhor carro e dos
    # descartes, além de pilotos que trocaram de equipe durante a temporada).
    # Os valores abaixo são apenas a diferença contábil até o standings da
    # Jolpica; nenhum resultado de corrida é modificado.
    (1970, "team_lotus"): -11.0,
    (1970, "ferrari"): -21.0,
    (1970, "march"): -7.0,
    (1970, "mclaren-ford"): -1.0,
    (1970, "brm"): -2.0,
    (1970, "matra"): -1.0,
    (1971, "tyrrell"): -15.0,
    (1971, "brm"): -6.0,
    (1971, "march-ford"): -3.0,
    (1971, "ferrari"): -11.0,
    (1971, "lotus-ford"): -4.0,
    (1971, "mclaren"): -3.0,
    (1971, "matra"): -1.0,
    (1971, "surtees"): -1.0,
    (1971, "brabham"): -2.0,
    (1972, "tyrrell"): -9.0,
    (1972, "mclaren"): -17.0,
    (1972, "ferrari"): -14.0,
    (1973, "team_lotus"): -16.0,
    (1973, "tyrrell"): -38.0,
    (1973, "mclaren"): -10.0,
    (1973, "ferrari"): -2.0,
    (1973, "brm"): -1.0,
    (1974, "mclaren"): -15.0,
    (1974, "ferrari"): -25.0,
    (1974, "tyrrell"): -8.0,
    (1974, "team_lotus"): -5.0,
    (1974, "brabham"): -11.0,
}

# Ajustes oficiais de pontos de pilotos. A regra dos melhores resultados
# (descartes) vigorou de 1975 a 1990: a soma bruta dos GPs difere do standings
# oficial. Os pontos brutos seguem nos resultados; o ajuste existe apenas para
# reconciliar a validação com o standings oficial, nunca para alterar dados.
# 1977: Lauda 72 brutos / 70 oficiais; Reutemann 42 / 41.
# 1979: Scheckter 60 / 51, Villeneuve 53 / 47, Jones 43 / 40,
#       Regazzoni 32 / 29, Depailler 22 / 20 e Reutemann 25 / 20.
# 1980: só os 5 melhores resultados de cada metade do campeonato contavam —
# Jones 71 brutos / 67 oficiais, Reutemann 49 brutos / 42 oficiais.
# 1990: só os 11 melhores resultados contavam — Prost 73 brutos / 71 oficiais,
# Piquet 44 brutos / 43 oficiais.
DRIVER_POINT_ADJUSTMENTS = {
    (1977, "lauda"): -2.0,
    (1977, "reutemann"): -1.0,
    (1979, "scheckter"): -9.0,
    (1979, "gilles_villeneuve"): -6.0,
    (1979, "jones"): -3.0,
    (1979, "regazzoni"): -3.0,
    (1979, "depailler"): -2.0,
    (1979, "reutemann"): -5.0,
    (1980, "jones"): -4.0,
    (1980, "reutemann"): -7.0,
    (1985, "prost"): -3.0,
    (1986, "prost"): -2.0,
    (1986, "mansell"): -2.0,
    (1987, "piquet"): -3.0,
    (1988, "senna"): -4.0,
    (1988, "prost"): -18.0,
    (1989, "prost"): -5.0,
    (1990, "prost"): -2.0,
    (1990, "piquet"): -1.0,
}

# Equipes excluídas do campeonato de construtores pela fonte oficial. Em 1994 a
# Benetton foi excluída (Schumacher manteve o título de pilotos; Williams levou
# o de construtores) por irregularidades no filtro de combustível e no "push
# start". Em 2007 a McLaren foi excluída (posição nula, 0 pontos, texto "E") por
# causa do caso de espionagem; os pilotos mantiveram seus pontos. A soma dos
# resultados da equipe não é reconciliada com o standings nesses casos, porque
# a exclusão é uma decisão oficial que não aparece como pontuação negativa nos
# resultados individuais.
EXCLUDED_CONSTRUCTOR_CHAMPIONSHIPS = {
    (1994, "benetton"),
    (2007, "mclaren"),
}

# GPs em que a ausência de volta mais rápida é real e documentada, não falha de
# importação. A validação aceita esses casos e o relatório registra o motivo.
# Nunca preencher por suposição.
DOCUMENTED_FASTEST_LAP_ABSENCES = {
    (2021, 12): (
        "Corrida encerrada sob safety car após 1 volta; a fonte não registra "
        "volta mais rápida. Ausência real, não falha de importação."
    ),
}
