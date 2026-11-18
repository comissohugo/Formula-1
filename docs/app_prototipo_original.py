
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor

BASE = "https://api.jolpi.ca/ergast/f1"
SEASONS = [2021, 2022, 2023, 2024, 2025]

st.set_page_config(page_title="F1 Data Center", page_icon="🏁", layout="wide")
st.title("🏁 F1 DATA CENTER")
st.caption("Base histórica interativa · Temporadas 2021–2025")

@st.cache_data(ttl=86400, show_spinner=False)
def get_endpoint(path):
    rows = []
    offset = 0
    limit = 100
    while True:
        url = f"{BASE}/{path.lstrip('/')}?limit={limit}&offset={offset}"
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        payload = response.json()["MRData"]
        table = payload.get("RaceTable", {})
        races = table.get("Races", [])
        rows.extend(races)
        total = int(payload.get("total", 0))
        returned = sum(len(r.get("Results", r.get("QualifyingResults", []))) for r in races)
        # Pagination is based on the innermost result rows for results/qualifying.
        if total == 0 or offset + limit >= total:
            break
        offset += limit
        if not races or (returned == 0 and offset > total):
            break
    return rows

def fetch_season(year):
    schedule = get_endpoint(f"{year}/races.json")
    results = get_endpoint(f"{year}/results.json")
    qualifying = get_endpoint(f"{year}/qualifying.json")
    return schedule, results, qualifying

@st.cache_data(ttl=86400, show_spinner=False)
def load_all():
    schedules, result_rows, quali_rows = [], [], []
    errors = []
    progress = st.progress(0, text="Preparando importação...")
    for i, year in enumerate(SEASONS, start=1):
        try:
            s, r, q = fetch_season(year)
            schedules.extend(s)
            result_rows.extend(r)
            quali_rows.extend(q)
            progress.progress(i / len(SEASONS), text=f"Importado {year} · calendário, corrida e classificação")
        except Exception as e:
            errors.append(f"{year}: {e}")
            progress.progress(i / len(SEASONS), text=f"Falha ao importar {year}")
    progress.empty()

    races = {}
    for race in schedules:
        key = (int(race["season"]), int(race["round"]))
        races[key] = {
            "season": int(race["season"]), "round": int(race["round"]),
            "race": race.get("raceName", ""),
            "date": race.get("date", ""),
            "circuit": race.get("Circuit", {}).get("circuitName", ""),
            "locality": race.get("Circuit", {}).get("Location", {}).get("locality", ""),
            "country": race.get("Circuit", {}).get("Location", {}).get("country", ""),
        }

    def flatten(source, field, prefix):
        out = []
        for race in source:
            season, rnd = int(race["season"]), int(race["round"])
            for item in race.get(field, []):
                driver = item.get("Driver", {})
                constructor = item.get("Constructor", {})
                row = {
                    "season": season, "round": rnd,
                    "driver_id": driver.get("driverId", ""),
                    "driver": (driver.get("givenName", "") + " " + driver.get("familyName", "")).strip(),
                    "code": driver.get("code", ""),
                    "number": item.get("number", ""),
                    "team": constructor.get("name", ""),
                    "nationality": driver.get("nationality", ""),
                }
                if prefix == "race":
                    fastest = item.get("FastestLap", {})
                    row.update({
                        "position": item.get("position", ""),
                        "position_text": item.get("positionText", ""),
                        "grid": item.get("grid", ""),
                        "laps": item.get("laps", ""),
                        "points": float(item.get("points", 0) or 0),
                        "status": item.get("status", ""),
                        "fastest_lap_rank": fastest.get("rank", ""),
                        "fastest_lap": fastest.get("lap", ""),
                        "fastest_lap_time": fastest.get("Time", {}).get("time", ""),
                        "fastest_lap_speed": fastest.get("AverageSpeed", {}).get("speed", ""),
                    })
                else:
                    row.update({
                        "position": item.get("position", ""),
                        "q1": item.get("Q1", ""),
                        "q2": item.get("Q2", ""),
                        "q3": item.get("Q3", ""),
                    })
                out.append(row)
        return pd.DataFrame(out)

    race_df = flatten(result_rows, "Results", "race")
    quali_df = flatten(quali_rows, "QualifyingResults", "quali")
    meta = pd.DataFrame(list(races.values()))
    return meta, race_df, quali_df, errors

with st.sidebar:
    st.header("Filtros")
    st.caption("Os dados são carregados da API Jolpica F1.")
    if st.button("🔄 Atualizar dados da API", use_container_width=True):
        load_all.clear()
        st.rerun()

with st.spinner("Importando as temporadas 2021–2025 da base histórica..."):
    meta, race_df, quali_df, errors = load_all()

if errors:
    st.warning("Algumas temporadas não puderam ser importadas:\n\n" + "\n".join(errors))

if meta.empty or race_df.empty:
    st.error("Não foi possível carregar os dados. Verifique sua conexão e tente atualizar.")
    st.stop()

