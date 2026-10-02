"""Cache MoneyPuck historique pour le backtest (backtest/cache/, gitignoré).

- Résumés de saison 2019-2025 (situation « all ») : prior Marcel et taux de carrière.
- Match par match des patineurs des saisons du backtest, réduit aux colonnes utiles.
- Dates de naissance (API stats de la LNH) : ajustement pour l'âge de Marcel.

    uv run python -m backtest.fetch
"""
import csv
import io
import time
from pathlib import Path

import requests

from model.ros import CAREER_PATH
from pipeline.http import get

CACHE = Path(__file__).resolve().parent / "cache"
SUMMARY_SEASONS = range(2019, 2026)    # MoneyPuck : année de début de saison
BACKTEST_SEASONS = range(2022, 2026)   # 2022-23 à 2025-26
SUMMARY_URL = "https://moneypuck.com/moneypuck/playerData/seasonSummary/{season}/regular/skaters.csv"
BIOS_URL = ("https://api.nhle.com/stats/rest/en/skater/bios?limit=-1&cayenneExp="
            "seasonId={season}{end}%20and%20gameTypeId=2")
GAME_URL = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/regular/skaters/{nhl_id}.csv"

COLUMNS = ["playerId", "season", "name", "gameId", "playerTeam", "gameDate", "position", "icetime",
           "I_F_goals", "I_F_primaryAssists", "I_F_secondaryAssists", "I_F_xGoals", "I_F_shotsOnGoal",
           "OnIce_F_goals", "OnIce_F_shotsOnGoal"]
# Totaux de carrière gardés pour l'ajustement pour la chance (clé du modèle → colonne MoneyPuck)
CAREER = {"gp": ["games_played"], "g": ["I_F_goals"], "a": ["I_F_primaryAssists", "I_F_secondaryAssists"],
          "ixg": ["I_F_xGoals"], "sog": ["I_F_shotsOnGoal"], "on_goals": ["OnIce_F_goals"],
          "on_sog": ["OnIce_F_shotsOnGoal"]}


def _all_rows(text: str) -> list[dict]:
    return [r for r in csv.DictReader(io.StringIO(text)) if r["situation"] == "all"]


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def summary_path(season: int) -> Path:
    return CACHE / f"summary_{season}.csv"


def games_path(nhl_id: str) -> Path:
    return CACHE / "games" / f"{nhl_id}.csv"


def fetch_summaries() -> None:
    for season in SUMMARY_SEASONS:
        path = summary_path(season)
        if not path.exists():
            rows = _all_rows(get(SUMMARY_URL.format(season=season)).text)
            _write(path, rows, list(rows[0]))
            print(f"résumé {season} : {len(rows)} patineurs")


def fetch_birthdates() -> None:
    path = CACHE / "birthdates.csv"
    if path.exists():
        return
    born = {}
    for season in SUMMARY_SEASONS:
        for p in get(BIOS_URL.format(season=season, end=season + 1)).json()["data"]:
            born[p["playerId"]] = p["birthDate"]
    _write(path, [{"playerId": k, "birthDate": v} for k, v in born.items()], ["playerId", "birthDate"])
    print(f"dates de naissance : {len(born)}")


def _fetch_games(nhl_id: str) -> None:
    path = games_path(nhl_id)
    if path.exists():
        return
    seasons = {str(s) for s in BACKTEST_SEASONS}
    for wait in (60, 300, 900):
        try:
            text = get(GAME_URL.format(nhl_id=nhl_id)).text
            break
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code != 429:
                raise
            print(f"  429, pause de {wait} s")
            time.sleep(wait)
    else:
        raise RuntimeError(f"MoneyPuck refuse toujours {nhl_id}")
    rows = [r for r in _all_rows(text) if r["season"] in seasons]
    _write(path, rows, COLUMNS)


def fetch_games() -> None:
    (CACHE / "games").mkdir(parents=True, exist_ok=True)
    ids = sorted({r["playerId"] for s in BACKTEST_SEASONS
                  for r in csv.DictReader(summary_path(s).open())})
    todo = [i for i in ids if not games_path(i).exists()]
    print(f"match par match : {len(todo)} joueurs à télécharger sur {len(ids)}")
    for n, nhl_id in enumerate(todo, 1):    # séquentiel : MoneyPuck répond 429 en parallèle
        _fetch_games(nhl_id)
        time.sleep(1)
        if n % 100 == 0:
            print(f"  {n}/{len(todo)}", flush=True)


def freeze_career(path: Path = CAREER_PATH) -> None:
    """Totaux des 3 saisons avant 2026-27 (ajustement pour la chance en production). Fichier figé."""
    totals = {}
    for season in range(max(SUMMARY_SEASONS) - 2, max(SUMMARY_SEASONS) + 1):
        for r in csv.DictReader(summary_path(season).open()):
            t = totals.setdefault(r["playerId"], {"nhl_id": r["playerId"], "name": r["name"]}
                                  | dict.fromkeys(CAREER, 0.0))
            for key, cols in CAREER.items():
                t[key] += sum(float(r[c]) for c in cols)
    rows = [t | {k: round(t[k], 2) for k in CAREER} for t in totals.values()]
    _write(path, sorted(rows, key=lambda t: int(t["nhl_id"])), ["nhl_id", "name", *CAREER])
    print(f"carrière : {len(rows)} joueurs → {path}")


if __name__ == "__main__":
    CACHE.mkdir(exist_ok=True)
    fetch_summaries()
    fetch_birthdates()
    fetch_games()
