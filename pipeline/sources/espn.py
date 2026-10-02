"""ESPN Fantasy : endpoint public (statuts de blessure) et API de la ligue (rosters, transactions)."""
import json

from pipeline import config
from pipeline.http import get_json

BASE = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{config.ESPN_SEASON}"
PLAYERS_URL = f"{BASE}/segments/0/leaguedefaults/1?view=kona_playercard"
LEAGUE_URL = f"{BASE}/segments/0/leagues/{config.LEAGUE_ID}"

POSITIONS = {1: "C", 2: "LW", 3: "RW", 4: "D", 5: "G"}


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
            # TODO confirmer avec une vraie réponse quel lineupSlotId correspond à IR
            row["slot_id"] = e.get("lineupSlotId")
            roster.append(row)
        teams.append({
            "team_id": t["id"],
            "abbrev": t.get("abbrev"),
            "name": t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}".strip(),
            "roster": roster,
        })
    return {"teams": teams, "settings": {"name": d.get("settings", {}).get("name")}}


def fetch_transactions() -> list[dict]:
    d = get_json(f"{LEAGUE_URL}?view=mTransactions2", cookies=_cookies())
    return d.get("transactions", [])
