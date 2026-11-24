"""Smoke test do dashboard com o banco real (pulado se a base não existe)."""

import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from f1dc import config


def _has_season(year: int) -> bool:
    if not Path(config.DB_PATH).exists():
        return False
    conn = sqlite3.connect(config.DB_PATH)
    try:
        return (
            conn.execute(
                "SELECT COUNT(*) FROM seasons WHERE season = ?", (year,)
            ).fetchone()[0]
            > 0
        )
    finally:
        conn.close()


@pytest.mark.skipif(
    not Path(config.DB_PATH).exists(), reason="base ainda não importada"
)
def test_app_abre_sem_excecao():
    app = AppTest.from_file(str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=120).run()
    assert not app.exception, [str(e) for e in app.exception]


@pytest.mark.skipif(
    not Path(config.DB_PATH).exists(), reason="base ainda não importada"
)
def test_app_troca_de_temporada():
    app = AppTest.from_file(str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=120).run()
    app.sidebar.selectbox[0].select(2021).run()
    assert not app.exception, [str(e) for e in app.exception]
    assert any("2021" in str(m.value) for m in app.metric)


@pytest.mark.skipif(
    not Path(config.DB_PATH).exists(), reason="base ainda não importada"
)
def test_comparacao_livre_entre_pilotos():
    app = AppTest.from_file(str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=180).run()
    compare = next(s for s in app.selectbox if s.key == "compare_driver")
    assert len(compare.options) > 1
    compare.select(compare.options[-1]).run()
    assert not app.exception, [str(e) for e in app.exception]
    assert any("Comparar com outro piloto" in str(m.value) for m in app.markdown)


@pytest.mark.skipif(
    not Path(config.DB_PATH).exists(), reason="base ainda não importada"
)
def test_piloto_com_mais_de_um_companheiro():
    app = AppTest.from_file(str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=180).run()
    app.sidebar.selectbox[0].select(2023).run()
    driver = next(s for s in app.selectbox if s.label == "Piloto")
    tsunoda = next(option for option in driver.options if "Tsunoda" in option)
    driver.select(tsunoda).run()
    assert not app.exception, [str(e) for e in app.exception]


@pytest.mark.skipif(
    not Path(config.DB_PATH).exists(), reason="base ainda não importada"
)
def test_app_temporada_2016_sem_sprint():
    app = AppTest.from_file(str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=180).run()
    app.sidebar.selectbox[0].select(2016).run()
    assert not app.exception, [str(e) for e in app.exception]
    assert any("2016" in str(m.value) for m in app.metric)


@pytest.mark.skipif(
    not Path(config.DB_PATH).exists(), reason="base ainda não importada"
)
def test_aba_ranking_troca_metrica():
    app = AppTest.from_file(str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=180).run()
    metric = next(s for s in app.selectbox if s.key == "ranking_metric")
    metric.select("Títulos").run()
    assert not app.exception, [str(e) for e in app.exception]
    assert any("Top 10 — Títulos" in str(m.value) for m in app.markdown)


@pytest.mark.skipif(
    not _has_season(2026), reason="temporada 2026 ainda não importada"
)
def test_app_temporada_2026_em_andamento():
    app = AppTest.from_file(
        str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=180
    ).run()
    app.sidebar.selectbox[0].select(2026).run()
    assert not app.exception, [str(e) for e in app.exception]
    assert any(
        "Temporada em andamento" in str(c.value) for c in app.caption
    ), [str(c.value) for c in app.caption]
    assert any(
        "garantido matematicamente" in str(c.value) for c in app.caption
    ), [str(c.value) for c in app.caption]
    assert any(
        "Campeão de pilotos (matemático)" in str(m.label) for m in app.metric
    ), [str(m.label) for m in app.metric]


@pytest.mark.skipif(
    not _has_season(2000), reason="temporada 2000 ainda não importada"
)
def test_app_2000_qualifying_complementar():
    app = AppTest.from_file(
        str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=180
    ).run()
    app.sidebar.selectbox[0].select(2000).run()
    gp = next(s for s in app.selectbox if s.label == "Escolha um Grande Prêmio")
    brazil = next(option for option in gp.options if "Brazilian" in option)
    gp.select(brazil).run()
    assert not app.exception, [str(e) for e in app.exception]
    assert any(
        "Classificação complementada pela Wikipédia (en)" in str(c.value)
        for c in app.caption
    ), [str(c.value) for c in app.caption]
    tables = [frame.value for frame in app.dataframe]
    assert any(
        "Tempo" in list(table.columns) and "Q1" not in list(table.columns)
        for table in tables
    ), [list(table.columns) for table in tables]


@pytest.mark.skipif(
    not _has_season(2001), reason="temporada 2001 ainda não importada"
)
def test_app_2001_qualifying_complementar():
    app = AppTest.from_file(
        str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=180
    ).run()
    app.sidebar.selectbox[0].select(2001).run()
    assert not app.exception, [str(e) for e in app.exception]
    assert any(
        "Classificação complementada pela Wikipédia (en)" in str(c.value)
        for c in app.caption
    ), [str(c.value) for c in app.caption]
    tables = [frame.value for frame in app.dataframe]
    assert any(
        "Tempo" in list(table.columns) and "Q1" not in list(table.columns)
        for table in tables
    ), [list(table.columns) for table in tables]


@pytest.mark.skipif(
    not _has_season(2002), reason="temporada 2002 ainda não importada"
)
def test_app_2002_qualifying_complementar():
    app = AppTest.from_file(
        str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=180
    ).run()
    app.sidebar.selectbox[0].select(2002).run()
    assert not app.exception, [str(e) for e in app.exception]
    assert any(
        "Classificação complementada pela Wikipédia (en)" in str(c.value)
        for c in app.caption
    ), [str(c.value) for c in app.caption]
    tables = [frame.value for frame in app.dataframe]
    assert any(
        "Tempo" in list(table.columns) and "Q1" not in list(table.columns)
        for table in tables
    ), [list(table.columns) for table in tables]


@pytest.mark.skipif(
    not _has_season(1990), reason="temporada 1990 ainda não importada"
)
def test_app_vencedores_por_seculo():
    app = AppTest.from_file(
        str(Path(config.PROJECT_ROOT) / "app.py"), default_timeout=180
    ).run()
    assert not app.exception, [str(e) for e in app.exception]
    markdowns = [str(m.value) for m in app.markdown]
    assert any("Maiores vencedores por século" in m for m in markdowns)
    assert any("Século XX (1970–1999)" in m for m in markdowns)
    assert any("Século XXI (2000–2026)" in m for m in markdowns)
    warnings = [str(w.value) for w in app.warning]
    assert any("faltam as temporadas 1950–1969" in w for w in warnings), warnings
