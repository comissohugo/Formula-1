"""F1 Data Center - dashboard histórico (1980-2026, com 2026 em andamento).

Execute com:
    streamlit run app.py

O painel lê exclusivamente o banco local (data/f1.db). Para atualizar os dados,
use o botão na barra lateral ou rode `python -m f1dc.ingest` no terminal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from f1dc import config, data
from f1dc.export import build_export_zip
from f1dc.ingest import import_seasons
from f1dc.validate import save_report, validate

DB_PATH = Path(config.DB_PATH)
REPORT_PATH = Path(config.REPORT_PATH)

PERIOD_LABEL = f"{min(config.SEASONS)}-{max(config.SEASONS)}"
POINTS_ERA_NOTE = (
    "A pontuação mudou ao longo do período: até 2009 o vencedor ganhava 10 "
    "pontos; a partir de 2010, 25 pontos (com o Top 10 pontuando). Por isso, "
    "a soma de pontos não é comparável entre eras; vitórias, pódios e poles "
    "são melhores para comparações históricas. Exceções pontuais, como os "
    "pontos dobrados de Abu Dhabi em 2014, vêm da fonte oficial."
)
IN_PROGRESS_SEASONS = set(getattr(config, "IN_PROGRESS_SEASONS", set()))
IN_PROGRESS_CALENDAR_RACES = getattr(config, "IN_PROGRESS_CALENDAR_RACES", {})
CLINCHED_CHAMPIONS = getattr(config, "CLINCHED_CHAMPIONS", {})

st.set_page_config(page_title="F1 Data Center", page_icon="🏁", layout="wide")

# Em telas estreitas as abas e as tabelas largas precisam de rolagem lateral.
# O Streamlit esconde a barra por padrão; aqui ela volta a ficar visível.
st.markdown(
    """
    <style>
    [data-baseweb="tab-list"] {
        scrollbar-width: thin !important;
        scrollbar-color: #8a8a8a transparent !important;
    }
    [data-baseweb="tab-list"]::-webkit-scrollbar {
        height: 8px !important;
    }
    [data-baseweb="tab-list"]::-webkit-scrollbar-thumb {
        background: #8a8a8a !important;
        border-radius: 4px !important;
    }
    .dvn-scroller {
        scrollbar-width: thin !important;
        scrollbar-color: #8a8a8a transparent !important;
    }
    .dvn-scroller::-webkit-scrollbar {
        height: 10px !important;
        width: 10px !important;
    }
    .dvn-scroller::-webkit-scrollbar-thumb {
        background: #8a8a8a !important;
        border-radius: 5px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# carregamento
# --------------------------------------------------------------------------
def db_signature() -> float:
    return DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0


@st.cache_data(show_spinner=False)
def get_frames(signature: float) -> dict[str, pd.DataFrame]:
    return data.load_frames(DB_PATH)


@st.cache_data(show_spinner=False)
def get_report(signature: float) -> dict[str, Any] | None:
    if not REPORT_PATH.exists():
        return None
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def get_export_zip(signature: float) -> bytes:
    return build_export_zip(get_frames(signature), DB_PATH, REPORT_PATH)


def live_seasons() -> list[int]:
    """Temporadas que ainda podem receber etapas novas."""
    return sorted(config.IN_PROGRESS_SEASONS) or [max(config.SEASONS)]


def run_import(seasons: list[int] | None = None) -> None:
    seasons = seasons or live_seasons()
    label = ", ".join(str(s) for s in seasons)
    with st.status(f"Importando {label} da Jolpica F1 API...", expanded=True) as status:
        bar = st.progress(0.0, text="Iniciando...")

        def progress(fraction: float, message: str) -> None:
            bar.progress(min(max(fraction, 0.0), 1.0), text=message)

        try:
            result = import_seasons(seasons=seasons, progress=progress)
        except Exception as exc:  # noqa: BLE001 - mostrar erro ao usuário
            status.update(label="Falha na importação", state="error")
            st.exception(exc)
            return

        bar.progress(1.0, text="Importação concluída")
        if result["errors"]:
            status.update(
                label=f"Importação concluída com {len(result['errors'])} erro(s)",
                state="error",
            )
            for error in result["errors"]:
                st.write(f"- {error}")
        else:
            status.update(label="Importação concluída com sucesso", state="complete")

    st.cache_data.clear()
    st.rerun()


def fmt_points(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):g}"


def position_label(row: pd.Series) -> Any:
    text = str(row.get("position_text") or "").upper()
    labels = {"D": "DSQ", "E": "EXC", "W": "WD", "F": "DNQ", "N": "NC"}
    if text in labels:
        return labels[text]
    if pd.notna(row.get("position")):
        return int(row["position"])
    return text or "—"


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def frames_for_seasons(
    frames: dict[str, pd.DataFrame], start: int, end: int
) -> dict[str, pd.DataFrame]:
    """Filtra as tabelas que têm `season` para o intervalo [start, end].

    Tabelas de dimensão (pilotos, equipes, circuitos) não têm `season` e
    permanecem intactas: elas só são usadas para enriquecer os resultados.
    """
    return {
        name: (
            frame[(frame["season"] >= start) & (frame["season"] <= end)]
            if "season" in frame.columns
            else frame
        )
        for name, frame in frames.items()
    }