season = st.sidebar.selectbox("Temporada", SEASONS, index=4)
season_meta = meta[meta.season == season].sort_values("round")
season_race = race_df[race_df.season == season].copy()
season_quali = quali_df[quali_df.season == season].copy()

def numeric_position(series):
    return pd.to_numeric(series, errors="coerce")

winners = season_race[numeric_position(season_race.position) == 1]
champion_points = season_race.groupby(["driver", "team"], as_index=False).points.sum().sort_values("points", ascending=False)
team_points = season_race.groupby("team", as_index=False).points.sum().sort_values("points", ascending=False)
winner_name = champion_points.iloc[0]["driver"] if not champion_points.empty else "—"
team_champ = team_points.iloc[0]["team"] if not team_points.empty else "—"

st.subheader(f"Temporada {season}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Grandes Prêmios", len(season_meta))
c2.metric("Pilotos com resultados", season_race.driver.nunique())
c3.metric("Líder por pontos na base", winner_name)
c4.metric("Equipe líder por pontos", team_champ)
st.caption("Os líderes são calculados somando os pontos de corrida importados. A classificação oficial final será validada em uma etapa própria.")

tab1, tab2, tab3, tab4 = st.tabs(["🏁 Corridas", "📊 Campeonato", "🏎️ Pilotos", "🛠️ Equipes"])

with tab1:
    race_options = {
        f"{int(r.round):02d} · {r.race} — {r.date}": int(r.round)
        for r in season_meta.itertuples()
    }
    selected_label = st.selectbox("Escolha um Grande Prêmio", list(race_options.keys()))
    rnd = race_options[selected_label]
    race_info = season_meta[season_meta["round"] == rnd].iloc[0]
    st.markdown(f"### {race_info['race']}")
    st.caption(f"{race_info['circuit']} · {race_info['locality']}, {race_info['country']} · {race_info['date']}")
    r = season_race[season_race["round"] == rnd].copy()
    q = season_quali[season_quali["round"] == rnd].copy()
    winner = r[numeric_position(r.position) == 1]
    pole = q[numeric_position(q.position) == 1]
    fastest = r[r.fastest_lap_rank.astype(str) == "1"]
    a, b, c = st.columns(3)
    a.metric("Vencedor", winner.iloc[0]["driver"] if not winner.empty else "—")
    b.metric("Pole position", pole.iloc[0]["driver"] if not pole.empty else "—")
    c.metric("Volta mais rápida", fastest.iloc[0]["driver"] if not fastest.empty else "Não disponível")
    st.markdown("#### Classificação")
    if q.empty:
        st.info("Classificação não disponível nesta resposta da API.")
    else:
        st.dataframe(q.sort_values("position", key=numeric_position)[["position","driver","team","q1","q2","q3"]], hide_index=True, use_container_width=True)
    st.markdown("#### Resultado completo da corrida")
    if not r.empty:
        cols = ["position","driver","team","grid","laps","points","status","fastest_lap_rank","fastest_lap_time"]
        st.dataframe(r.sort_values("position", key=numeric_position)[cols], hide_index=True, use_container_width=True)
    else:
        st.info("Resultado de corrida não encontrado.")

with tab2:
    st.markdown("#### Campeonato de pilotos · pontos somados")
    driver_standings = season_race.groupby(["driver","team"], as_index=False).agg(points=("points","sum"), wins=("position", lambda x: (numeric_position(x)==1).sum()))
    driver_standings = driver_standings.sort_values(["points","wins"], ascending=False)
    driver_standings.insert(0, "posição", range(1, len(driver_standings)+1))
    st.dataframe(driver_standings, hide_index=True, use_container_width=True)
    st.markdown("#### Campeonato de construtores · pontos somados")
    st.dataframe(team_points, hide_index=True, use_container_width=True)
    fig = px.bar(driver_standings.head(10), x="driver", y="points", color="team", title="Top 10 pilotos por pontos")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    drivers = sorted(season_race.driver.dropna().unique())
    selected_driver = st.selectbox("Piloto", drivers)
    d = season_race[season_race.driver == selected_driver]
    wins = (numeric_position(d.position) == 1).sum()
    podiums = (numeric_position(d.position) <= 3).sum()
    x1, x2, x3, x4 = st.columns(4)
    x1.metric("Pontos", f"{d.points.sum():g}")
    x2.metric("Vitórias", int(wins))
    x3.metric("Pódios", int(podiums))
    x4.metric("GPs com resultado", len(d))
    st.dataframe(d.sort_values("round")[["round","driver","team","position","grid","points","status","fastest_lap_time"]], hide_index=True, use_container_width=True)

with tab4:
    st.markdown("#### Pontuação por equipe")
    st.dataframe(team_points, hide_index=True, use_container_width=True)
    fig2 = px.bar(team_points, x="team", y="points", title="Pontos por construtor")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.caption("Fonte de dados: Jolpica F1 API (compatível com Ergast). Dados sujeitos à disponibilidade e às regras de cobertura da API. Este painel é uma primeira versão de importação e exploração; validações de classificação oficial, desempates, penalidades e regras de pontuação serão refinadas.")
