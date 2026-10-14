"""Gardiens partants de ce soir d'après MoneyPuck (probabilité de commencer, puis « confirmé » le jour même).

Points attendus d'un gardien dont on connaît la chance de commencer : P(partant) × points de pool attendus du
gardien de son équipe ce soir (cotes, ou la moyenne de la ligue sans cotes). L'autre gardien de l'équipe :
1 − P(partant), partagé s'ils sont plusieurs. Sans info MoneyPuck : le rythme ROS × facteur (part des départs).

MoneyPuck retire le partant de sa page dès que le match commence : on garde alors la P(partant) du today.json
précédent, pour que l'attendu d'avant-match ne bouge pas pendant le match.
"""
import unicodedata
from datetime import date

from model import soir as model
from pipeline import soiree
from pipeline.contexte import LEAGUE_GOALS
from pipeline.sources import moneypuck


def _norm(name: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)).lower().strip()


def p_start(league: dict, starters: dict[str, tuple[str, float]]) -> dict[int, float]:
    """espn_id → P(partant) des gardiens des équipes de la ligue dont MoneyPuck nomme le partant probable."""
    goalies: dict[str, list[dict]] = {}
    for t in league["teams"]:
        for p in t["roster"]:
            if p.get("pos") == "G":
                goalies.setdefault(soiree._nhl_team(p), []).append(p)
    out = {}
    for team, mine in goalies.items():
        if team not in starters:
            continue
        last, prob = starters[team]
        named = [p for p in mine if _norm(p["name"]).endswith(" " + _norm(last))]
        others = [p for p in mine if p not in named]
        for p in named:
            out[p["espn_id"]] = prob
        for p in others:
            out[p["espn_id"]] = (1 - prob) / len(others)
    return out


def previous(data: dict | None, day: date) -> dict[int, float]:
    """Les P(partant) d'un today.json du même jour."""
    if not data or data.get("date") != day.isoformat():
        return {}
    return {p["espn_id"]: p["p_start"] for t in data.get("teams", []) for p in t.get("players", [])
            if p.get("p_start") is not None}


def load(day: date, league: dict, goals: dict[str, tuple[float, float]],
         current: dict | None = None) -> dict[int, tuple[float, float]]:
    """espn_id → (P(partant), points attendus ce soir). `goals` : contexte.load_goals ; `current` : le today.json
    actuel. MoneyPuck en panne : on garde ce qu'on avait."""
    try:
        fresh = p_start(league, moneypuck.fetch_starters(day))
    except Exception as e:  # noqa: BLE001 — les partants sont un plus : la soirée doit partir sans eux
        print(f"Partants MoneyPuck inaccessibles ({e})")
        fresh = {}
    teams = {p["espn_id"]: soiree._nhl_team(p) for t in league["teams"] for p in t["roster"]}
    out = {}
    for espn_id, p in (previous(current, day) | fresh).items():
        lam, lam_opp = goals.get(teams.get(espn_id), (LEAGUE_GOALS, LEAGUE_GOALS))
        out[espn_id] = (p, p * model.goalie_points(lam, lam_opp))
    return out
