"""ESPN Fantasy : endpoint public (statuts de blessure) et API de la ligue (rosters, transactions).
ESPN LNH (public) : les cotes des matchs d'un jour."""
import json

from pipeline import config
from pipeline.http import get_json
from pipeline.ids import ESPN_TO_NHL_TEAM

BASE = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{config.ESPN_SEASON}"
PLAYERS_URL = f"{BASE}/segments/0/leaguedefaults/1?view=kona_playercard"
LEAGUE_URL = f"{BASE}/segments/0/leagues/{config.LEAGUE_ID}"

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={day}"
ODDS_URL = "https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events/{id}/competitions/{id}/odds"

POSITIONS = {1: "C", 2: "LW", 3: "RW", 4: "D", 5: "G"}
# lineupSlotId dans la ligue (vérifié le 2026-10-02 sur les rosters réels)
SLOTS = {3: "F", 4: "D", 5: "G", 8: "IR"}


def _pro_teams() -> dict[int, str]:
    d = get_json(f"{BASE}?view=proTeamSchedules_wl")
    return {t["id"]: t["abbrev"] for t in d["settings"]["proTeams"]}


def _player_row(p: dict, pro_teams: dict[int, str]) -> dict:
    details = p.get("injuryDetails") or {}
    ret = details.get("expectedReturnDate")
    return {
        "espn_id": p["id"],
        "name": p["fullName"],
        "pos": POSITIONS.get(p.get("defaultPositionId"), "?"),
        "pro_team": pro_teams.get(p.get("proTeamId"), "FA"),
        "injury_status": p.get("injuryStatus", "ACTIVE"),
        "injury_type": details.get("type"),
        "expected_return": f"{ret[0]:04d}-{ret[1]:02d}-{ret[2]:02d}" if ret else None,
        "out_for_season": bool(details.get("outForSeason")),
    }


def fetch_players(limit: int = 1500) -> list[dict]:
    """Les `limit` joueurs les plus détenus dans ESPN, avec leur statut. Aucune auth."""
    filt = {"players": {"limit": limit, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
    d = get_json(PLAYERS_URL, headers={"X-Fantasy-Filter": json.dumps(filt)})
    pro_teams = _pro_teams()
    rows = [_player_row(e["player"], pro_teams) for e in d["players"]]
    for e, row in zip(d["players"], rows, strict=True):
        row["pct_owned"] = round(e["player"].get("ownership", {}).get("percentOwned", 0), 2)
    return rows


def fetch_players_by_id(espn_ids: list[int]) -> list[dict]:
    filt = {"players": {"filterIds": {"value": espn_ids}}}
    d = get_json(PLAYERS_URL, headers={"X-Fantasy-Filter": json.dumps(filt)})
    pro_teams = _pro_teams()
    return [_player_row(e["player"], pro_teams) for e in d["players"]]


def has_cookies() -> bool:
    return bool(config.env("ESPN_S2") and config.env("SWID"))


def _cookies() -> dict:
    s2, swid = config.env("ESPN_S2"), config.env("SWID")
    if not (s2 and swid):
        raise RuntimeError("ESPN_S2 et SWID requis pour l'API de la ligue")
    return {"espn_s2": s2, "SWID": swid}


def fetch_league() -> dict:
    """Équipes et rosters de la ligue. Lève AuthError si les cookies sont expirés."""
    d = get_json(f"{LEAGUE_URL}?view=mTeam&view=mRoster&view=mSettings", cookies=_cookies())
    pro_teams = _pro_teams()
    teams = []
    for t in d["teams"]:
        roster = []
        for e in t.get("roster", {}).get("entries", []):
            row = _player_row(e["playerPoolEntry"]["player"], pro_teams)
            row["slot"] = SLOTS.get(e.get("lineupSlotId"), str(e.get("lineupSlotId")))
            roster.append(row)
        teams.append({
            "team_id": t["id"],
            "abbrev": t.get("abbrev"),
            "name": t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}".strip(),
            # + les points d'avant le draft, qu'ESPN n'ajoutera qu'à la fin de la saison
            "points": (t.get("points") or 0) + config.PRE_DRAFT.get(t["id"], (0, 0))[1],
            # Signatures de FA de la saison (les moves sont limités)
            "acquisitions": t.get("transactionCounter", {}).get("acquisitions"),
            "roster": roster,
        })
    # L'API de la ligue donne le statut mais pas les détails (type, date de retour) : on les prend du public
    rostered = [p for t in teams for p in t["roster"]]
    public = {p["espn_id"]: p for p in fetch_players_by_id([p["espn_id"] for p in rostered])}
    for p in rostered:
        if p["espn_id"] in public:
            for k in ("injury_status", "injury_type", "expected_return", "out_for_season"):
                p[k] = public[p["espn_id"]][k]
    return {"teams": teams, "settings": {"name": d.get("settings", {}).get("name")}}


def fetch_transactions() -> list[dict]:
    d = get_json(f"{LEAGUE_URL}?view=mTransactions2", cookies=_cookies())
    return d.get("transactions", [])


def odds_book(item: dict) -> dict:
    """Cotes d'un livre (américaines ; None si absentes). Victoire : la fermeture, sinon la dernière cote
    (avant 2023-24, ESPN n'a pas de fermeture)."""
    def moneyline(side: str):
        odds = item.get(side, {})
        ml = odds.get("close", {}).get("moneyLine", {}).get("american")
        if ml in (None, "", "OFF"):
            return odds.get("moneyLine")
        return float(ml.replace("EVEN", "100"))
    return {"book": item["provider"]["name"], "home_ml": moneyline("homeTeamOdds"),
            "away_ml": moneyline("awayTeamOdds"), "total": item.get("overUnder"), "over": item.get("overOdds"),
            "under": item.get("underOdds")}


def fetch_game_odds(day: str) -> list[dict]:
    """Matchs de saison régulière du jour (AAAA-MM-JJ) : équipes (abréviations LNH), état (pre, in, post) et cotes
    de chaque livre."""
    events = get_json(SCOREBOARD_URL.format(day=day.replace("-", ""))).get("events", [])
    out = []
    for e in events:
        if e["season"]["type"] != 2:
            continue
        side = {t["homeAway"]: t["team"]["abbreviation"] for t in e["competitions"][0]["competitors"]}
        items = get_json(ODDS_URL.format(id=e["id"])).get("items", [])
        out.append({"home": ESPN_TO_NHL_TEAM.get(side["home"], side["home"]),
                    "away": ESPN_TO_NHL_TEAM.get(side["away"], side["away"]), "state": e["status"]["type"]["state"],
                    "books": [odds_book(i) for i in items]})
    return out