def render_century_winners(
    frames: dict[str, pd.DataFrame],
    label: str,
    slug: str,
    start: int,
    end: int,
    note: str,
    warning: str | None = None,
) -> None:
    """Mostra o top 10 de vencedores de um recorte de século."""
    st.markdown(f"##### {label}")
    if warning:
        st.warning(warning)
    subset = frames_for_seasons(frames, start, end)
    rankings = data.period_driver_rankings(subset)
    winners = data.period_top_winners(subset, limit=10)
    if winners.empty:
        st.info("Sem vitórias registradas neste recorte.")
        return
    info = rankings.set_index("driver_id")
    table = pd.DataFrame(
        {
            "Pos.": range(1, len(winners) + 1),
            "Piloto": winners["full_name"],
            "Títulos": winners["driver_id"].map(info["titles"]).astype(int),
            "Vitórias": winners["wins"].astype(int),
            "Corridas": winners["starts"].astype(int),
            "% vitórias": winners["win_pct"].map(
                lambda value: f"{value:.1f}".replace(".", ",") + "%"
            ),
            "Circuito onde mais venceu": [
                f"{row['favorite']} — {row['favorite_wins']}"
                + (" *" if row["tied"] else "")
                for _, row in winners.iterrows()
            ],
            "Equipe(s)": winners["driver_id"].map(info["teams"]).fillna("—"),
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")
    for _, row in winners[winners["tied"].map(bool)].iterrows():
        st.caption(
            f"\\* {row['full_name']}: empate com "
            f"{', '.join(row['tied'])} — {row['favorite_wins']} "
            "vitória(s) em cada circuito."
        )
    st.caption(note)
    st.download_button(
        f"Baixar top 10 — {label} (CSV)",
        csv_bytes(table),
        file_name=f"vencedores_{slug}.csv",
        mime="text/csv",
    )


def driver_comparison_frame(
    driver_name: str,
    driver_stats: dict[str, Any],
    other_name: str,
    other_stats: dict[str, Any],
    h2h: dict[str, Any],
) -> pd.DataFrame:
    """Tabela de comparação entre dois pilotos na temporada selecionada."""
    return pd.DataFrame(
        {
            "Métrica": [
                "Pontos",
                "Vitórias",
                "Pódios",
                "Poles",
                "Abandonos",
                "Classificação (H2H)",
                "Corrida (H2H)",
            ],
            driver_name: [
                fmt_points(driver_stats["points"]),
                driver_stats["wins"],
                driver_stats["podiums"],
                driver_stats["poles"],
                driver_stats["dnf"],
                f"{h2h['quali_a']} x {h2h['quali_b']}",
                f"{h2h['race_a']} x {h2h['race_b']}",
            ],
            other_name: [
                fmt_points(other_stats["points"]),
                other_stats["wins"],
                other_stats["podiums"],
                other_stats["poles"],
                other_stats["dnf"],
                "",
                "",
            ],
        }
    ).astype(str)


# --------------------------------------------------------------------------
# estado vazio (primeira execução)
# --------------------------------------------------------------------------
if not DB_PATH.exists():
    st.title("🏁 F1 DATA CENTER")
    st.caption(f"Base histórica interativa · Temporadas {PERIOD_LABEL}")
    st.info(
        "A base local ainda não foi criada. A importação baixa calendário, "
        f"resultados, classificações e sprints de {PERIOD_LABEL} "
        f"(temporadas encerradas e etapas já realizadas de 2026). Leva alguns minutos."
    )
    st.code("python -m f1dc.ingest", language="powershell")
    if st.button("Importar dados agora", type="primary"):
        run_import()
    st.stop()


signature = db_signature()
frames = get_frames(signature)
report = get_report(signature)

cons_names = dict(
    zip(frames["constructors"]["constructor_id"], frames["constructors"]["name"])
)


def team_label(constructor_ids: Any) -> str:
    if constructor_ids is None or pd.isna(constructor_ids):
        return "—"
    parts = [p.strip() for p in str(constructor_ids).split(",") if p.strip()]
    return " / ".join(cons_names.get(p, p) for p in parts) or "—"


def expected_total_for_loaded_seasons() -> int:
    """Total esperado considerando só as temporadas presentes no banco."""
    total = 0
    for _, row in frames["seasons"].iterrows():
        season_year = int(row["season"])
        actual = int(row["races_count"] or 0)
        if season_year in IN_PROGRESS_SEASONS:
            total += IN_PROGRESS_CALENDAR_RACES.get(season_year, actual)
        else:
            total += config.EXPECTED_RACES.get(season_year, actual)
    return total


# --------------------------------------------------------------------------
# barra lateral
# --------------------------------------------------------------------------
seasons = sorted(int(s) for s in frames["seasons"]["season"].dropna().unique())

with st.sidebar:
    st.header("Filtros")
    season = st.selectbox("Temporada", seasons, index=len(seasons) - 1)

    st.divider()
    st.subheader("Estado da base")
    runs = frames["import_runs"]
    if not runs.empty:
        ordered = runs.sort_values("id")
        finished = ordered[ordered["finished_at"].notna()]
        # ignora runs que ficaram sem data de fim (container reiniciado no meio)
        last_run = finished.iloc[-1] if not finished.empty else ordered.iloc[-1]
        status_labels = {
            "ok": "concluída",
            "running": "em andamento",
            "interrupted": "interrompida",
            "error": "com erro",
            "failed": "com erro",
        }
        when = last_run["finished_at"] or last_run["started_at"]
        st.caption(f"Última importação: {when}")
        st.caption(
            f"Status: {status_labels.get(last_run['status'], last_run['status'])}"
        )
    st.caption(
        f"GPs no banco: {len(frames['races'])} / {expected_total_for_loaded_seasons()}"
    )
    if report is not None:
        st.caption(
            "Validação: " + ("aprovada ✅" if report["ok"] else "com pendências ⚠️")
        )

    st.divider()
    live = live_seasons()
    live_label = ", ".join(str(s) for s in live)
    if st.button(f"🔄 Atualizar {live_label} da API", width="stretch"):
        run_import(live)
    st.caption(
        f"Reimporta só a temporada em andamento ({live_label}), sem duplicar "
        "registros. O histórico anterior não é alterado."
    )

# --------------------------------------------------------------------------
# cabeçalho
# --------------------------------------------------------------------------
summary = data.season_summary(frames, season)
champion_team = cons_names.get(summary.get("champion_constructor_id"), "—")
driver_champion = frames["drivers"].loc[
    frames["drivers"]["driver_id"] == summary.get("champion_driver_id"), "full_name"
]
driver_champion_name = driver_champion.iloc[0] if not driver_champion.empty else "—"

season_in_progress = season in IN_PROGRESS_SEASONS
leader_driver_name = "—"
leader_team_name = "—"
if season_in_progress:
    season_standings = frames["driver_standings"]
    season_standings = season_standings[season_standings["season"] == season]
    leader_row = season_standings[season_standings["position"] == 1]
    if not leader_row.empty:
        leader_driver_name = leader_row["full_name"].iloc[0]

    season_team_standings = frames["constructor_standings"]
    season_team_standings = season_team_standings[
        season_team_standings["season"] == season
    ]
    leader_team_row = season_team_standings[season_team_standings["position"] == 1]
    if not leader_team_row.empty:
        leader_team_name = leader_team_row["constructor_name"].iloc[0]

st.title("🏁 F1 DATA CENTER")
st.caption(
    f"Base histórica interativa · {PERIOD_LABEL} · fonte: Jolpica F1 API "
    "(estrutura Ergast) · dados locais em SQLite"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Temporada", season)
c2.metric("Grandes Prêmios", int(summary.get("races_count") or 0))
season_clinch = CLINCHED_CHAMPIONS.get(season, {}) if season_in_progress else {}
clinched_driver = season_clinch.get("driver")
clinched_constructor = season_clinch.get("constructor")
if season_in_progress:
    c3.metric(
        "Campeão de pilotos (matemático)"
        if clinched_driver
        else "Líder do campeonato",
        leader_driver_name,
    )
    c4.metric(
        "Campeão de construtores (matemático)"
        if clinched_constructor
        else "Líder de construtores",
        leader_team_name,
    )
else:
    c3.metric("Campeão de pilotos", driver_champion_name)
    c4.metric("Campeão de construtores", champion_team)

if season_in_progress:
    calendar_races = IN_PROGRESS_CALENDAR_RACES.get(season)
    total_label = (
        f" de {calendar_races}" if calendar_races else ""
    )
    clinch_parts = []
    if clinched_driver:
        clinch_parts.append("O título de pilotos já está garantido matematicamente.")
    if clinched_constructor:
        clinch_parts.append(
            "O título de construtores também está garantido matematicamente."
        )
    if clinch_parts:
        closing = (
            " ".join(clinch_parts)
            + " A temporada continua em andamento; a classificação exibida é a "
            "posição atual, não a final."
        )
    else:
        closing = (
            "A classificação exibida é a posição atual, não o resultado final; "
            "nenhum campeão é declarado antes do encerramento."
        )
    st.caption(
        f"Temporada em andamento: {int(summary.get('races_count') or 0)}"
        f"{total_label} GPs concluídos. {closing}"
    )

races = data.season_races(frames, season)
race_results = frames["race_results"]
season_results = race_results[race_results["season"] == season].copy()
qualifying = frames["qualifying_results"]
season_quali = qualifying[qualifying["season"] == season].copy()
sprints = frames["sprint_results"]
season_sprints = sprints[sprints["season"] == season].copy()
driver_extras = data.season_driver_extras(frames, season)
team_extras = data.season_constructor_extras(frames, season)
season_awards = data.season_awards(frames, season)

tab_races, tab_champ, tab_drivers, tab_teams, tab_history, tab_ranking, tab_quality = st.tabs(
    [
        "🏁 Corridas",
        "📊 Campeonato",
        "🏎️ Pilotos",
        "🛠️ Equipes",
        "🏆 Histórico",
        "🥇 Ranking",
        "✅ Qualidade dos dados",
    ]
)

# --------------------------------------------------------------------------
# aba corridas
# --------------------------------------------------------------------------
with tab_races:
    labels = {
        f"{int(row['round']):02d} · {row['race_name']} — {row['date']}": int(row["round"])
        for _, row in races.iterrows()
    }
    selected = st.selectbox("Escolha um Grande Prêmio", list(labels.keys()))
    round_ = labels[selected]
    race = races[races["round"] == round_].iloc[0]

    st.markdown(f"### {race['race_name']}")
    sprint_badge = " · 🏃 com Sprint" if int(race.get("has_sprint") or 0) else ""
    st.caption(
        f"{race.get('circuit_name', '—')} · {race.get('circuit_locality', '—')}, "
        f"{race.get('circuit_country', '—')} · {race['date']}{sprint_badge}"
    )

    result = season_results[season_results["round"] == round_].copy()
    quali = season_quali[season_quali["round"] == round_].copy()
    sprint = season_sprints[season_sprints["round"] == round_].copy()

    winner = result[result["position"] == 1]
    gp_awards = season_awards[season_awards["round"] == round_]
    pole_event = gp_awards[gp_awards["award"] == "pole"]
    fastest_event = gp_awards[gp_awards["award"] == "fastest_lap"]
    grid_first = result[result["grid"] == 1]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vencedor", winner["full_name"].iloc[0] if not winner.empty else "—")
    m2.metric(
        "Pole position",
        pole_event["full_name"].iloc[0] if not pole_event.empty else "—",
    )
    m3.metric(
        "Volta mais rápida",
        fastest_event["full_name"].iloc[0]
        if not fastest_event.empty
        else "Não disponível",
    )
    m4.metric("P1 do grid efetivo", grid_first["full_name"].iloc[0] if not grid_first.empty else "—")
    st.caption(
        "Pole position é o P1 da classificação oficial. O grid efetivo pode mudar "
        "por penalidades e é exibido separadamente, sem inferir punições."
    )
    complementary = gp_awards[
        gp_awards["source"].astype(str).str.startswith("Wikipédia")
    ]
    if not complementary.empty:
        urls = sorted(complementary["source_url"].dropna().unique())
        st.caption(
            "Pole e/ou volta mais rápida deste GP foram complementadas pela "
            "Wikipédia (pt/en), porque a fonte primária não as fornece. Fonte: "
            + "; ".join(urls)
        )

    if not result.empty and not quali.empty:
        sem_resultado = quali[~quali["driver_id"].isin(result["driver_id"])]
        if not sem_resultado.empty:
            nomes = ", ".join(sem_resultado["full_name"].fillna(sem_resultado["driver_id"]))
            st.warning(
                "Classificado(s) que não constam no resultado da corrida na fonte "
                f"(DNS/ausência): {nomes}. Nenhuma posição foi inventada."
            )

    st.markdown("#### Classificação (qualifying)")
    if quali.empty:
        if not pole_event.empty:
            st.info(
                "Classificação completa não disponível para este GP na fonte "
                "primária. A pole position está identificada pela fonte "
                "complementar: "
                f"{pole_event['full_name'].iloc[0]}."
            )
        else:
            st.info("Classificação não disponível para este GP.")
    else:
        q = quali.sort_values("position").copy()
        if q["q2"].notna().any() or q["q3"].notna().any():
            time_columns = {
                "Q1": q["q1"].fillna("—"),
                "Q2": q["q2"].fillna("—"),
                "Q3": q["q3"].fillna("—"),
            }
        else:
            # Sessão única (1990–2002): o tempo é o melhor da classificação,
            # não uma etapa Q1 de formato eliminatório.
            time_columns = {"Tempo": q["q1"].fillna("—")}
        q_table = pd.DataFrame(
            {
                "Pos.": q["position"].astype("Int64"),
                "Piloto": q["full_name"],
                "Equipe": q["constructor_name"],
                **time_columns,
            }
        )
        if (
            q["source_url"].fillna("").astype(str).str.contains("wikipedia.org").any()
        ):
            wiki_urls = sorted(q["source_url"].dropna().unique())
            st.caption(
                "Classificação complementada pela Wikipédia (en), porque a fonte "
                "primária não traz o qualifying deste GP. Fonte: "
                + "; ".join(wiki_urls)
            )
        st.dataframe(q_table, hide_index=True, width="stretch")
        st.download_button(
            "Baixar classificação (CSV)",
            csv_bytes(q_table),
            file_name=f"classificacao_{season}_{round_:02d}.csv",
            mime="text/csv",
        )

    st.markdown("#### Resultado completo da corrida")
    if result.empty:
        st.info("Resultado de corrida não disponível para este GP.")
    else:
        r = result.sort_values(["position_order", "position"], na_position="last").copy()
        r["Pos."] = r.apply(position_label, axis=1)

        def fastest_lap_label(row: pd.Series) -> str:
            lap_time = row.get("fastest_lap_time")
            if lap_time is not None and not pd.isna(lap_time):
                if row.get("fastest_lap_rank") == 1:
                    return f"⚡ {lap_time}"
                return str(lap_time)
            if (
                not fastest_event.empty
                and row.get("driver_id") == fastest_event["driver_id"].iloc[0]
            ):
                return "⚡ (tempo não disponível na fonte)"
            return "—"

        r["Volta rápida"] = r.apply(fastest_lap_label, axis=1)
        race_table = pd.DataFrame(
            {
                "Pos.": r["Pos."].astype(str),
                "Piloto": r["full_name"],
                "Equipe": r["constructor_name"],
                "Nº": r["number"],
                "Grid": r["grid"].astype("Int64"),
                "Voltas": r["laps"].astype("Int64"),
                "Pontos": r["points"].fillna(0).map(fmt_points),
                "Tempo/Intervalo": r["time_text"].fillna("—"),
                "Status": r["status"].fillna("—"),
                "Volta rápida": r["Volta rápida"],
            }
        )
        st.dataframe(race_table, hide_index=True, width="stretch")
        st.download_button(
            "Baixar resultado (CSV)",
            csv_bytes(race_table),
            file_name=f"corrida_{season}_{round_:02d}.csv",
            mime="text/csv",
        )

    if not sprint.empty:
        st.markdown("#### Sprint (sessão separada)")
        s = sprint.sort_values(["position_order", "position"], na_position="last").copy()
        s["Pos."] = s.apply(position_label, axis=1)
        sprint_table = pd.DataFrame(
            {
                "Pos.": s["Pos."].astype(str),
                "Piloto": s["full_name"],
                "Equipe": s["constructor_name"],
                "Grid": s["grid"].astype("Int64"),
                "Voltas": s["laps"].astype("Int64"),
                "Pontos": s["points"].fillna(0).map(fmt_points),
                "Tempo/Intervalo": s["time_text"].fillna("—"),
                "Status": s["status"].fillna("—"),
            }
        )
        st.dataframe(sprint_table, hide_index=True, width="stretch")
    elif int(race.get("has_sprint") or 0):
        st.warning("Este GP tem sprint no calendário, mas os resultados não foram encontrados.")

# --------------------------------------------------------------------------
# aba campeonato
# --------------------------------------------------------------------------
with tab_champ:
    standings = frames["driver_standings"]
    standings = standings[standings["season"] == season].sort_values("position")
    team_standings = frames["constructor_standings"]
    team_standings = team_standings[team_standings["season"] == season].sort_values("position")

    standings_title = (
        "Classificação oficial de pilotos (atual)"
        if season_in_progress
        else "Classificação oficial final de pilotos"
    )
    st.markdown(f"#### {standings_title}")
    if standings.empty:
        st.info("Classificação de pilotos não disponível.")
    else:
        st_table = pd.DataFrame(
            {
                "Pos.": standings["position"].astype("Int64"),
                "Piloto": standings["full_name"],
                "Equipe": standings["constructor_ids"].map(team_label),
                "Pontos": standings["points"].map(fmt_points),
                "Vitórias": standings["wins"].astype("Int64"),
                "Pódios": standings["driver_id"]
                .map(driver_extras["podiums"])
                .fillna(0)
                .astype(int),
                "Poles": standings["driver_id"]
                .map(driver_extras["poles"])
                .fillna(0)
                .astype(int),
            }
        )
        st.dataframe(st_table, hide_index=True, width="stretch")
        st.caption(
            "Pódios e poles são calculados dos resultados oficiais da temporada "
            "(corridas principais). Pole = P1 do qualifying; sprint não entra."
        )
        if season_awards["source"].astype(str).str.startswith("Wikipédia").any():
            st.caption(
                "Nesta temporada, a fonte primária não fornece pole e/ou volta "
                "mais rápida em todos os GPs; os dados faltantes foram "
                "complementados pela Wikipédia (pt/en), com fonte e data "
                "registradas na base."
            )
        st.caption(POINTS_ERA_NOTE)

    constructors_title = (
        "Classificação oficial de construtores (atual)"
        if season_in_progress
        else "Classificação oficial final de construtores"
    )
    st.markdown(f"#### {constructors_title}")
    if team_standings.empty:
        st.info("Classificação de construtores não disponível.")
    else:
        c_table = pd.DataFrame(
            {
                "Pos.": team_standings["position"].astype("Int64"),
                "Equipe": team_standings["constructor_name"],
                "Pontos": team_standings["points"].map(fmt_points),
                "Vitórias": team_standings["wins"].astype("Int64"),
                "Pódios": team_standings["constructor_id"]
                .map(team_extras["podiums"])
                .fillna(0)
                .astype(int),
                "Poles": team_standings["constructor_id"]
                .map(team_extras["poles"])
                .fillna(0)
                .astype(int),
            }
        )
        st.dataframe(c_table, hide_index=True, width="stretch")
        if team_standings["position"].isna().any():
            st.caption(
                "Equipe(s) com posição vazia foram excluídas do campeonato pela "
                "fonte oficial; os pontos aparecem como 0."
            )

    st.markdown("#### Evolução de pontos por etapa")
    st.caption(
        "Pontos acumulados somando corrida + sprint a cada rodada, a partir dos "
        "resultados oficiais. A classificação final acima é a fonte oficial."
    )
    cumulative = data.cumulative_points(frames, season)
    top_drivers = standings.head(10)["driver_id"].tolist()
    if not cumulative.empty and top_drivers:
        chart = cumulative[cumulative["driver_id"].isin(top_drivers)]
        fig = px.line(
            chart,
            x="round",
            y="points",
            color="full_name",
            markers=True,
            labels={"round": "Rodada", "points": "Pontos", "full_name": "Piloto"},
        )
        fig.update_layout(legend_title_text="", height=460)
        st.plotly_chart(fig, width="stretch")

    if not standings.empty:
        bar = standings.head(10).copy()
        bar["Equipe"] = bar["constructor_ids"].map(team_label)
        fig2 = px.bar(
            bar,
            x="full_name",
            y="points",
            color="Equipe",
            labels={"full_name": "Piloto", "points": "Pontos"},
            title="Top 10 pilotos por pontos",
        )
        fig2.update_layout(showlegend=False, height=420)
        st.plotly_chart(fig2, width="stretch")

# --------------------------------------------------------------------------
# aba pilotos
# --------------------------------------------------------------------------
with tab_drivers:
    driver_options: dict[str, str] = {}
    if not standings.empty:
        for _, row in standings.iterrows():
            driver_options[f"{row['full_name']} ({team_label(row['constructor_ids'])})"] = row["driver_id"]
    else:
        for _, row in season_results[["driver_id", "full_name"]].drop_duplicates().iterrows():
            driver_options[row["full_name"]] = row["driver_id"]

    if not driver_options:
        st.info("Sem dados de pilotos para esta temporada.")
    else:
        driver_label = st.selectbox("Piloto", list(driver_options.keys()))
        driver_id = driver_options[driver_label]
        stats = data.driver_season_stats(frames, season, driver_id)

        x1, x2, x3, x4, x5 = st.columns(5)
        x1.metric(
            "Posição atual" if season_in_progress else "Posição final",
            stats["official_position"] or "—",
        )
        x2.metric("Pontos", fmt_points(stats["points"]))
        x3.metric("Vitórias", stats["wins"])
        x4.metric("Pódios", stats["podiums"])
        x5.metric("Poles", stats["poles"])

        y1, y2, y3, y4, y5 = st.columns(5)
        y1.metric("Voltas mais rápidas", stats["fastest_laps"])
        y2.metric("Largadas", stats["starts"])
        y3.metric("Abandonos", stats["dnf"])
        y4.metric("Desclassificações", stats["dsq"])
        y5.metric(
            "Grid médio",
            f"{stats['avg_grid']:.1f}" if stats["avg_grid"] is not None else "—",
        )

        st.markdown("#### Resultados por etapa")
        d = season_results[season_results["driver_id"] == driver_id].copy()
        q = season_quali[season_quali["driver_id"] == driver_id][["round", "position"]].rename(
            columns={"position": "quali_position"}
        )
        d = d.merge(q, on="round", how="left")
        d = d.merge(
            races[["round", "race_name", "date"]], on="round", how="left"
        ).sort_values("round")
        d["Pos."] = d.apply(position_label, axis=1)
        fastest_rounds = (
            season_awards[season_awards["award"] == "fastest_lap"]
            .set_index("round")["driver_id"]
        )
        d["volta_rapida"] = d.apply(
            lambda row: (
                row["fastest_lap_time"]
                if pd.notna(row["fastest_lap_time"])
                else (
                    "⚡ (tempo não disponível na fonte)"
                    if fastest_rounds.get(row["round"]) == driver_id
                    else "—"
                )
            ),
            axis=1,
        )
        driver_table = pd.DataFrame(
            {
                "Rodada": d["round"].astype("Int64"),
                "GP": d["race_name"],
                "Equipe": d["constructor_name"],
                "Classificação": d["quali_position"].astype("Int64"),
                "Grid": d["grid"].astype("Int64"),
                "Chegada": d["Pos."].astype(str),
                "Pontos": d["points"].fillna(0).map(fmt_points),
                "Status": d["status"].fillna("—"),
                "Volta rápida": d["volta_rapida"],
            }
        )
        st.dataframe(driver_table, hide_index=True, width="stretch")

        driver_name = frames["drivers"].loc[
            frames["drivers"]["driver_id"] == driver_id, "full_name"
        ].iloc[0]

        st.markdown(f"#### Onde ele mais venceu (carreira {PERIOD_LABEL})")
        career = data.driver_circuit_stats(frames, driver_id)
        favorite = data.favorite_circuit(frames, driver_id)
        if favorite is None:
            st.info(f"Sem vitórias no período carregado ({PERIOD_LABEL}).")
        else:
            wins_only = career[career["wins"] > 0].reset_index(drop=True)
            tied_count = len(favorite["others"]) + 1
            f1, f2, f3 = st.columns(3)
            if favorite["others"]:
                f1.metric("Circuito onde mais venceu", f"{tied_count} empatados")
                f2.metric("Vitórias em cada", favorite["wins"])
            else:
                f1.metric("Circuito onde mais venceu", favorite["label"])
                f2.metric("Vitórias nesse circuito", favorite["wins"])
            f3.metric("Circuitos com vitória", len(wins_only))

            career_table = pd.DataFrame(
                {
                    "Circuito": wins_only["circuit_name"],
                    "País": wins_only["circuit_country"].fillna("—"),
                    "Vitórias": wins_only["wins"].astype(int),
                    "Corridas": wins_only["starts"].astype(int),
                    "% vitórias": wins_only["win_pct"].map(
                        lambda value: f"{value:.1f}".replace(".", ",") + "%"
                    ),
                }
            )
            with st.expander(
                f"Ver vitórias por circuito ({len(wins_only)})", expanded=False
            ):
                st.dataframe(career_table, hide_index=True, width="stretch")
            if favorite["others"]:
                names = [favorite["label"], *favorite["others"]]
                shown = ", ".join(names[:3])
                if len(names) > 3:
                    shown += f" e mais {len(names) - 3}"
                st.caption(
                    f"Empate: {shown} — {favorite['wins']} vitória(s) em cada "
                    "(detalhe completo na tabela acima)."
                )
            st.caption(
                "Contagem por circuito (não por nome de GP), considerando apenas "
                "corridas principais e pilotos classificados. Circuitos com o mesmo "
                "número de vitórias aparecem listados como empate."
            )

        mates = data.teammate_ids(frames, season, driver_id)
        if mates:
            st.markdown("#### Comparação com companheiro(s) de equipe")
            for mate in mates:
                mate_stats = data.driver_season_stats(frames, season, mate)
                mate_name = frames["drivers"].loc[
                    frames["drivers"]["driver_id"] == mate, "full_name"
                ].iloc[0]
                h2h = data.head_to_head(frames, season, driver_id, mate)
                if len(mates) > 1:
                    st.markdown(f"**{mate_name}**")
                st.dataframe(
                    driver_comparison_frame(
                        driver_name, stats, mate_name, mate_stats, h2h
                    ),
                    hide_index=True,
                    width="stretch",
                )
            st.caption(
                "H2H: GPs em que ambos têm dado, contando quem ficou à frente. "
                "Nas corridas, só entram GPs em que ambos foram classificados."
            )

            chart_ids = [driver_id, *mates]
            cum = data.cumulative_points(frames, season)
            cum = cum[cum["driver_id"].isin(chart_ids)]
            if not cum.empty:
                fig3 = px.line(
                    cum,
                    x="round",
                    y="points",
                    color="full_name",
                    markers=True,
                    title="Pontos acumulados: piloto x companheiro(s)",
                    labels={"round": "Rodada", "points": "Pontos", "full_name": "Piloto"},
                )
                fig3.update_layout(height=400)
                st.plotly_chart(fig3, width="stretch")

        st.markdown("#### Comparar com outro piloto (qualquer equipe)")
        others = (
            season_results[season_results["driver_id"] != driver_id]
            .drop_duplicates("driver_id")
            .sort_values("full_name")
        )
        other_options = {
            f"{row['full_name']} ({row['constructor_name']})": row["driver_id"]
            for _, row in others.iterrows()
        }
        if not other_options:
            st.info("Sem outro piloto nesta temporada para comparar.")
        else:
            compare_label = st.selectbox(
                "Comparar com", list(other_options), key="compare_driver"
            )
            compare_id = other_options[compare_label]
            compare_stats = data.driver_season_stats(frames, season, compare_id)
            compare_name = frames["drivers"].loc[
                frames["drivers"]["driver_id"] == compare_id, "full_name"
            ].iloc[0]
            compare_h2h = data.head_to_head(frames, season, driver_id, compare_id)
            compare_table = driver_comparison_frame(
                driver_name, stats, compare_name, compare_stats, compare_h2h
            )
            st.dataframe(compare_table, hide_index=True, width="stretch")
            st.caption(
                "Comparação livre: vale qualquer piloto da temporada, de qualquer "
                "equipe. H2H conta apenas GPs em que ambos têm dado; nas corridas, "
                "só GPs em que ambos foram classificados."
            )

            cum_compare = data.cumulative_points(frames, season)
            cum_compare = cum_compare[
                cum_compare["driver_id"].isin([driver_id, compare_id])
            ]
            if not cum_compare.empty:
                fig_cmp = px.line(
                    cum_compare,
                    x="round",
                    y="points",
                    color="full_name",
                    markers=True,
                    title=f"Pontos acumulados: {driver_name} x {compare_name}",
                    labels={"round": "Rodada", "points": "Pontos", "full_name": "Piloto"},
                )
                fig_cmp.update_layout(height=400, legend_title_text="")
                st.plotly_chart(fig_cmp, width="stretch")

            st.download_button(
                "Baixar comparação (CSV)",
                csv_bytes(compare_table),
                file_name=f"comparacao_{season}_{driver_id}_{compare_id}.csv",
                mime="text/csv",
            )

        st.download_button(
            "Baixar resultados do piloto (CSV)",
            csv_bytes(driver_table),
            file_name=f"piloto_{season}_{driver_id}.csv",
            mime="text/csv",
        )

# --------------------------------------------------------------------------
# aba equipes
# --------------------------------------------------------------------------
with tab_teams:
    team_standings = frames["constructor_standings"]
    team_standings = team_standings[team_standings["season"] == season].sort_values("position")
    team_options = {
        row["constructor_name"]: row["constructor_id"] for _, row in team_standings.iterrows()
    }
    if not team_options:
        team_options = {
            row["constructor_name"]: row["constructor_id"]
            for _, row in season_results[["constructor_id", "constructor_name"]]
            .drop_duplicates()
            .iterrows()
        }

    if not team_options:
        st.info("Sem dados de equipes para esta temporada.")
    else:
        team_label_selected = st.selectbox("Equipe", list(team_options.keys()))
        constructor_id = team_options[team_label_selected]

        team_row = team_standings[team_standings["constructor_id"] == constructor_id]
        team_results = season_results[season_results["constructor_id"] == constructor_id].copy()
        team_classified = team_results[data.classified_mask(team_results)]

        team_position = team_row["position"].iloc[0] if not team_row.empty else None
        z1, z2, z3, z4 = st.columns(4)
        z1.metric(
            "Posição no campeonato",
            int(team_position) if pd.notna(team_position) else "—",
        )
        z2.metric(
            "Pontos",
            fmt_points(team_row["points"].iloc[0]) if not team_row.empty else fmt_points(team_results["points"].sum()),
        )
        z3.metric("Vitórias", int((team_classified["position"] == 1).sum()))
        z4.metric("Pódios", int((team_classified["position"] <= 3).sum()))
        if not team_row.empty and pd.isna(team_position):
            st.caption(
                "Equipe sem posição oficial: foi excluída do campeonato pela fonte."
            )

        st.markdown("#### Pilotos da equipe na temporada")
        drivers_table = (
            team_results.groupby(["driver_id", "full_name"], as_index=False)
            .agg(
                corridas=("round", "count"),
                pontos=("points", "sum"),
                abandonos=("position_text", lambda s: (s.astype(str).str.upper() == "R").sum()),
            )
            .sort_values("pontos", ascending=False)
        )
        drivers_table["pontos"] = drivers_table["pontos"].map(fmt_points)
        drivers_table = drivers_table.rename(
            columns={"full_name": "Piloto", "corridas": "Corridas", "pontos": "Pontos", "abandonos": "Abandonos"}
        )
        st.dataframe(drivers_table, hide_index=True, width="stretch")

        st.markdown("#### Resultados por GP")
        t = team_results.sort_values(["round", "position_order"], na_position="last").copy()
        t["Pos."] = t.apply(position_label, axis=1)
        t = t.merge(races[["round", "race_name"]], on="round", how="left")
        team_table = pd.DataFrame(
            {
                "Rodada": t["round"].astype("Int64"),
                "GP": t["race_name"],
                "Piloto": t["full_name"],
                "Grid": t["grid"].astype("Int64"),
                "Chegada": t["Pos."].astype(str),
                "Pontos": t["points"].fillna(0).map(fmt_points),
                "Status": t["status"].fillna("—"),
            }
        )
        st.dataframe(team_table, hide_index=True, width="stretch")

        st.markdown("#### Evolução de pontos da equipe")
        team_cum = data.cumulative_constructor_points(frames, season)
        if not team_cum.empty:
            fig4 = px.line(
                team_cum,
                x="round",
                y="points",
                color="constructor_name",
                markers=True,
                labels={"round": "Rodada", "points": "Pontos", "constructor_name": "Equipe"},
            )
            fig4.update_layout(height=430, legend_title_text="")
            st.plotly_chart(fig4, width="stretch")

        st.download_button(
            "Baixar resultados da equipe (CSV)",
            csv_bytes(team_table),
            file_name=f"equipe_{season}_{constructor_id}.csv",
            mime="text/csv",
        )

# --------------------------------------------------------------------------
# aba historico (periodo completo)
# --------------------------------------------------------------------------
with tab_history:
    st.caption(
        f"Comparações de todo o período carregado ({PERIOD_LABEL}), independentes do "
        "filtro de temporada. Corridas e sprints entram separadas nos cálculos."
    )

    # campeoes ---------------------------------------------------------
    champions = data.champions_timeline(frames)
    if not champions.empty:
        st.markdown("#### Campeões do período")
        champ_table = pd.DataFrame(
            {
                "Temporada": champions["season"].astype(int),
                "Status": champions["status"].map(
                    lambda status: (
                        "Encerrada"
                        if status == "encerrada"
                        else "Matemático (em andamento)"
                    )
                ),
                "Campeão (pilotos)": champions["full_name"],
                "Pontos": champions["driver_points"].map(fmt_points),
                "Vitórias": champions["wins"].astype(int),
                "Equipe campeã": champions["constructor_name"],
                "Pontos da equipe": champions["team_points"].map(fmt_points),
            }
        )
        st.dataframe(champ_table, hide_index=True, width="stretch")
        if (champions["status"] != "encerrada").any():
            st.caption(
                "Temporadas em andamento aparecem com o título matemático; elas só "
                "passam a ser tratadas como encerradas depois da última etapa."
            )
        st.caption(
            "A coluna 'Equipe campeã' é o campeonato de construtores e pode ser "
            "diferente da equipe do campeão de pilotos (ex.: 2008, Hamilton pela "
            "McLaren e Ferrari campeã de construtores)."
        )

        fig_champ = px.bar(
            champions,
            x="season",
            y="driver_points",
            color="full_name",
            text="driver_points",
            labels={
                "season": "Temporada",
                "driver_points": "Pontos do campeão",
                "full_name": "Piloto",
            },
        )
        fig_champ.update_layout(height=340, showlegend=False)
        fig_champ.update_xaxes(type="category")
        st.plotly_chart(fig_champ, width="stretch")

    # ranking do periodo ----------------------------------------------
    rankings = data.period_driver_rankings(frames)
    if not rankings.empty:
        st.markdown("#### Ranking acumulado do período")
        metric_labels = {
            "points": "Pontos",
            "wins": "Vitórias",
            "podiums": "Pódios",
            "poles": "Poles",
            "fastest_laps": "Voltas mais rápidas",
            "starts": "Largadas",
        }
        metric = st.selectbox(
            "Ordenar ranking por",
            list(metric_labels),
            format_func=lambda key: metric_labels[key],
            key="period_metric",
        )
        max_top = max(5, min(30, len(rankings)))
        top_n = st.slider("Quantos pilotos exibir", 5, max_top, min(10, max_top))

        rank = rankings.sort_values([metric, "points"], ascending=False).head(top_n)
        fig_rank = px.bar(
            rank.iloc[::-1],
            x=metric,
            y="full_name",
            orientation="h",
            text=metric,
            labels={metric: metric_labels[metric], "full_name": "Piloto"},
        )
        fig_rank.update_layout(height=max(320, 26 * len(rank)), showlegend=False)
        st.plotly_chart(fig_rank, width="stretch")

        rank_table = pd.DataFrame(
            {
                "Piloto": rank["full_name"],
                "Temporadas": rank["seasons"].astype(int),
                "Largadas": rank["starts"].astype(int),
                "Pontos": rank["points"].map(fmt_points),
                "Vitórias": rank["wins"].astype(int),
                "Pódios": rank["podiums"].astype(int),
                "Poles": rank["poles"].astype(int),
                "Voltas rápidas": rank["fastest_laps"].astype(int),
                "Abandonos": rank["dnf"].astype(int),
                "Desclassificações": rank["dsq"].astype(int),
            }
        )
        st.dataframe(rank_table, hide_index=True, width="stretch")
        st.caption(
            "Pontos somam corridas + sprints. Vitórias e pódios ignoram "
            "desclassificados; abandonos usam o status textual da fonte. "
            + POINTS_ERA_NOTE
        )
        st.download_button(
            "Baixar ranking do período (CSV)",
            csv_bytes(rank_table),
            file_name=f"ranking_periodo_{PERIOD_LABEL.replace('-', '_')}.csv",
            mime="text/csv",
        )

        # duelo entre pilotos ----------------------------------------
        st.markdown("#### Duelo entre pilotos no período")
        driver_options_period = {
            row["full_name"]: row["driver_id"]
            for _, row in rankings.sort_values("full_name").iterrows()
        }
        duel_names = list(driver_options_period)
        col_a, col_b = st.columns(2)
        name_a = col_a.selectbox("Piloto A", duel_names, key="duel_a")
        default_b = 1 if len(duel_names) > 1 else 0
        name_b = col_b.selectbox(
            "Piloto B", duel_names, index=default_b, key="duel_b"
        )

        if name_a == name_b:
            st.info("Escolha dois pilotos diferentes para ver o confronto.")
        else:
            id_a = driver_options_period[name_a]
            id_b = driver_options_period[name_b]
            h2h = data.period_head_to_head(frames, id_a, id_b)

            d1, d2, d3, d4 = st.columns(4)
            d1.metric(
                "Classificação (H2H)",
                f"{h2h['quali_a']} x {h2h['quali_b']}",
                help=f"{h2h['quali_rounds']} GPs em que ambos têm classificação.",
            )
            d2.metric(
                "Corrida (H2H)",
                f"{h2h['race_a']} x {h2h['race_b']}",
                help=f"{h2h['race_rounds']} GPs em que ambos foram classificados.",
            )
            points_table = data.points_by_season(frames, [id_a, id_b])
            totals = points_table.drop(columns="season").sum()
            d3.metric(f"Pontos · {name_a}", fmt_points(totals.get(name_a, 0)))
            d4.metric(f"Pontos · {name_b}", fmt_points(totals.get(name_b, 0)))

            points_long = points_table.melt(
                id_vars="season", var_name="Piloto", value_name="Pontos"
            )
            fig_duel = px.bar(
                points_long,
                x="season",
                y="Pontos",
                color="Piloto",
                barmode="group",
                text="Pontos",
                labels={"season": "Temporada"},
            )
            fig_duel.update_layout(height=360, legend_title_text="")
            fig_duel.update_xaxes(type="category")
            st.plotly_chart(fig_duel, width="stretch")
            st.caption(
                "H2H conta apenas GPs em que os dois têm dado. Nas corridas, "
                "desclassificados ficam de fora. Pontos por temporada somam "
                "corridas + sprints."
            )

    # por circuito ----------------------------------------------------
    st.markdown("#### Por circuito")
    circuits = (
        frames["races"][["circuit_id", "circuit_name", "circuit_country"]]
        .drop_duplicates("circuit_id")
        .sort_values("circuit_name")
    )
    if circuits.empty:
        st.info("Sem circuitos cadastrados.")
    else:
        circuit_options = {
            f"{row['circuit_name']} · {row['circuit_country']}": row["circuit_id"]
            for _, row in circuits.iterrows()
        }
        circuit_label = st.selectbox("Circuito", list(circuit_options))
        editions = data.circuit_editions(frames, circuit_options[circuit_label])

        if editions.empty:
            st.info("Nenhuma edição encontrada para este circuito.")
        else:
            editions_table = pd.DataFrame(
                {
                    "Temporada": editions["season"].astype(int),
                    "GP": editions["race_name"],
                    "Data": editions["date"],
                    "Vencedor": editions["winner"].fillna("—"),
                    "Equipe": editions["winner_team"].fillna("—"),
                    "Pole position": editions["pole"].fillna("—"),
                    "Volta mais rápida": editions["fastest_lap"].fillna("—"),
                }
            )
            st.dataframe(editions_table, hide_index=True, width="stretch")

            st.markdown("#### Top 5 que mais venceram neste circuito")
            circuit_winners = data.circuit_top_winners(
                frames, circuit_options[circuit_label], limit=5
            )
            if circuit_winners.empty:
                st.info("Nenhuma vitória registrada neste circuito.")
            else:
                circuit_table = pd.DataFrame(
                    {
                        "Pos.": range(1, len(circuit_winners) + 1),
                        "Piloto": circuit_winners["full_name"],
                        "Vitórias": circuit_winners["wins"].astype(int),
                        "Corridas": circuit_winners["starts"].astype(int),
                        "% vitórias": circuit_winners["win_pct"].map(
                            lambda value: f"{value:.1f}".replace(".", ",") + "%"
                        ),
                    }
                )
                st.dataframe(circuit_table, hide_index=True, width="stretch")
                st.caption(
                    "Vitórias por piloto no traçado selecionado; corridas incluem "
                    "todas as largadas no circuito."
                )

            wins = editions["winner"].dropna().value_counts().rename_axis("Piloto").reset_index(name="Vitórias")
            if not wins.empty:
                fig_circuit = px.bar(
                    wins,
                    x="Vitórias",
                    y="Piloto",
                    orientation="h",
                    text="Vitórias",
                    title=f"Vitórias em {circuits.loc[circuits['circuit_id'] == circuit_options[circuit_label], 'circuit_name'].iloc[0]}",
                )
                fig_circuit.update_layout(height=max(280, 40 * len(wins)), showlegend=False)
                st.plotly_chart(fig_circuit, width="stretch")

            st.download_button(
                "Baixar edições do circuito (CSV)",
                csv_bytes(editions_table),
                file_name=f"circuito_{circuit_options[circuit_label]}.csv",
                mime="text/csv",
            )

    # circuitos fora do calendario atual -------------------------------
    st.markdown("#### Circuitos fora do calendário atual")
    reference_season = int(frames["races"]["season"].max())
    season_running = reference_season in IN_PROGRESS_SEASONS
    outside = data.inactive_circuits(
        frames,
        reference_season=reference_season,
        min_seasons_absent=2 if season_running else 1,
    )
    if outside.empty:
        st.info("Todos os circuitos da base estão no calendário atual.")
    else:
        def absent_label(value: int) -> str:
            return "1 temporada" if int(value) == 1 else f"{int(value)} temporadas"

        outside_table = pd.DataFrame(
            {
                "Circuito": outside["circuit_name"],
                "País": outside["circuit_country"].fillna("—"),
                "Último GP": outside["last_race_name"].fillna("—"),
                "Estreia": outside["first_season"].astype(int),
                "Última edição": outside["last_season"].astype(int),
                "Edições": outside["editions"].astype(int),
                "Ausente há": outside["seasons_absent"].map(absent_label),
                "Maior vencedor": [
                    f"{row['biggest_winner']} — {int(row['biggest_wins'])}"
                    + (" *" if row["tied"] else "")
                    for _, row in outside.iterrows()
                ],
            }
        )
        st.dataframe(outside_table, hide_index=True, width="stretch")
        for _, row in outside[outside["tied"].map(bool)].iterrows():
            st.caption(
                f"\\* {row['circuit_name']}: empate com "
                f"{', '.join(row['tied'])} — {int(row['biggest_wins'])} "
                "vitória(s) em cada."
            )
        st.caption(
            f"Lista calculada pelo calendário importado: traçados que não "
            f"recebem GP em {reference_season}. \"Ausente há\" é a diferença "
            "entre a última edição e a temporada atual. Uma temporada de "
            "ausência pode ser rotação (ex.: Barcelona e Spa a partir de 2027) "
            "e não extinção — o painel não prevê calendário futuro."
        )
        if season_running:
            st.caption(
                f"Como {reference_season} está em andamento, a lista exige "
                "2 temporadas de ausência: etapas futuras ainda não importadas "
                "não aparecem como fora do calendário."
            )
        st.download_button(
            "Baixar circuitos fora do calendário (CSV)",
            csv_bytes(outside_table),
            file_name="circuitos_fora_do_calendario.csv",
            mime="text/csv",
        )

    # equipes no periodo ----------------------------------------------
    team_period = data.constructor_period_stats(frames)
    if not team_period.empty:
        st.markdown("#### Equipes no período")
        team_table = pd.DataFrame(
            {
                "Equipe": team_period["constructor_name"],
                "Temporadas": team_period["seasons"].astype(int),
                "Pontos": team_period["points"].map(fmt_points),
                "Vitórias": team_period["wins"].astype(int),
                "Pódios": team_period["podiums"].astype(int),
            }
        )
        st.dataframe(team_table, hide_index=True, width="stretch")

        team_by_season = data.constructor_points_by_season(frames)
        team_long = team_by_season.melt(
            id_vars="season", var_name="Equipe", value_name="Pontos"
        )
        fig_teams = px.bar(
            team_long,
            x="season",
            y="Pontos",
            color="Equipe",
            barmode="group",
            labels={"season": "Temporada"},
            title="Pontos por equipe e temporada (corridas + sprints)",
        )
        fig_teams.update_layout(height=420, legend_title_text="")
        fig_teams.update_xaxes(type="category")
        st.plotly_chart(fig_teams, width="stretch")

        st.download_button(
            "Baixar equipes do período (CSV)",
            csv_bytes(team_table),
            file_name=f"equipes_periodo_{PERIOD_LABEL.replace('-', '_')}.csv",
            mime="text/csv",
        )

# --------------------------------------------------------------------------
# aba ranking (periodo carregado)
# --------------------------------------------------------------------------
with tab_ranking:
    ranking_caption = (
        f"Ranking acumulado de {PERIOD_LABEL}, usando apenas corridas principais "
        "(sprints não contam como GP nem como vitória). Quando novas temporadas "
        "forem importadas, o ranking se amplia automaticamente."
    )
    if IN_PROGRESS_SEASONS:
        ranking_caption += (
            " Temporadas em andamento entram com as etapas já disputadas. "
            "Títulos só contam quando já estão matematicamente garantidos ou "
            "quando a temporada é encerrada."
        )
    ranking_caption += " " + POINTS_ERA_NOTE
    st.caption(ranking_caption)
    rankings = data.period_driver_rankings(frames)
    if rankings.empty:
        st.info("Sem dados suficientes para montar o ranking.")
    else:
        metric_options = {
            "Vitórias": "wins",
            "Pódios": "podiums",
            "Corridas disputadas": "starts",
            "Poles": "poles",
            "Voltas rápidas": "fastest_laps",
            "Títulos": "titles",
            "Pontos": "points",
        }
        metric_label = st.selectbox(
            "Métrica do ranking",
            list(metric_options),
            key="ranking_metric",
        )
        metric = metric_options[metric_label]

        top = (
            rankings.sort_values(
                [metric, "wins", "podiums", "starts"], ascending=False
            )
            .head(10)
            .reset_index(drop=True)
        )
        top.insert(0, "Pos.", top.index + 1)
        top_table = pd.DataFrame(
            {
                "Pos.": top["Pos."],
                "Piloto": top["full_name"],
                "Equipe(s)": top["teams"].fillna("—"),
                metric_label: (
                    top[metric].map(fmt_points)
                    if metric == "points"
                    else top[metric].astype(int)
                ),
                "Temporadas": top["seasons"].astype(int),
            }
        )

        st.markdown(f"#### Top 10 — {metric_label}")
        st.dataframe(top_table, hide_index=True, width="stretch")

        fig_rank = px.bar(
            top.sort_values(metric),
            x=metric,
            y="full_name",
            orientation="h",
            labels={metric: metric_label, "full_name": "Piloto"},
            title=f"Top 10 — {metric_label} ({PERIOD_LABEL})",
        )
        fig_rank.update_layout(height=420, showlegend=False)
        st.plotly_chart(fig_rank, width="stretch")

        st.download_button(
            f"Baixar top 10 — {metric_label} (CSV)",
            csv_bytes(top_table),
            file_name=f"ranking_{metric}_{PERIOD_LABEL.replace('-', '_')}.csv",
            mime="text/csv",
        )

        st.divider()
        st.markdown("#### Maiores vencedores por século — top 10")
        st.caption(
            "Dois recortes calculados a partir da base carregada: século XX "
            "(1980–1999) e século XXI (2000–2026). Empates são exibidos "
            "explicitamente; nunca são resolvidos por ordem arbitrária."
        )
        render_century_winners(
            frames,
            "Século XX (1980–1999)",
            "seculo_xx_1980_1999",
            1980,
            1999,
            "Critério: os 10 pilotos com mais vitórias entre 1980 e 1999, com "
            "desempate por pódios e corridas. O circuito é contado por traçado, "
            "não pelo nome do GP. Vitórias em sprints não entram.",
            warning=(
                "Recorte incompleto: a base começa em 1980, então faltam as "
                "temporadas 1950–1979 do século XX. Esta lista mostra apenas "
                "os vencedores de 1980–1999."
            ),
        )
        render_century_winners(
            frames,
            "Século XXI (2000–2026)",
            "seculo_xxi_2000_2026",
            2000,
            2026,
            "Critério: os 10 pilotos com mais vitórias entre 2000 e 2026, com "
            "desempate por pódios e corridas. O circuito é contado por traçado, "
            "não pelo nome do GP. Vitórias em sprints não entram. 2026 está em "
            "andamento e entra com as etapas já disputadas.",
        )

# --------------------------------------------------------------------------
# aba qualidade
# --------------------------------------------------------------------------
with tab_quality:
    st.markdown("#### Validação da base")
    if report is None:
        st.info("Nenhum relatório de validação encontrado para esta base.")
        if st.button("Rodar validação agora", type="primary"):
            new_report = validate(DB_PATH)
            save_report(new_report, REPORT_PATH)
            st.cache_data.clear()
            st.rerun()
    else:
        st.caption(
            f"Relatório gerado em {report['generated_at']} · "
            f"resultado geral: {'APROVADO ✅' if report['ok'] else 'COM PENDÊNCIAS ⚠️'}"
        )
        for check in report["checks"]:
            icon = "✅" if check["ok"] else "❌"
            with st.expander(f"{icon} {check['title']}", expanded=not check["ok"]):
                st.write(check["detail"])
                if not check["ok"] and check.get("data"):
                    st.json(check["data"])
        if st.button("Rodar validação novamente"):
            new_report = validate(DB_PATH)
            save_report(new_report, REPORT_PATH)
            st.cache_data.clear()
            st.rerun()

        if report.get("notes"):
            st.markdown("#### Ausências verificadas na fonte")
            for note in report["notes"]:
                where = f" (R{note['round']})" if note.get("round") else ""
                st.info(
                    f"**{note['season']} · {note['race']}{where}** — {note['note']}"
                )

    st.markdown("#### Cobertura por temporada")
    seasons_table = frames["seasons"].sort_values("season").copy()
    if not seasons_table.empty:
        coverage = pd.DataFrame(
            {
                "Temporada": seasons_table["season"].astype("Int64"),
                "GPs": seasons_table["races_count"].astype("Int64"),
                "Com resultado": seasons_table["results_races"].astype("Int64"),
                "Com classificação": seasons_table["qualifying_races"].astype("Int64"),
                "Sprints": seasons_table["sprint_races"].astype("Int64"),
                "Modo": seasons_table["season"].map(
                    lambda s: "em andamento"
                    if int(s) in IN_PROGRESS_SEASONS
                    else "encerrada"
                ),
                "Campeão": seasons_table["champion_driver_id"].map(
                    lambda d: frames["drivers"].loc[
                        frames["drivers"]["driver_id"] == d, "full_name"
                    ].iloc[0]
                    if d and not frames["drivers"].loc[frames["drivers"]["driver_id"] == d].empty
                    else "—"
                ),
                "Construtor campeão": seasons_table["champion_constructor_id"].map(
                    lambda c: cons_names.get(c, "—")
                ),
                "Importado em": seasons_table["imported_at"],
            }
        )
        st.dataframe(coverage, hide_index=True, width="stretch")

    st.markdown("#### Histórico de importações")
    if not frames["import_runs"].empty:
        runs_table = frames["import_runs"].sort_values("id", ascending=False).head(10)
        st.dataframe(
            pd.DataFrame(
                {
                    "ID": runs_table["id"],
                    "Início": runs_table["started_at"],
                    "Fim": runs_table["finished_at"],
                    "Temporadas": runs_table["seasons"],
                    "Status": runs_table["status"],
                    "Requisições": runs_table["requests"],
                }
            ),
            hide_index=True,
            width="stretch",
        )

    st.markdown("#### Exportar base completa")
    full = season_results.merge(
        races[["round", "race_name", "date"]], on="round", how="left"
    )
    export_cols = [
        "season", "round", "race_name", "date", "full_name", "constructor_name",
        "number", "grid", "position", "position_text", "points", "laps", "status",
        "time_text", "fastest_lap_rank", "fastest_lap_time",
    ]
    st.download_button(
        "Baixar resultados da temporada (CSV)",
        csv_bytes(full[[c for c in export_cols if c in full.columns]]),
        file_name=f"resultados_{season}.csv",
        mime="text/csv",
    )

    st.caption(
        "O ZIP inclui o banco SQLite, todos os CSVs (corridas, classificação, "
        "sprints, standings e cadastros), o relatório de validação e um LEIA-ME."
    )
    export_zip = get_export_zip(signature)
    st.download_button(
        "Baixar base completa (ZIP)",
        export_zip,
        file_name=f"f1_data_center_{PERIOD_LABEL.replace('-', '_')}.zip",
        mime="application/zip",
        type="primary",
    )
    st.caption(f"Tamanho do pacote: {len(export_zip) / 1024:.0f} KB")

    st.divider()
    st.caption(
        "Limitações conhecidas: a API pode não trazer volta mais rápida de todos os GPs; "
        "penalidades e decisões dos comissários não são inferidas; corridas sprint são "
        "mantidas separadas dos GPs principais; a classificação oficial vem dos "
        "endpoints de standings, não de soma manual; temporadas em andamento mostram "
        "apenas as etapas concluídas e a posição atual, sem campeão."
    )
