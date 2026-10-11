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


def fetch_games(day: str) -> list[dict]:
    """Matchs de saison régulière d'une journée (date de Montréal), avec l'heure de début et l'état."""
    d = get_json(f"{BASE}/score/{day}")
    return [
        {"game_id": g["id"], "start": g["startTimeUTC"], "state": g["gameState"],
         "teams": [g["awayTeam"]["abbrev"], g["homeTeam"]["abbrev"]]}
        for g in d.get("games", [])
        if g["gameType"] == REGULAR_SEASON
    ]


def fetch_points(game_id: int) -> dict[int, tuple[int, str]]:
    """Points de pool de chaque joueur du match, par nhl_id, avec un libellé : patineurs 1 par but ou passe
    (« 1+1 »), gardiens 2 par victoire, 1 par défaite en prolongation et 1 par blanchissage (barème de la ligue ;
    les passes des gardiens ne comptent pas)."""
    d = get_json(f"{BASE}/gamecenter/{game_id}/boxscore")
    out = {}
    for side in d.get("playerByGameStats", {}).values():
        for p in side.get("forwards", []) + side.get("defense", []):
            g, a = p.get("goals", 0), p.get("assists", 0)
            out[p["playerId"]] = (g + a, f"{g}+{a}")
        used = [p for p in side.get("goalies", []) if p.get("toi", "00:00") != "00:00"]
        for p in used:
            if p.get("decision") == "W" and p.get("goalsAgainst") == 0 and len(used) == 1:
                out[p["playerId"]] = (3, "blanchissage")
            elif p.get("decision") == "W":
                out[p["playerId"]] = (2, "victoire")
            elif p.get("decision") == "O":
                out[p["playerId"]] = (1, "déf. en prol.")
    return out


def fetch_goalie_stats() -> dict[int, dict]:
    """Stats de la saison de chaque gardien, par nhl_id, avec ses points de pool (2 V + DP + BL)."""
    d = get_json("https://api.nhle.com/stats/rest/en/goalie/summary?limit=-1"
                 f"&cayenneExp=seasonId={config.NHL_SEASON}%20and%20gameTypeId={REGULAR_SEASON}")
    return {
        r["playerId"]: {"gp": r["gamesPlayed"], "gs": r["gamesStarted"], "w": r["wins"], "otl": r["otLosses"],
                        "so": r["shutouts"], "points": 2 * r["wins"] + r["otLosses"] + r["shutouts"]}
        for r in d["data"]
    }
