import io
import zipfile

import pandas as pd

from f1dc import export


def _frames():
    return {
        "seasons": pd.DataFrame({"season": [2025]}),
        "races": pd.DataFrame({"season": [2025], "round": [1], "race_name": ["GP A"]}),
        "race_results": pd.DataFrame(
            {"season": [2025], "driver_id": ["a"], "points": [25.0]}
        ),
        "qualifying_results": pd.DataFrame(
            {"season": [2025], "driver_id": ["a"], "position": [1]}
        ),
        "sprint_results": pd.DataFrame(
            {"season": [2025], "driver_id": ["a"], "points": [8.0]}
        ),
        "driver_standings": pd.DataFrame({"season": [2025], "driver_id": ["a"]}),
        "constructor_standings": pd.DataFrame({"season": [2025], "constructor_id": ["t1"]}),
        "drivers": pd.DataFrame({"driver_id": ["a"], "full_name": ["Piloto A"]}),
        "constructors": pd.DataFrame({"constructor_id": ["t1"], "name": ["Equipe 1"]}),
        "circuits": pd.DataFrame({"circuit_id": ["c1"], "name": ["Circuito"]}),
    }


def test_export_zip_contains_db_csvs_report_and_readme(tmp_path):
    db = tmp_path / "f1.db"
    db.write_bytes(b"SQLite format 3\x00")
    report = tmp_path / "validation_report.json"
    report.write_text('{"ok": true}', encoding="utf-8")

    data = export.build_export_zip(
        _frames(),
        db_path=db,
        report_path=report,
        generated_at="2026-01-01T00:00:00+00:00",
    )

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert "base_f1.db" in names
        assert "validacao.json" in names
        assert "LEIA-ME.txt" in names
        assert "resultados_corridas.csv" in names
        assert "classificacao.csv" in names
        assert "sprints.csv" in names
        assert "standings_pilotos.csv" in names
        assert "standings_construtores.csv" in names

        readme = zf.read("LEIA-ME.txt").decode("utf-8")
        assert "2026-01-01T00:00:00+00:00" in readme
        assert "Temporadas: 2025" in readme
        assert "api.jolpi.ca" in readme

        csv_text = zf.read("resultados_corridas.csv").decode("utf-8-sig")
        assert ";" in csv_text
        assert "25,0" in csv_text


def test_export_without_db_or_report_still_builds():
    data = export.build_export_zip(_frames())

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert "base_f1.db" not in names
        assert "validacao.json" not in names
        assert "LEIA-ME.txt" in names
        assert "calendario.csv" in names


def test_readme_marks_in_progress_season(monkeypatch):
    monkeypatch.setattr(export.config, "IN_PROGRESS_SEASONS", {2026})
    monkeypatch.setattr(export.config, "IN_PROGRESS_CALENDAR_RACES", {2026: 23})
    monkeypatch.setattr(
        export.config,
        "CLINCHED_CHAMPIONS",
        {2026: {"driver": "antonelli", "constructor": "mercedes"}},
    )
    frames = _frames()
    frames["seasons"] = pd.DataFrame(
        {"season": [2025, 2026], "races_count": [24, 20]}
    )

    data = export.build_export_zip(frames, generated_at="2026-01-01T00:00:00+00:00")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        readme = zf.read("LEIA-ME.txt").decode("utf-8")

    assert "Temporadas encerradas: 2025" in readme
    assert "Temporadas em andamento: 2026: 20 de 23 GPs concluídos" in readme
    assert "título de pilotos garantido matematicamente: antonelli" in readme
    assert "título de construtores garantido matematicamente: mercedes" in readme
    assert "sem campeão" not in readme


def test_readme_marks_in_progress_season_without_clinched_title(monkeypatch):
    monkeypatch.setattr(export.config, "IN_PROGRESS_SEASONS", {2026})
    monkeypatch.setattr(export.config, "IN_PROGRESS_CALENDAR_RACES", {2026: 23})
    monkeypatch.setattr(export.config, "CLINCHED_CHAMPIONS", {})
    frames = _frames()
    frames["seasons"] = pd.DataFrame(
        {"season": [2025, 2026], "races_count": [24, 20]}
    )

    data = export.build_export_zip(frames, generated_at="2026-01-01T00:00:00+00:00")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        readme = zf.read("LEIA-ME.txt").decode("utf-8")

    assert "2026: 20 de 23 GPs concluídos, sem campeão definido" in readme
