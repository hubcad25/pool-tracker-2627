"""Cache MoneyPuck historique pour le backtest (backtest/cache/, gitignoré).

- Résumés de saison 2008-2025 : prior Marcel (3 saisons) et taux de carrière (toutes les saisons depuis 2008-09,
  premier exercice de MoneyPuck ; mêmes totaux que le match par match, en 18 fichiers au lieu de ~1300).
- Match par match des patineurs des saisons du backtest, réduit aux colonnes utiles.
- Dates de naissance (API stats de la LNH) : ajustement pour l'âge de Marcel.
- Matchs ESPN avec les cotes de chaque livre (victoire, total de buts) : backtest des points d'un soir.

    uv run python -m backtest.fetch
"""
import csv
import io
import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

from model.ros import CAREER_PATH
from pipeline.http import get
from pipeline.sources.espn import ODDS_URL, SCOREBOARD_URL, odds_book

CACHE = Path(__file__).resolve().parent / "cache"
GAMES_DIR = CACHE / "games_xg"     # avec OnIce_F_xGoals (games_sit : ancienne version, sans)
SUMMARY_SEASONS = range(2008, 2026)    # MoneyPuck : année de début de saison
BACKTEST_SEASONS = range(2022, 2026)   # 2022-23 à 2025-26
SUMMARY_URL = "https://moneypuck.com/moneypuck/playerData/seasonSummary/{season}/regular/skaters.csv"
BIOS_URL = ("https://api.nhle.com/stats/rest/en/skater/bios?limit=-1&cayenneExp="
            "seasonId={season}{end}%20and%20gameTypeId=2")
ODDS_PATH = CACHE / "odds.jsonl"     # un match ESPN par ligne
GAME_URL = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/regular/skaters/{nhl_id}.csv"

SITUATIONS = {"all", "5on5", "5on4"}   # 5on4 : avantage numérique
COLUMNS = ["playerId", "season", "name", "gameId", "playerTeam", "gameDate", "position", "situation", "icetime",
           "I_F_goals", "I_F_primaryAssists", "I_F_secondaryAssists", "I_F_xGoals", "I_F_shotsOnGoal",
           "OnIce_F_goals", "OnIce_F_shotsOnGoal", "OnIce_F_xGoals"]
# Totaux de carrière gardés pour l'ajustement pour la chance (clé du modèle → colonne MoneyPuck)
CAREER = {"gp": ["games_played"], "g": ["I_F_goals"], "a": ["I_F_primaryAssists", "I_F_secondaryAssists"],
          "ixg": ["I_F_xGoals"], "sog": ["I_F_shotsOnGoal"], "on_goals": ["OnIce_F_goals"],
          "on_sog": ["OnIce_F_shotsOnGoal"], "on_xg": ["OnIce_F_xGoals"]}


def _rows(text: str) -> list[dict]:
    return [r for r in csv.DictReader(io.StringIO(text)) if r["situation"] in SITUATIONS]


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def summary_path(season: int) -> Path:
    return CACHE / f"summary_sit_{season}.csv"


def games_path(nhl_id: str) -> Path:
    return GAMES_DIR / f"{nhl_id}.csv"


def fetch_summaries() -> None:
    for season in SUMMARY_SEASONS:
        path = summary_path(season)
        if not path.exists():
            rows = _rows(get(SUMMARY_URL.format(season=season)).text)
            _write(path, rows, list(rows[0]))
            print(f"résumé {season} : {len(rows)} patineurs")
            time.sleep(2)


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
    rows = [r for r in _rows(text) if r["season"] in seasons]
    _write(path, rows, COLUMNS)


def fetch_games() -> None:
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
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
    """Totaux de carrière (2008-09 à 2025-26) pour l'ajustement pour la chance en production. Fichier figé :
    régénéré le 2026-10-12 (carrière complète au lieu des 3 dernières saisons, exception autorisée)."""
    totals = {}
    for season in SUMMARY_SEASONS:
        for r in csv.DictReader(summary_path(season).open()):
            if r["situation"] != "all":
                continue
            t = totals.setdefault(r["playerId"], {"nhl_id": r["playerId"], "name": r["name"]}
                                  | dict.fromkeys(CAREER, 0.0))
            for key, cols in CAREER.items():
                t[key] += sum(float(r[c]) for c in cols)
    rows = [t | {k: round(t[k], 2) for k in CAREER} for t in totals.values()]
    _write(path, sorted(rows, key=lambda t: int(t["nhl_id"])), ["nhl_id", "name", *CAREER])
    print(f"carrière : {len(rows)} joueurs → {path}")


def fetch_odds() -> None:
    """Matchs de saison régulière des saisons du backtest, avec score et cotes (reprend là où il s'est arrêté)."""
    done = set()
    if ODDS_PATH.exists():
        done = {r["day"] for r in map(json.loads, ODDS_PATH.open()) if r["espn_id"] is None}
    with ODDS_PATH.open("a") as out:
        for season in BACKTEST_SEASONS:
            day = date(season, 10, 1)
            while day < date(season + 1, 4, 25):
                if day.isoformat() not in done:
                    events = get(SCOREBOARD_URL.format(day=day.strftime("%Y%m%d"))).json().get("events", [])
                    for e in events:
                        if e["season"]["type"] != 2:
                            continue
                        side = {t["homeAway"]: t for t in e["competitions"][0]["competitors"]}
                        items = get(ODDS_URL.format(id=e["id"])).json().get("items", [])
                        out.write(json.dumps({
                            "day": day.isoformat(), "espn_id": e["id"], "start": e["date"],
                            "home": side["home"]["team"]["abbreviation"], "away": side["away"]["team"]["abbreviation"],
                            "home_goals": int(side["home"].get("score") or 0),
                            "away_goals": int(side["away"].get("score") or 0),
                            "periods": e["competitions"][0].get("status", e.get("status", {})).get("period"),
                            "books": [odds_book(i) for i in items]}) + "\n")
                    out.write(json.dumps({"day": day.isoformat(), "espn_id": None}) + "\n")   # jour traité
                    out.flush()
                    if day.day == 1:
                        print(f"cotes : {day}", flush=True)
                day += timedelta(days=1)


if __name__ == "__main__":
    CACHE.mkdir(exist_ok=True)
    fetch_summaries()
    fetch_birthdates()
    fetch_games()
    fetch_odds()
