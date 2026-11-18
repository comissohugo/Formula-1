"""Exportação da base completa do F1 Data Center em um arquivo ZIP.

O pacote inclui o banco SQLite, os CSVs de todas as tabelas principais, o
relatório de validação e um LEIA-ME com a origem e o resumo dos dados.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config

# (chave em frames, nome do arquivo no ZIP)
TABLE_FILES: tuple[tuple[str, str], ...] = (
    ("races", "calendario.csv"),
    ("race_results", "resultados_corridas.csv"),
    ("qualifying_results", "classificacao.csv"),
    ("session_awards", "premios_complementares.csv"),
    ("sprint_results", "sprints.csv"),
    ("driver_standings", "standings_pilotos.csv"),
    ("constructor_standings", "standings_construtores.csv"),
    ("drivers", "pilotos.csv"),
    ("constructors", "equipes.csv"),
    ("circuits", "circuitos.csv"),
)


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def _lookup_name(
    frames: dict[str, pd.DataFrame],
    table: str,
    id_column: str,
    name_column: str,
    value: str | None,
) -> str | None:
    """Resolve um nome legível, mantendo o identificador se não encontrar."""
    if value is None:
        return None
    df = frames.get(table)
    if df is None or df.empty:
        return value
    if id_column not in df.columns or name_column not in df.columns:
        return value
    match = df[df[id_column] == value]
    return str(match[name_column].iloc[0]) if not match.empty else value


def _readme(
    frames: dict[str, pd.DataFrame],
    generated_at: str,
    db_path: Path | None,
    report_path: Path | None,
) -> str:
    seasons = frames.get("seasons")
    races = frames.get("races")
    results = frames.get("race_results")
    sprints = frames.get("sprint_results")

    season_years = (
        sorted(int(s) for s in seasons["season"].dropna().unique())
        if seasons is not None and not seasons.empty
        else []
    )
    in_progress = set(getattr(config, "IN_PROGRESS_SEASONS", set()))
    in_progress_calendar = getattr(config, "IN_PROGRESS_CALENDAR_RACES", {})
    clinched = getattr(config, "CLINCHED_CHAMPIONS", {})
    closed_years = [y for y in season_years if y not in in_progress]
    progress_years = [y for y in season_years if y in in_progress]
    period = (
        f"{season_years[0]}-{season_years[-1]}" if season_years else "período carregado"
    )

    lines = [
        "F1 DATA CENTER - exportação da base histórica",
        "=" * 48,
        "",
        f"Gerado em: {generated_at}",
        "Fonte: Jolpica F1 API (estrutura Ergast) - https://api.jolpi.ca/ergast/f1",
        f"Temporadas: {period}",
        "",
        "Resumo",
        "------",
    ]
    if closed_years:
        lines.append(
            "Temporadas encerradas: " + ", ".join(str(y) for y in closed_years)
        )
    if progress_years:
        details = []
        for year in progress_years:
            count = 0
            if seasons is not None and not seasons.empty:
                match = seasons[seasons["season"] == year]
                if not match.empty:
                    count = int(match["races_count"].iloc[0] or 0)
            total = in_progress_calendar.get(year)
            label = f"{year}: {count}"
            if total:
                label += f" de {total}"
            label += " GPs concluídos"
            info = clinched.get(year, {})
            clinch_parts = []
            if info.get("driver"):
                driver_name = _lookup_name(
                    frames, "drivers", "driver_id", "full_name", info["driver"]
                )
                clinch_parts.append(
                    f"título de pilotos garantido matematicamente: {driver_name}"
                )
            if info.get("constructor"):
                team_name = _lookup_name(
                    frames, "constructors", "constructor_id", "name", info["constructor"]
                )
                clinch_parts.append(
                    f"título de construtores garantido matematicamente: {team_name}"
                )
            if clinch_parts:
                label += "; " + "; ".join(clinch_parts)
            else:
                label += ", sem campeão definido"
            details.append(label)
        lines.append("Temporadas em andamento: " + "; ".join(details))
    if races is not None:
        lines.append(f"Grandes Prêmios: {len(races)}")
    if results is not None:
        lines.append(f"Linhas de resultado de corrida: {len(results)}")
    if sprints is not None:
        lines.append(f"Linhas de resultado de sprint: {len(sprints)}")
    if db_path is not None and Path(db_path).exists():
        lines.append("Banco SQLite: base_f1.db")
    if report_path is not None and Path(report_path).exists():
        lines.append("Relatório de validação: validacao.json")

    lines += [
        "",
        "Arquivos CSV",
        "------------",
        "Separador: ponto e vírgula (;)",
        "Decimal: vírgula (,)",
        "Codificação: UTF-8 com BOM (abre direto no Excel em português)",
        "",
        "calendario.csv ............... GPs, circuitos e datas",
        "resultados_corridas.csv ...... resultado completo de cada corrida",
        "classificacao.csv ............ classificação (qualifying; tempo único "
        "em 2000–2002)",
        "premios_complementares.csv ... pole/volta rápida de fonte complementar "
        "(Wikipédia)",
        "sprints.csv .................. resultados das sprints (separadas dos GPs)",
        "standings_pilotos.csv ........ classificação oficial de pilotos "
        "(final ou atual)",
        "standings_construtores.csv ... classificação oficial de construtores "
        "(final ou atual)",
        "pilotos.csv .................. cadastro de pilotos",
        "equipes.csv .................. cadastro de equipes",
        "circuitos.csv ................ cadastro de circuitos",
        "",
        "Observações",
        "-----------",
        "- Corridas sprint são mantidas separadas dos GPs principais.",
        "- A classificação oficial vem dos endpoints de standings, não de",
        "  soma manual de pontos.",
        "- Temporadas em andamento incluem apenas etapas concluídas; a",
        "  classificação é a posição atual, não a final. Títulos só aparecem",
        "  quando já estão matematicamente garantidos.",
        "- Penalidades não são inferidas; apenas os status fornecidos são exibidos.",
        "- Quando a fonte primária não traz pole ou volta mais rápida, a lacuna",
        "  pode ser complementada pela Wikipédia (pt) na tabela",
        "  session_awards, com URL e data de importação. A fonte primária",
        "  sempre tem prioridade; nada é preenchido por suposição.",
        "- O qualifying completo de 2000 a 2002, ausente na maior parte dos",
        "  GPs na fonte primária, foi complementado pela Wikipédia (en) na",
        "  própria tabela de classificação, com source_url e fetched_at por",
        "  linha. Os GPs já cobertos pela fonte primária foram mantidos e",
        "  conferidos (4 em 2000, 1 em 2001 e 2 em 2002).",
        "- Ausências da fonte são documentadas no relatório de validação, sem",
        "  preenchimento por suposição.",
        "- Em temporada em andamento, atualize depois de cada GP com",
        "  f1dc.ingest --seasons <ano> e em seguida f1dc.validate. Etapas que",
        "  ainda não aconteceram são ignoradas com aviso e a importação não",
        "  duplica registros.",
        "",
    ]
    return "\n".join(lines)


def build_export_zip(
    frames: dict[str, pd.DataFrame],
    db_path: str | Path | None = None,
    report_path: str | Path | None = None,
    generated_at: str | None = None,
) -> bytes:
    """Monta em memória o ZIP completo da base e devolve os bytes."""
    moment = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = Path(db_path) if db_path else None
    report = Path(report_path) if report_path else None

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, filename in TABLE_FILES:
            df = frames.get(key)
            if df is not None and not df.empty:
                zf.writestr(filename, _csv_bytes(df))

        if db is not None and db.exists():
            zf.write(db, arcname="base_f1.db")
        if report is not None and report.exists():
            zf.write(report, arcname="validacao.json")

        zf.writestr("LEIA-ME.txt", _readme(frames, moment, db, report))

    return buffer.getvalue()
