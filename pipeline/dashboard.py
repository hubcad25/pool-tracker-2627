"""data/dashboard.json : tout ce que la PWA affiche, déjà calculé. L'app ne fait aucun calcul de modèle.

Une carte par joueur de mon équipe : points, pace, bande préseason, ROS et total final projeté,
indicateurs de chance et verdict.
"""
import json
from datetime import date

from model import ros as model_ros
from pipeline import config, rules
from pipeline.events import Event
from pipeline.ids import pos_group

PATH = config.ROOT / "data" / "dashboard.json"
# Avant ce nombre de matchs, les indicateurs de chance sont surtout du bruit
MIN_GP_VERDICT = 10
# Écart minimal entre les points attendus (sans la chance) et les points réels pour un verdict
LUCK_POINTS = 3.0
SLOT_ORDER = {"F": 0, "D": 1, "G": 2, "IR": 3}
SEASON_GAMES = 84         # depuis 2026-27


def _ratio(num: float, den: float) -> float | None:
    return num / den if den > 0 else None


def _round(x: float | None, n: int = 1) -> float | None:
    return None if x is None else round(x, n)


def luck(obs: dict | None, career: dict | None, pos: str) -> dict | None:
    """Indicateurs de chance de la saison. `expected` : les points avec la finition et le sh% des coéquipiers
    de carrière (régressés vers la moyenne), comme dans la ROS mais sans le poids w."""
    if not obs or not obs["gp"] or pos == "G":
        return None
    params = rules.ros_params()
    expected = model_ros.luck_adjusted_points(obs, career, params[pos]["m"], params["league_teammate_sh"])
    return {
        "expected_points": _round(expected),
        "sh": _round(_ratio(obs["g"], obs["sog"]), 3),
        "sh_career": _round(_ratio(career["g"], career["sog"]), 3) if career else None,
        "g_minus_ixg": _round(obs["g"] - obs["ixg"]),
        "oish": _round(model_ros.teammate_sh(obs), 3),
        "oish_career": _round(model_ros.teammate_sh(career), 3) if career else None,
        "toi": _round(obs["toi"] / obs["gp"] / 60) if obs.get("toi") else None,
    }


def verdict(gp: float, points: float, indicators: dict | None, pos: str) -> str | None:
    """malchanceux / chanceux / conforme, ou petit_echantillon. None pour un gardien."""
    if pos == "G":
        return None
    if indicators is None:
        return "petit_echantillon" if gp == 0 else None
    if gp < MIN_GP_VERDICT:
        return "petit_echantillon"
    gap = indicators["expected_points"] - points
    if gap >= LUCK_POINTS:
        return "malchanceux"
    if gap <= -LUCK_POINTS:
        return "chanceux"
    return "conforme"


def prior_band(prior: dict, games: float) -> dict:
    """Quantiles préseason ramenés au même nombre de matchs que le total final projeté.

    Le prior inclut le risque de blessure (`gp` < 84) alors que la ROS n'en prévoit aucune : sans ça,
    presque tout le monde finirait au-dessus de sa médiane préseason."""
    return {name: _round(prior[q] / prior["gp"] * games) for name, q in (("p10", "q10"), ("p50", "sim_median"),
                                                                         ("p90", "q90"))}


def card(player: dict, prior: dict | None, schedule: list[dict], today: date) -> dict:
    pos = pos_group(player["pos"])
    obs = (prior or {}).get("obs")
    gp = obs["gp"] if obs else 0
    g, a = (obs["g"], obs["a"]) if obs else (0, 0)
    points = g + a
    r = rules.ros(player, prior, schedule, today)
    games_left = rules.games_left(player, schedule, today)
    indicators = luck(obs, (prior or {}).get("career"), pos)
    injured = player["injury_status"] != "ACTIVE"
    return {
        "espn_id": player["espn_id"],
        "name": player["name"],
        "pos": player["pos"],
        "group": pos,
        "team": player["pro_team"],
        "slot": player["slot"],
        "injury": {
            "status": player["injury_status"],
            "type": player.get("injury_type"),
            "expected_return": player.get("expected_return"),
            "out_for_season": player.get("out_for_season", False),
            "games_missed": rules.games_missed(player, schedule, today),
        } if injured else None,
        "gp": gp, "g": g, "a": a, "points": points,
        "pace": _round(points / gp * SEASON_GAMES) if gp else None,
        "prior": prior_band(prior, gp + games_left) if r else None,
        "ros": {"mean": _round(r[0]), "p10": _round(r[1]), "p90": _round(r[2]),
                "games_left": games_left} if r else None,
        "final": {"mean": _round(points + r[0]), "p10": _round(points + r[1]), "p90": _round(points + r[2])}
        if r else None,
        "luck": indicators,
        "verdict": verdict(gp, points, indicators, pos),
    }


def build(league: dict | None, team_id: int, schedule: list[dict], priors: dict[int, dict], today: date,
          alerts: list[Event]) -> dict:
    team = next((t for t in (league or {}).get("teams", []) if t["team_id"] == team_id), None)
    cards = [card(p, priors.get(p["espn_id"]), schedule, today) for p in (team or {}).get("roster", [])]
    cards.sort(key=lambda c: (SLOT_ORDER.get(c["slot"], 9), -((c["final"] or {}).get("mean") or 0)))
    return {
        "day": today.isoformat(),
        "team": {"id": team_id, "name": team.get("name")} if team else None,
        "alerts": [{"kind": e.kind, "message": e.message, "priority": e.priority} for e in alerts],
        "players": cards,
    }


def write(data: dict) -> None:
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
