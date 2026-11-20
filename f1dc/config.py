"""Configuração central do F1 Data Center."""

from pathlib import Path

# --- Fonte de dados -------------------------------------------------------
BASE_URL = "https://api.jolpi.ca/ergast/f1"
SEASONS = (
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
}

# Equipes excluídas do campeonato de construtores pela fonte oficial. Em 2007 a
# McLaren foi excluída (posição nula, 0 pontos, texto "E") por causa do caso de
# espionagem; os pilotos mantiveram seus pontos. A soma dos resultados da equipe
# não é reconciliada com o standings nesse caso, porque a exclusão é uma decisão
# oficial que não aparece como pontuação negativa nos resultados individuais.
EXCLUDED_CONSTRUCTOR_CHAMPIONSHIPS = {
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
