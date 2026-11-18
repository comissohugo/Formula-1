"""Cliente HTTP da Jolpica F1 API.

Pontos importantes (verificados contra a API real):

* Os endpoints de temporada (``/{season}/races``, ``/{season}/driverStandings``)
  paginam por linha. ``limit``/``offset`` funcionam e ``MRData.total`` informa
  o total de linhas.
* Os endpoints por GP (``/{season}/{round}/results``) retornam todas as linhas
  daquele GP em uma única página (no máximo ~24 pilotos), então não há risco
  de resultado truncado no meio de um GP.
* ``/{season}/driverStandings`` devolve apenas a classificação APÓS A ÚLTIMA
  rodada (uma única StandingsList).
* O campo ``points`` dos resultados já inclui o ponto de volta mais rápida
  quando a regra valia (2021-2024). Confirmado em 2021 (Bottas 16 pts) e
  2024 (vencedor com 26 pts); em 2025 o vencedor tem 25 pts.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Iterable

import requests

from . import config

log = logging.getLogger(__name__)


class ApiError(RuntimeError):
    """Falha definitiva ao consultar a API."""


class JolpicaClient:
    def __init__(
        self,
        base_url: str = config.BASE_URL,
        interval: float = config.REQUEST_INTERVAL,
        timeout: int = config.REQUEST_TIMEOUT,
        max_retries: int = config.MAX_RETRIES,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.interval = interval
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent", "f1-data-center/1.0 (projeto historico pessoal)"
        )
        self.request_count = 0
        self._last_request = 0.0

    # -- infraestrutura ----------------------------------------------------
    def _throttle(self) -> None:
        wait = self.interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        """GET em ``path`` e devolve o dicionário ``MRData``."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        params.setdefault("limit", config.PAGE_SIZE)
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:  # rede caiu, timeout, DNS...
                last_error = exc
                delay = min(2 ** attempt, 30)
                log.warning(
                    "Falha de rede em %s (tentativa %s/%s): %s. Nova tentativa em %ss",
                    url, attempt, self.max_retries, exc, delay,
                )
                time.sleep(delay)
                continue
            finally:
                self._last_request = time.monotonic()

            self.request_count += 1

            if response.status_code == 429 or 500 <= response.status_code < 600:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else min(2 ** attempt, 30)
                except ValueError:
                    delay = min(2 ** attempt, 30)
                if response.status_code == 429:
                    # Adapta o ritmo: se a API reclamar, diminuímos a cadência.
                    self.interval = min(self.interval * 1.5, 5.0)
                last_error = ApiError(f"HTTP {response.status_code} em {url}")
                log.warning(
                    "HTTP %s em %s (tentativa %s/%s). Nova tentativa em %ss",
                    response.status_code, url, attempt, self.max_retries, delay,
                )
                time.sleep(delay)
                continue

            if response.status_code == 404:
                # Recurso inexistente (ex.: GP que não aconteceu). Não é erro fatal.
                log.info("404 em %s - recurso inexistente, retornando vazio", url)
                return {"total": "0"}

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                raise ApiError(f"HTTP {response.status_code} em {url}") from exc

            payload = response.json()
            if "MRData" not in payload:
                raise ApiError(f"Resposta inesperada (sem MRData) em {url}")
            return payload["MRData"]

        raise ApiError(f"Falha após {self.max_retries} tentativas em {url}: {last_error}")

    def paginate(
        self,
        path: str,
        extract: Callable[[dict[str, Any]], tuple[list[Any], int]],
    ) -> list[Any]:
        """Percorre todas as páginas de um endpoint de temporada."""
        rows: list[Any] = []
        offset = 0
        while True:
            mrdata = self.get(path, limit=config.PAGE_SIZE, offset=offset)
            page_rows, total = extract(mrdata)
            rows.extend(page_rows)
            offset += config.PAGE_SIZE
            if not page_rows or offset >= total:
                break
        return rows

    # -- endpoints ---------------------------------------------------------
    def races(self, season: int) -> list[dict[str, Any]]:
        return self.paginate(f"{season}/races.json", _extract_races)

    def sprint_rounds(self, season: int) -> list[int]:
        races = self.paginate(f"{season}/sprint.json", _extract_races)
        return sorted({int(r["round"]) for r in races})

    def race_results(self, season: int, round_: int) -> list[dict[str, Any]]:
        return _single_race_rows(f"{season}/{round_}/results.json", "Results", self)

    def qualifying(self, season: int, round_: int) -> list[dict[str, Any]]:
        return _single_race_rows(
            f"{season}/{round_}/qualifying.json", "QualifyingResults", self
        )

    def sprint_results(self, season: int, round_: int) -> list[dict[str, Any]]:
        return _single_race_rows(f"{season}/{round_}/sprint.json", "SprintResults", self)

    def driver_standings(self, season: int) -> list[tuple[str, str, dict[str, Any]]]:
        """Classificação final oficial: lista de (season, round, linha)."""
        return self.paginate(
            f"{season}/driverStandings.json", _extract_standings("DriverStandings")
        )

    def constructor_standings(self, season: int) -> list[tuple[str, str, dict[str, Any]]]:
        return self.paginate(
            f"{season}/constructorStandings.json",
            _extract_standings("ConstructorStandings"),
        )


# --- extratores -----------------------------------------------------------
def _extract_races(mrdata: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    races = mrdata.get("RaceTable", {}).get("Races", []) or []
    return races, int(mrdata.get("total", 0) or 0)


def _extract_standings(key: str) -> Callable[[dict[str, Any]], tuple[list[Any], int]]:
    def extract(mrdata: dict[str, Any]) -> tuple[list[Any], int]:
        lists = mrdata.get("StandingsTable", {}).get("StandingsLists", []) or []
        rows = [
            (lst.get("season", ""), lst.get("round", ""), item)
            for lst in lists
            for item in lst.get(key, []) or []
        ]
        return rows, int(mrdata.get("total", 0) or 0)

    return extract


def _single_race_rows(
    path: str, key: str, client: JolpicaClient
) -> list[dict[str, Any]]:
    mrdata = client.get(path)
    races = mrdata.get("RaceTable", {}).get("Races", []) or []
    if not races:
        return []
    return races[0].get(key, []) or []


def dedupe(rows: Iterable[Any], key: Callable[[Any], Any]) -> list[Any]:
    """Remove duplicatas mantendo a primeira ocorrência (defesa contra paginação)."""
    seen: set[Any] = set()
    out: list[Any] = []
    for row in rows:
        k = key(row)
        if k in seen:
            continue
        seen.add(k)
        out.append(row)
    return out
