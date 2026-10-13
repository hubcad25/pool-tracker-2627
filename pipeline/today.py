"""data/today.json : la soirée pour la PWA (matchs, points attendus et réels, P(1er), joueurs adverses à surveiller).

Écrit par la job quotidienne, puis réécrit par chaque run de soirée qui envoie une notif (points réels des
matchs terminés). Les deux jobs poussent ce fichier : un fichier à part évite les conflits sur dashboard.json.

- Attendus : les mêmes que la notif « avant » (`soiree.night` : ROS ÷ matchs restants × facteur du match).
- P(1er) et son delta par point : ceux du classement (`dashboard.standings`), relus par la job de soirée dans
  le today.json précédent. Idem pour le total final projeté du matin (`final`) et son écart-type (`sd`) : la PWA
  recalcule la P(1er) en direct (total du matin − attendu ce soir + réel + encore possible).
  Le delta est le même pour tous les joueurs d'une équipe ; menace = attendu × delta.
- `teams[].players` : les joueurs de l'alignement de chaque équipe qui jouent ce soir (ids ESPN et LNH, match,
  attendu) : la PWA recalcule la soirée en direct à partir du pointage LNH (proxy `infra/aws/proxy_lnh.py`).
- Historique de ma P(1er) : data/state/p_first.json, une valeur par jour, écrite par la job quotidienne.
"""
import json
from datetime import date, datetime, timedelta

from pipeline import config, soiree

PATH = config.ROOT / "data" / "today.json"
HISTORY = config.STATE_DIR / "p_first.json"
HISTORY_DAYS = 400       # toute la saison : la PWA écrase les vieux jours
WATCH = 8
# États LNH → ceux de la PWA
STATES = {"FUT": "FUT", "PRE": "FUT", "LIVE": "LIVE", "CRIT": "LIVE", "OFF": "FINAL", "FINAL": "FINAL"}


def load_history() -> list[dict]:
    return json.loads(HISTORY.read_text()) if HISTORY.exists() else []


def record_p_first(day: date, p_first: float) -> None:
    """Ma P(1er) du jour dans l'historique (remplace celle du même jour)."""
    history = {h["day"]: h["p_first"] for h in load_history()} | {day.isoformat(): p_first}
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps([{"day": d, "p_first": p} for d, p in sorted(history.items())], indent=0) + "\n")


def odds(rows: list[dict]) -> dict[int, tuple[float | None, float | None]]:
    """team_id → (P(1er), delta de ma P(1er) par point), depuis le classement ou un today.json."""
    return {r["team_id"]: (r.get("p_first"), r.get("delta_p_first_per_point")) for r in rows}


def load_odds() -> dict[int, tuple[float | None, float | None]]:
    return odds(json.loads(PATH.read_text()).get("teams", [])) if PATH.exists() else {}


def finals(rows: list[dict]) -> dict[int, tuple[float | None, float | None]]:
    """team_id → (total final projeté du matin, son écart-type), depuis le classement ou un today.json."""
    return {r["team_id"]: (r.get("final"), r.get("sd")) for r in rows}


def load_finals() -> dict[int, tuple[float | None, float | None]]:
    return finals(json.loads(PATH.read_text()).get("teams", [])) if PATH.exists() else {}


def _when(team: str, games: list[dict]) -> dict | None:
    """Le match de ce soir d'une équipe LNH : début, adversaire (« @CGY » à l'étranger) et état."""
    for g in games:
        away, home = g["teams"]
        if team in (away, home):
            return {"game_id": g["game_id"], "start": g["start"], "opp": f"@{home}" if team == away else away,
                    "state": g["state"]}
    return None


