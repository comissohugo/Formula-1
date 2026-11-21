"""Consultas e agregações usadas pelo dashboard (sem chamadas de rede)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from . import config, db

TABLES = (
    "seasons",
    "circuits",
    "races",
    "drivers",
    "constructors",
    "race_results",
    "qualifying_results",
    "sprint_results",
    "session_awards",
    "driver_standings",
    "constructor_standings",
    "import_runs",
)

AWARD_COLUMNS = [
    "season",
    "round",
    "award",
    "driver_id",
    "constructor_id",
    "source",
    "source_url",
    "lap",
    "time",
    "speed",
]

NON_CLASSIFIED = {"R", "D", "E", "W", "F", "N"}


def load_frames(db_path: str | Path = config.DB_PATH) -> dict[str, pd.DataFrame]:
    """Carrega todas as tabelas e enriquece com nomes legíveis."""
    conn = db.connect(db_path)
    try:
        frames = {
            table: pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
            for table in TABLES
        }
    finally:
        conn.close()

    drivers = frames["drivers"][["driver_id", "full_name", "code", "nationality"]].rename(
        columns={"nationality": "driver_nationality"}
    )
    constructors = frames["constructors"][
        ["constructor_id", "name", "nationality"]
    ].rename(
        columns={"name": "constructor_name", "nationality": "constructor_nationality"}
    )

    for table in (
        "race_results",
        "qualifying_results",
        "sprint_results",
        "session_awards",
    ):
        frames[table] = (
            frames[table]
            .merge(drivers, on="driver_id", how="left")
            .merge(constructors, on="constructor_id", how="left")
        )

    frames["driver_standings"] = frames["driver_standings"].merge(
        drivers, on="driver_id", how="left"
    )
    frames["constructor_standings"] = frames["constructor_standings"].merge(
        constructors, on="constructor_id", how="left"
    )

    circuits = frames["circuits"][["circuit_id", "name", "locality", "country"]].rename(
        columns={
            "name": "circuit_name",
            "locality": "circuit_locality",
            "country": "circuit_country",
        }
    )
    frames["races"] = apply_race_name_aliases(
        frames["races"].merge(circuits, on="circuit_id", how="left")
    )

    return frames


def apply_race_name_aliases(races: pd.DataFrame) -> pd.DataFrame:
    """Usa o nome oficial conferido onde a primária diverge (ex.: 2026 R7).

    Não altera o banco: ``frames`` é usado apenas para exibição e exportação.
    A URL e a data da conferência viajam nas colunas ``race_name_source*``,
    que também aparecem no CSV do calendário. O alias só é aplicado se o nome
    bruto no banco continuar sendo exatamente o ``primary_name`` esperado —
    assim uma mudança futura da primária não troca o nome de outro GP.
    """
    result = races.copy()
    result["race_name_source"] = "Jolpica"
    result["race_name_source_url"] = None
    result["race_name_verified_at"] = None
    for (season, round_number), alias in config.RACE_NAME_ALIASES.items():
        mask = (
            (result["season"] == season)
            & (result["round"] == round_number)
            & (result["race_name"] == alias["primary_name"])
        )
        if not mask.any():
            continue
        result.loc[mask, "race_name"] = alias["official_name"]
        result.loc[mask, "race_name_source"] = "official"
        result.loc[mask, "race_name_source_url"] = alias["source_url"]
        result.loc[mask, "race_name_verified_at"] = alias["verified_at"]
    return result


def season_races(frames: dict[str, pd.DataFrame], season: int) -> pd.DataFrame:
    races = frames["races"]
    return races[races["season"] == season].sort_values("round").reset_index(drop=True)


def award_events(
    frames: dict[str, pd.DataFrame], award: str
) -> pd.DataFrame:
    """Eventos de pole/volta rápida, com a fonte primária sempre na frente.

    A fonte primária é ``qualifying_results`` (pole) ou ``race_results``
    (volta rápida). A tabela complementar ``session_awards`` só preenche GPs
    sem dado primário; quando as duas existem para o mesmo GP, vale a primária.
    """
    if award not in {"pole", "fastest_lap"}:
        raise ValueError("award deve ser 'pole' ou 'fastest_lap'")

    if award == "pole":
        source = frames["qualifying_results"]
        source = source[source["position"] == 1]
        primary = source[["season", "round", "driver_id", "constructor_id"]].copy()
        primary["lap"] = pd.NA
        primary["time"] = pd.NA
        primary["speed"] = pd.NA
        primary["source_url"] = (
            source["source_url"] if "source_url" in source.columns else pd.NA
        )
    else:
        source = frames["race_results"]
        source = source[source["fastest_lap_rank"] == 1]
        primary = source[["season", "round", "driver_id", "constructor_id"]].copy()
        for target, origin in (
            ("lap", "fastest_lap_number"),
            ("time", "fastest_lap_time"),
            ("speed", "fastest_lap_speed"),
        ):
            primary[target] = source[origin] if origin in source.columns else pd.NA
        primary["source_url"] = pd.NA
    primary["award"] = award
    primary["source"] = [
        "Wikipédia (en)" if "wikipedia.org" in str(url) else "Jolpica"
        for url in primary["source_url"].fillna("")
    ]

    complementary = frames.get("session_awards")
    if complementary is None or complementary.empty:
        wiki = primary.iloc[0:0].copy()
    else:
        wiki = complementary[complementary["award"] == award].copy()
        for column in ("lap", "time", "speed"):
            if column not in wiki:
                wiki[column] = pd.NA
        wiki["source"] = "Wikipédia"

    combined = pd.concat([primary, wiki], ignore_index=True)
    combined = combined[AWARD_COLUMNS].drop_duplicates(
        ["season", "round"], keep="first"
    )

    names = frames["drivers"][["driver_id", "full_name"]]
    constructors = frames["constructors"][["constructor_id", "name"]].rename(
        columns={"name": "constructor_name"}
    )
    return combined.merge(names, on="driver_id", how="left").merge(
        constructors, on="constructor_id", how="left"
    )


def season_awards(
    frames: dict[str, pd.DataFrame], season: int
) -> pd.DataFrame:
    """Poles e voltas rápidas de uma temporada, com fonte e nomes legíveis."""
    events = pd.concat(
        [award_events(frames, "pole"), award_events(frames, "fastest_lap")],
        ignore_index=True,
    )
    return events[events["season"] == season].reset_index(drop=True)


def is_classified(position_text: Any) -> bool:
    text = str(position_text or "").upper()
    return bool(text) and text not in NON_CLASSIFIED


def disqualified_mask(df: pd.DataFrame) -> pd.Series:
    """Desclassificação por positionText 'D' ou status 'Disqualified'."""
    text = df["position_text"].fillna("").astype(str).str.upper()
    status = df["status"].fillna("").astype(str).str.lower()
    return (text == "D") | status.str.contains("disqualified|excluded|withdrawn", regex=True)


def classified_mask(df: pd.DataFrame) -> pd.Series:
    """Piloto recebeu posição de chegada e não foi desclassificado."""
    if df.empty:
        return pd.Series(dtype=bool)
    text = df["position_text"].fillna("").astype(str).str.upper()
    return (
        (text != "")
        & (~text.isin(NON_CLASSIFIED))
        & (~disqualified_mask(df))
        & df["position"].notna()
    )


def _classified_mask(df: pd.DataFrame) -> pd.Series:
    return classified_mask(df)


def driver_season_stats(
    frames: dict[str, pd.DataFrame], season: int, driver_id: str
) -> dict[str, Any]:
    results = frames["race_results"]
    results = results[(results["season"] == season) & (results["driver_id"] == driver_id)]

    classified = _classified_mask(results) if not results.empty else pd.Series(dtype=bool)
    standings = frames["driver_standings"]
    standings = standings[(standings["season"] == season) & (standings["driver_id"] == driver_id)]

    points = float(results["points"].fillna(0).sum()) if not results.empty else 0.0
    official_points = float(standings["points"].iloc[0]) if not standings.empty else None
    official_position = (
        int(standings["position"].iloc[0]) if not standings.empty and pd.notna(standings["position"].iloc[0]) else None
    )

    poles = award_events(frames, "pole")
    poles = poles[(poles["season"] == season) & (poles["driver_id"] == driver_id)]
    fastest = award_events(frames, "fastest_lap")
    fastest = fastest[
        (fastest["season"] == season) & (fastest["driver_id"] == driver_id)
    ]

    return {
        "starts": int(len(results)),
        "points": official_points if official_points is not None else points,
        "calculated_points": points,
        "official_position": official_position,
        "wins": int(((results["position"] == 1) & classified).sum()),
        "podiums": int(((results["position"] <= 3) & classified).sum()),
        "poles": int(len(poles)),
        "fastest_laps": int(len(fastest)),
        "dnf": int((results["position_text"].astype(str).str.upper() == "R").sum()),
        "dsq": int(disqualified_mask(results).sum()) if not results.empty else 0,
        "avg_grid": float(results["grid"].dropna().mean()) if not results.empty else None,
        "avg_finish": float(results["position"].dropna().mean()) if not results.empty else None,
        "constructors": sorted(results["constructor_name"].dropna().unique().tolist()),
    }


def teammate_ids(
    frames: dict[str, pd.DataFrame], season: int, driver_id: str
) -> list[str]:
    results = frames["race_results"]
    season_results = results[results["season"] == season]
    teams = set(season_results.loc[season_results["driver_id"] == driver_id, "constructor_id"])
    mates = season_results[
        season_results["constructor_id"].isin(teams)
        & (season_results["driver_id"] != driver_id)
    ]["driver_id"].unique()
    return sorted(mates)


def head_to_head(
    frames: dict[str, pd.DataFrame], season: int, driver_a: str, driver_b: str
) -> dict[str, Any]:
    """Confronto direto: classificação e corrida (apenas GPs em que ambos têm dado)."""
    quali = frames["qualifying_results"]
    q = quali[quali["season"] == season]
    qa = q[q["driver_id"] == driver_a][["round", "position"]].rename(columns={"position": "pos_a"})
    qb = q[q["driver_id"] == driver_b][["round", "position"]].rename(columns={"position": "pos_b"})
    qm = qa.merge(qb, on="round").dropna()

    results = frames["race_results"]
    r = results[results["season"] == season].copy()
    r = r[_classified_mask(r)]
    ra = r[r["driver_id"] == driver_a][["round", "position"]].rename(columns={"position": "pos_a"})
    rb = r[r["driver_id"] == driver_b][["round", "position"]].rename(columns={"position": "pos_b"})
    rm = ra.merge(rb, on="round").dropna()

    return {
        "quali_a": int((qm["pos_a"] < qm["pos_b"]).sum()),
        "quali_b": int((qm["pos_b"] < qm["pos_a"]).sum()),
        "quali_rounds": int(len(qm)),
        "race_a": int((rm["pos_a"] < rm["pos_b"]).sum()),
        "race_b": int((rm["pos_b"] < rm["pos_a"]).sum()),
        "race_rounds": int(len(rm)),
    }


def cumulative_points(
    frames: dict[str, pd.DataFrame], season: int
) -> pd.DataFrame:
    """Pontos acumulados por piloto ao fim de cada rodada (corrida + sprint)."""
    rounds = season_races(frames, season)["round"].sort_values().tolist()
    parts = []
    for table in ("race_results", "sprint_results"):
        df = frames[table]
        df = df[df["season"] == season][["round", "driver_id", "points"]]
        parts.append(df)
    points = pd.concat(parts, ignore_index=True)
    points["points"] = points["points"].fillna(0.0)
    if not rounds or points.empty:
        return pd.DataFrame(columns=["round", "driver_id", "points", "full_name"])

    grouped = points.groupby(["round", "driver_id"], as_index=False)["points"].sum()
    pivot = (
        grouped.pivot(index="round", columns="driver_id", values="points")
        .reindex(rounds)
        .fillna(0.0)
        .cumsum()
    )
    long = (
        pivot.reset_index()
        .melt(id_vars="round", var_name="driver_id", value_name="points")
        .sort_values(["round", "points"], ascending=[True, False])
    )
    names = frames["drivers"][["driver_id", "full_name"]]
    long = long.merge(names, on="driver_id", how="left")
    return long


def cumulative_constructor_points(
    frames: dict[str, pd.DataFrame], season: int
) -> pd.DataFrame:
    """Pontos acumulados por equipe ao fim de cada rodada (corrida + sprint)."""
    rounds = season_races(frames, season)["round"].sort_values().tolist()
    parts = []
    for table in ("race_results", "sprint_results"):
        df = frames[table]
        df = df[df["season"] == season][["round", "constructor_id", "points"]]
        parts.append(df)
    points = pd.concat(parts, ignore_index=True)
    points["points"] = points["points"].fillna(0.0)
    if not rounds or points.empty:
        return pd.DataFrame(
            columns=["round", "constructor_id", "points", "constructor_name"]
        )

    grouped = points.groupby(["round", "constructor_id"], as_index=False)["points"].sum()
    pivot = (
        grouped.pivot(index="round", columns="constructor_id", values="points")
        .reindex(rounds)
        .fillna(0.0)
        .cumsum()
    )
    long = (
        pivot.reset_index()
        .melt(id_vars="round", var_name="constructor_id", value_name="points")
        .sort_values(["round", "points"], ascending=[True, False])
    )
    names = frames["constructors"][["constructor_id", "name"]].rename(
        columns={"name": "constructor_name"}
    )
    return long.merge(names, on="constructor_id", how="left")


def season_summary(frames: dict[str, pd.DataFrame], season: int) -> dict[str, Any]:
    seasons = frames["seasons"]
    row = seasons[seasons["season"] == season]
    if row.empty:
        return {}
    return row.iloc[0].to_dict()


def _season_extras(
    frames: dict[str, pd.DataFrame], season: int, id_column: str
) -> pd.DataFrame:
    """Pódios (corridas principais) e poles (P1 do qualifying) por temporada."""
    results = frames["race_results"]
    results = results[results["season"] == season].copy()
    if results.empty:
        podiums = pd.Series(dtype=int, name="podiums")
    else:
        classified = classified_mask(results)
        podiums = (
            results[classified & (results["position"] <= 3)]
            .groupby(id_column)
            .size()
            .rename("podiums")
        )

    poles_events = award_events(frames, "pole")
    poles_events = poles_events[poles_events["season"] == season]
    poles = poles_events.groupby(id_column).size().rename("poles")

    return pd.concat([podiums, poles], axis=1).fillna(0).astype(int)


def season_driver_extras(
    frames: dict[str, pd.DataFrame], season: int
) -> pd.DataFrame:
    """Pódios e poles por piloto na temporada, indexados por driver_id."""
    return _season_extras(frames, season, "driver_id")


def season_constructor_extras(
    frames: dict[str, pd.DataFrame], season: int
) -> pd.DataFrame:
    """Pódios e poles por equipe na temporada, indexados por constructor_id."""
    return _season_extras(frames, season, "constructor_id")


# --------------------------------------------------------------------------
# agregações do período completo (aba Histórico)
# --------------------------------------------------------------------------
def period_driver_rankings(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Ranking acumulado de pilotos em todas as temporadas carregadas."""
    in_progress = set(getattr(config, "IN_PROGRESS_SEASONS", set()))
    results = frames["race_results"].copy()
    if results.empty:
        return pd.DataFrame(
            columns=[
                "driver_id", "full_name", "teams", "starts", "points", "wins",
                "podiums", "poles", "fastest_laps", "titles", "dnf", "dsq",
                "seasons",
            ]
        )

    classified = classified_mask(results)
    results["win"] = ((results["position"] == 1) & classified).astype(int)
    results["podium"] = ((results["position"] <= 3) & classified).astype(int)
    results["dnf"] = (results["position_text"].astype(str).str.upper() == "R").astype(int)
    results["dsq"] = disqualified_mask(results).astype(int)

    agg = (
        results.groupby("driver_id")
        .agg(
            starts=("season", "size"),
            points=("points", "sum"),
            wins=("win", "sum"),
            podiums=("podium", "sum"),
            dnf=("dnf", "sum"),
            dsq=("dsq", "sum"),
            seasons=("season", "nunique"),
        )
        .reset_index()
    )

    poles = (
        award_events(frames, "pole")
        .groupby("driver_id")
        .size()
        .rename("poles")
        .reset_index()
    )
    agg = agg.merge(poles, on="driver_id", how="left")
    agg["poles"] = agg["poles"].fillna(0).astype(int)

    fastest = (
        award_events(frames, "fastest_lap")
        .groupby("driver_id")
        .size()
        .rename("fastest_laps")
        .reset_index()
    )
    agg = agg.merge(fastest, on="driver_id", how="left")
    agg["fastest_laps"] = agg["fastest_laps"].fillna(0).astype(int)

    sprint_points = (
        frames["sprint_results"]
        .groupby("driver_id", as_index=False)["points"]
        .sum()
        .rename(columns={"points": "sprint_points"})
    )
    agg = agg.merge(sprint_points, on="driver_id", how="left")
    agg["points"] = agg["points"] + agg["sprint_points"].fillna(0.0)
    agg = agg.drop(columns="sprint_points")

    titles = frames["driver_standings"]
    titles = titles[titles["position"] == 1]
    if in_progress:
        # Líder de temporada em andamento não é campeão, a menos que o título
        # já esteja matematicamente garantido (ver CLINCHED_CHAMPIONS).
        titles = titles[~titles["season"].isin(in_progress)]
    title_rows = titles[["driver_id"]].copy()

    clinched = getattr(config, "CLINCHED_CHAMPIONS", {})
    clinched_drivers = [
        {"driver_id": info["driver"]}
        for season, info in clinched.items()
        if season in in_progress and info.get("driver")
    ]
    if clinched_drivers:
        title_rows = pd.concat(
            [title_rows, pd.DataFrame(clinched_drivers)], ignore_index=True
        )

    titles = (
        title_rows.groupby("driver_id")
        .size()
        .rename("titles")
        .reset_index()
    )
    agg = agg.merge(titles, on="driver_id", how="left")
    agg["titles"] = agg["titles"].fillna(0).astype(int)

    teams = (
        results.dropna(subset=["constructor_name"])
        .groupby("driver_id")["constructor_name"]
        .apply(lambda values: " / ".join(sorted(set(values))))
        .rename("teams")
        .reset_index()
    )
    agg = agg.merge(teams, on="driver_id", how="left")

    names = frames["drivers"][["driver_id", "full_name"]]
    agg = agg.merge(names, on="driver_id", how="left")
    return agg.sort_values("points", ascending=False).reset_index(drop=True)


