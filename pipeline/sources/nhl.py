"""API publique de la LNH : rosters (ids NHL) et calendrier."""
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

from pipeline import config
from pipeline.http import get_json

BASE = "https://api-web.nhle.com/v1"
REGULAR_SEASON = 2


def team_abbrevs() -> list[str]:
    d = get_json(f"{BASE}/standings/now")
    return sorted(t["teamAbbrev"]["default"] for t in d["standings"])


def _roster(team: str) -> list[dict]:
    d = get_json(f"{BASE}/roster/{team}/current")
    return [
        {
            "nhl_id": p["id"],
            "name": f"{p['firstName']['default']} {p['lastName']['default']}",
            "pos": p["positionCode"],
            "team": team,
            "birth_date": p.get("birthDate"),
        }
        for group in ("forwards", "defensemen", "goalies")
        for p in d.get(group, [])
    ]


def fetch_rosters() -> list[dict]:
    with ThreadPoolExecutor(4) as ex:
        return [p for roster in ex.map(_roster, team_abbrevs()) for p in roster]


def search(name: str) -> list[dict]:
    """Recherche de joueurs par nom. Couvre ceux absents des rosters `current` (blessés, LTIR)."""
    d = get_json(f"https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit=20&q={quote(name)}")
    return [
        {"nhl_id": int(p["playerId"]), "name": p["name"], "pos": p["positionCode"],
         "team": p.get("teamAbbrev") or p.get("lastTeamAbbrev")}
        for p in d
    ]


def _schedule(team: str) -> list[dict]:
    d = get_json(f"{BASE}/club-schedule-season/{team}/{config.NHL_SEASON}")
    return [
        {"game_id": g["id"], "date": g["gameDate"], "team": team, "state": g.get("gameState")}
        for g in d["games"]
        if g["gameType"] == REGULAR_SEASON
    ]


def fetch_schedule() -> list[dict]:
    """Un enregistrement par (équipe, match) de saison régulière."""
    with ThreadPoolExecutor(4) as ex:
        return [g for games in ex.map(_schedule, team_abbrevs()) for g in games]