def _player(p: dict, rate: float, game: dict, points: dict[int, tuple[int, str]],
            nhl_of: dict[int, int]) -> dict:
    done = game["state"] in soiree.DONE
    nhl_id = nhl_of.get(p["espn_id"])
    return {"espn_id": p["espn_id"], "nhl_id": nhl_id, "name": p["name"], "pos": p.get("pos"),
            "team": soiree._nhl_team(p), "game_id": game["game_id"], "opp": game["opp"], "start": game["start"],
            "expected": round(rate, 2), "actual": points.get(nhl_id, (0, ""))[0] if done else None}


# Champs d'un joueur dans `teams[].players` (de quoi recalculer la soirée en direct dans la PWA)
LIVE_FIELDS = ("espn_id", "nhl_id", "name", "pos", "team", "game_id", "opp", "start", "expected", "actual")


def build(day: date, league: dict, team_id: int, rates: dict[str, float], games: list[dict],
          points: dict[int, tuple[int, str]], nhl_of: dict[int, int],
          team_odds: dict[int, tuple[float | None, float | None]], history: list[dict], now: datetime,
          factors: dict[str, tuple[float, float]] | None = None,
          team_finals: dict[int, tuple[float | None, float | None]] | None = None) -> dict:
    """`games` : nhl.fetch_games du jour ; `points` : points de pool des matchs terminés, par nhl_id ;
    `factors` : contexte.factors du soir ; `team_finals` : total final du matin et écart-type (cf. finals)."""
    started = any(g["state"] in soiree.DONE for g in games)
    teams, my_players, watch = [], [], []
    for t in league["teams"]:
        mine = t["team_id"] == team_id
        p_first, delta = team_odds.get(t["team_id"], (None, None))
        final, sd = (team_finals or {}).get(t["team_id"], (None, None))
        n = soiree.night(t, rates, games, points, nhl_of, factors)
        teams.append({"team_id": t["team_id"], "abbrev": t.get("abbrev"), "name": t.get("name"), "mine": mine,
                      "points": t.get("points") or 0, "p_first": p_first, "delta_p_first_per_point": delta,
                      "final": final, "sd": sd,
                      "expected_tonight": round(n["expected"], 1), "actual_tonight": n["actual"] if started else None,
                      "playing_tonight": len(n["players"]), "players": []})
        for p, rate in n["players"]:
            card = _player(p, rate, _when(soiree._nhl_team(p), games), points, nhl_of)
            teams[-1]["players"].append({k: card[k] for k in LIVE_FIELDS})
            if mine:
                card["injury"] = None if p.get("injury_status", "ACTIVE") == "ACTIVE" else p["injury_status"]
                my_players.append(card)
            else:
                card["owner"] = {"team_id": t["team_id"], "abbrev": t.get("abbrev"), "name": t.get("name")}
                card["delta_p_first_per_point"] = delta
                card["threat"] = round(rate * delta, 5) if delta is not None else None
                watch.append(card)
    for r in teams:
        r["players"].sort(key=lambda c: (c["start"], -c["expected"]))
    teams.sort(key=lambda r: (-(r["p_first"] or 0), -r["points"]))
    my_players.sort(key=lambda c: (c["start"], -c["expected"]))
    watch.sort(key=lambda c: (c["threat"] if c["threat"] is not None else 0, -c["expected"]))
    me = team_odds.get(team_id, (None, None))[0]
    yesterday = (day - timedelta(days=1)).isoformat()
    past = [h for h in history if h["day"] <= day.isoformat()]
    return {
        "date": day.isoformat(),
        "updated": now.astimezone(config.TZ).isoformat(timespec="seconds"),
        "games": [{"id": g["game_id"], "start": g["start"], "away": g["teams"][0], "home": g["teams"][1],
                   "state": STATES.get(g["state"], g["state"])} for g in sorted(games, key=lambda g: g["start"])],
        "p_first": {"now": me, "yesterday": next((h["p_first"] for h in past if h["day"] == yesterday), None),
                    "history": past[-HISTORY_DAYS:]},
        "teams": teams,
        "my_players": my_players,
        "watch": watch[:WATCH],
    }


def write(data: dict) -> None:
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