def _circuit_labels(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Nome e país de cada circuito, sem repetir."""
    races = frames["races"]
    columns = ["circuit_id", "circuit_name", "circuit_country"]
    if races.empty or not set(columns).issubset(races.columns):
        return pd.DataFrame(columns=columns)
    return races[columns].drop_duplicates("circuit_id").reset_index(drop=True)


def _circuit_label(row: pd.Series) -> str:
    """Rótulo do circuito no formato \"Nome (País)\"."""
    name = row.get("circuit_name")
    if name is None or pd.isna(name):
        return "—"
    country = row.get("circuit_country")
    if country is None or pd.isna(country):
        return str(name)
    return f"{name} ({country})"


def _wins_by_circuit(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Uma linha por piloto e circuito, somente onde houve vitória."""
    columns = [
        "driver_id", "circuit_id", "circuit_name", "circuit_country", "wins",
    ]
    results = frames["race_results"]
    if results.empty:
        return pd.DataFrame(columns=columns)
    wins = results[(results["position"] == 1) & classified_mask(results)]
    if wins.empty:
        return pd.DataFrame(columns=columns)
    wins = wins.merge(
        frames["races"][["season", "round", "circuit_id"]],
        on=["season", "round"],
        how="left",
    )
    counts = (
        wins.groupby(["driver_id", "circuit_id"], dropna=False)
        .size()
        .rename("wins")
        .reset_index()
    )
    return counts.merge(_circuit_labels(frames), on="circuit_id", how="left")


def driver_circuit_stats(
    frames: dict[str, pd.DataFrame], driver_id: str
) -> pd.DataFrame:
    """Largadas, vitórias e aproveitamento de um piloto por circuito."""
    columns = [
        "circuit_id", "circuit_name", "circuit_country",
        "starts", "wins", "win_pct",
    ]
    results = frames["race_results"]
    if results.empty:
        return pd.DataFrame(columns=columns)
    own = results[results["driver_id"] == driver_id]
    if own.empty:
        return pd.DataFrame(columns=columns)
    own = own.merge(
        frames["races"][["season", "round", "circuit_id"]],
        on=["season", "round"],
        how="left",
    )
    own = own.assign(
        win=((own["position"] == 1) & classified_mask(own)).astype(int)
    )
    agg = (
        own.groupby("circuit_id", dropna=False)
        .agg(starts=("season", "size"), wins=("win", "sum"))
        .reset_index()
        .merge(_circuit_labels(frames), on="circuit_id", how="left")
    )
    agg["wins"] = agg["wins"].astype(int)
    agg["starts"] = agg["starts"].astype(int)
    agg["win_pct"] = (agg["wins"] / agg["starts"] * 100).round(1)
    return agg.sort_values(
        ["wins", "starts"], ascending=False
    ).reset_index(drop=True)


def favorite_circuit(
    frames: dict[str, pd.DataFrame], driver_id: str
) -> dict[str, Any] | None:
    """Circuito onde o piloto mais venceu, com empates explícitos."""
    table = driver_circuit_stats(frames, driver_id)
    table = table[table["wins"] > 0]
    if table.empty:
        return None
    best = int(table["wins"].max())
    leaders = table[table["wins"] == best].sort_values("circuit_name")
    return {
        "wins": best,
        "label": _circuit_label(leaders.iloc[0]),
        "others": [
            _circuit_label(row) for _, row in leaders.iloc[1:].iterrows()
        ],
    }


def period_top_winners(
    frames: dict[str, pd.DataFrame], limit: int = 10
) -> pd.DataFrame:
    """Top N pilotos por vitórias e o circuito onde cada um mais venceu."""
    columns = [
        "driver_id", "full_name", "wins", "starts", "win_pct",
        "favorite", "favorite_wins", "tied",
    ]
    rankings = period_driver_rankings(frames)
    if rankings.empty:
        return pd.DataFrame(columns=columns)
    by_circuit = _wins_by_circuit(frames)
    top = rankings.sort_values(
        ["wins", "podiums", "starts"], ascending=False
    ).head(limit)
    rows = []
    for _, driver in top.iterrows():
        mine = by_circuit[by_circuit["driver_id"] == driver["driver_id"]]
        favorite = "—"
        favorite_wins = 0
        tied: list[str] = []
        if not mine.empty:
            best = int(mine["wins"].max())
            leaders = mine[mine["wins"] == best].sort_values("circuit_name")
            favorite = _circuit_label(leaders.iloc[0])
            favorite_wins = best
            tied = [
                _circuit_label(row) for _, row in leaders.iloc[1:].iterrows()
            ]
        starts = int(driver["starts"])
        wins = int(driver["wins"])
        rows.append(
            {
                "driver_id": driver["driver_id"],
                "full_name": driver["full_name"],
                "wins": wins,
                "starts": starts,
                "win_pct": round(wins / starts * 100, 1) if starts else 0.0,
                "favorite": favorite,
                "favorite_wins": favorite_wins,
                "tied": tied,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def circuit_top_winners(
    frames: dict[str, pd.DataFrame], circuit_id: str, limit: int = 5
) -> pd.DataFrame:
    """Top N pilotos com mais vitórias em um circuito."""
    columns = ["driver_id", "full_name", "wins", "starts", "win_pct"]
    results = frames["race_results"]
    races = frames["races"]
    if results.empty or races.empty:
        return pd.DataFrame(columns=columns)
    rounds = races[races["circuit_id"] == circuit_id][["season", "round"]]
    if rounds.empty:
        return pd.DataFrame(columns=columns)
    editions = results.merge(rounds, on=["season", "round"], how="inner")
    if editions.empty:
        return pd.DataFrame(columns=columns)
    editions = editions.assign(
        win=((editions["position"] == 1) & classified_mask(editions)).astype(int)
    )
    agg = (
        editions.groupby("driver_id")
        .agg(starts=("season", "size"), wins=("win", "sum"))
        .reset_index()
    )
    agg = agg[agg["wins"] > 0]
    if agg.empty:
        return pd.DataFrame(columns=columns)
    agg = agg.merge(
        frames["drivers"][["driver_id", "full_name"]], on="driver_id", how="left"
    )
    agg["wins"] = agg["wins"].astype(int)
    agg["starts"] = agg["starts"].astype(int)
    agg["win_pct"] = (agg["wins"] / agg["starts"] * 100).round(1)
    agg = agg.sort_values(["wins", "starts"], ascending=False).head(limit)
    return agg.reset_index(drop=True)[columns]


def champions_timeline(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Campeões por temporada encerrada, mais títulos matemáticos em andamento."""
    in_progress = set(getattr(config, "IN_PROGRESS_SEASONS", set()))
    clinched = getattr(config, "CLINCHED_CHAMPIONS", {})

    clinched_driver_seasons = {
        season
        for season, info in clinched.items()
        if season in in_progress and info.get("driver")
    }
    clinched_team_seasons = {
        season
        for season, info in clinched.items()
        if season in in_progress and info.get("constructor")
    }
    closed_seasons = [s for s in config.SEASONS if s not in in_progress]
    driver_seasons = set(closed_seasons) | clinched_driver_seasons
    team_seasons = set(closed_seasons) | clinched_team_seasons

    drivers = frames["driver_standings"]
    drivers = drivers[(drivers["position"] == 1) & drivers["season"].isin(driver_seasons)]
    teams = frames["constructor_standings"]
    teams = teams[(teams["position"] == 1) & teams["season"].isin(team_seasons)]

    timeline = drivers[["season", "driver_id", "full_name", "points", "wins"]].rename(
        columns={"points": "driver_points"}
    )
    timeline = timeline.merge(
        teams[["season", "constructor_id", "constructor_name", "points"]].rename(
            columns={"points": "team_points"}
        ),
        on="season",
        how="left",
    )
    timeline["status"] = timeline["season"].map(
        lambda season: (
            "em andamento (matemático)" if season in in_progress else "encerrada"
        )
    )
    return timeline.sort_values("season").reset_index(drop=True)


def constructor_period_stats(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Pontos, vitórias e pódios por equipe no período."""
    results = frames["race_results"].copy()
    if results.empty:
        return pd.DataFrame(
            columns=["constructor_id", "constructor_name", "points", "wins", "podiums", "seasons"]
        )

    classified = classified_mask(results)
    results["win"] = ((results["position"] == 1) & classified).astype(int)
    results["podium"] = ((results["position"] <= 3) & classified).astype(int)

    agg = (
        results.groupby("constructor_id")
        .agg(
            points=("points", "sum"),
            wins=("win", "sum"),
            podiums=("podium", "sum"),
            seasons=("season", "nunique"),
        )
        .reset_index()
    )
    names = frames["constructors"][["constructor_id", "name"]].rename(
        columns={"name": "constructor_name"}
    )
    agg = agg.merge(names, on="constructor_id", how="left")
    return agg.sort_values("points", ascending=False).reset_index(drop=True)


def points_by_season(
    frames: dict[str, pd.DataFrame], driver_ids: list[str]
) -> pd.DataFrame:
    """Matriz temporada x piloto com os pontos somados no ano."""
    results = frames["race_results"]
    results = results[results["driver_id"].isin(driver_ids)]
    parts = [results[["season", "driver_id", "points"]]]
    sprints = frames["sprint_results"]
    parts.append(sprints[sprints["driver_id"].isin(driver_ids)][["season", "driver_id", "points"]])
    points = pd.concat(parts, ignore_index=True).fillna({"points": 0.0})

    table = (
        points.groupby(["season", "driver_id"], as_index=False)["points"].sum()
        .pivot(index="season", columns="driver_id", values="points")
        .fillna(0.0)
    )
    table = table.reindex(sorted(frames["seasons"]["season"].unique())).fillna(0.0)
    names = dict(zip(frames["drivers"]["driver_id"], frames["drivers"]["full_name"]))
    return table.rename(columns=names).reset_index()


def constructor_points_by_season(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Matriz temporada x equipe com os pontos somados no ano."""
    parts = []
    for table_name in ("race_results", "sprint_results"):
        df = frames[table_name]
        parts.append(df[["season", "constructor_id", "points"]])
    points = pd.concat(parts, ignore_index=True).fillna({"points": 0.0})

    table = (
        points.groupby(["season", "constructor_id"], as_index=False)["points"].sum()
        .pivot(index="season", columns="constructor_id", values="points")
        .fillna(0.0)
    )
    table = table.reindex(sorted(frames["seasons"]["season"].unique())).fillna(0.0)
    names = dict(zip(frames["constructors"]["constructor_id"], frames["constructors"]["name"]))
    return table.rename(columns=names).reset_index()


def circuit_editions(frames: dict[str, pd.DataFrame], circuit_id: str) -> pd.DataFrame:
    """Uma linha por edição do circuito no período (vencedor, pole, volta rápida)."""
    races = frames["races"]
    editions = races[races["circuit_id"] == circuit_id].sort_values("season")
    poles = award_events(frames, "pole")
    fastest_laps = award_events(frames, "fastest_lap")
    rows = []
    for _, race in editions.iterrows():
        results = frames["race_results"]
        results = results[
            (results["season"] == race["season"]) & (results["round"] == race["round"])
        ]
        winner = results[results["position"] == 1]
        pole = poles[
            (poles["season"] == race["season"]) & (poles["round"] == race["round"])
        ]
        fastest = fastest_laps[
            (fastest_laps["season"] == race["season"])
            & (fastest_laps["round"] == race["round"])
        ]
        rows.append(
            {
                "season": int(race["season"]),
                "round": int(race["round"]),
                "race_name": race["race_name"],
                "date": race["date"],
                "winner": winner["full_name"].iloc[0] if not winner.empty else None,
                "winner_team": winner["constructor_name"].iloc[0] if not winner.empty else None,
                "pole": pole["full_name"].iloc[0] if not pole.empty else None,
                "fastest_lap": fastest["full_name"].iloc[0] if not fastest.empty else None,
            }
        )
    return pd.DataFrame(rows)


def period_head_to_head(
    frames: dict[str, pd.DataFrame], driver_a: str, driver_b: str
) -> dict[str, Any]:
    """Confronto direto entre dois pilotos em todo o período."""
    quali = frames["qualifying_results"]
    qa = quali[quali["driver_id"] == driver_a][
        ["season", "round", "position"]
    ].rename(columns={"position": "pos_a"})
    qb = quali[quali["driver_id"] == driver_b][
        ["season", "round", "position"]
    ].rename(columns={"position": "pos_b"})
    qm = qa.merge(qb, on=["season", "round"]).dropna()

    results = frames["race_results"].copy()
    results = results[classified_mask(results)]
    ra = results[results["driver_id"] == driver_a][
        ["season", "round", "position"]
    ].rename(columns={"position": "pos_a"})
    rb = results[results["driver_id"] == driver_b][
        ["season", "round", "position"]
    ].rename(columns={"position": "pos_b"})
    rm = ra.merge(rb, on=["season", "round"]).dropna()

    return {
        "quali_a": int((qm["pos_a"] < qm["pos_b"]).sum()),
        "quali_b": int((qm["pos_b"] < qm["pos_a"]).sum()),
        "quali_rounds": int(len(qm)),
        "race_a": int((rm["pos_a"] < rm["pos_b"]).sum()),
        "race_b": int((rm["pos_b"] < rm["pos_a"]).sum()),
        "race_rounds": int(len(rm)),
    }


def inactive_circuits(
    frames: dict[str, pd.DataFrame],
    reference_season: int | None = None,
    min_seasons_absent: int = 1,
) -> pd.DataFrame:
    """Circuitos que não aparecem na temporada de referência.

    Tudo é derivado dos dados carregados: ``seasons_absent`` conta quantas
    temporadas se passaram desde a última edição, e ``last_race_name`` é o
    nome do GP dessa última edição. O painel **não prevê calendário futuro**:
    ausência de uma temporada pode ser rotação, não extinção. Circuitos com o
    mesmo número de vitórias aparecem todos em ``tied``.

    Em temporada em andamento o calendário completo não está na base (etapas
    futuras não são importadas), então use ``min_seasons_absent=2`` para não
    marcar como ausente um circuito que ainda vai receber corrida.
    """
    columns = [
        "circuit_id", "circuit_name", "circuit_country", "last_race_name",
        "first_season", "last_season", "editions", "seasons_absent",
        "biggest_winner", "biggest_wins", "tied",
    ]
    races = frames["races"]
    if races.empty:
        return pd.DataFrame(columns=columns)
    if reference_season is None:
        reference_season = int(races["season"].max())

    current = set(races.loc[races["season"] == reference_season, "circuit_id"])
    stats = (
        races.groupby("circuit_id")
        .agg(
            circuit_name=("circuit_name", "last"),
            circuit_country=("circuit_country", "last"),
            first_season=("season", "min"),
            last_season=("season", "max"),
            editions=("season", "size"),
        )
        .reset_index()
    )
    last_names = (
        races.sort_values(["season", "round"])
        .groupby("circuit_id")["race_name"]
        .last()
        .rename("last_race_name")
        .reset_index()
    )
    stats = stats.merge(last_names, on="circuit_id", how="left")
    stats = stats[~stats["circuit_id"].isin(current)]
    if stats.empty:
        return pd.DataFrame(columns=columns)

    stats["seasons_absent"] = reference_season - stats["last_season"]
    stats = stats[stats["seasons_absent"] >= max(1, int(min_seasons_absent))]
    if stats.empty:
        return pd.DataFrame(columns=columns)
    stats["first_season"] = stats["first_season"].astype(int)
    stats["last_season"] = stats["last_season"].astype(int)
    stats["editions"] = stats["editions"].astype(int)

    wins = _wins_by_circuit(frames)
    if not wins.empty:
        wins = wins.merge(
            frames["drivers"][["driver_id", "full_name"]], on="driver_id", how="left"
        )
    biggest: list[str] = []
    biggest_wins: list[int] = []
    tied: list[list[str]] = []
    for circuit_id in stats["circuit_id"]:
        mine = wins[wins["circuit_id"] == circuit_id] if not wins.empty else wins
        if mine.empty:
            biggest.append("—")
            biggest_wins.append(0)
            tied.append([])
            continue
        best = int(mine["wins"].max())
        leaders = mine[mine["wins"] == best].sort_values("full_name")
        biggest.append(str(leaders.iloc[0]["full_name"]))
        biggest_wins.append(best)
        tied.append([str(name) for name in leaders.iloc[1:]["full_name"]])
    stats["biggest_winner"] = biggest
    stats["biggest_wins"] = biggest_wins
    stats["tied"] = tied
    return stats.sort_values(
        ["seasons_absent", "last_season", "circuit_name"],
        ascending=[True, False, True],
    ).reset_index(drop=True)[columns]
