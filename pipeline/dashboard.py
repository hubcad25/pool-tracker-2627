"""data/dashboard.json : tout ce que la PWA affiche, déjà calculé. L'app ne fait aucun calcul de modèle.

- players : une carte par joueur de mon équipe (points, pace, bande préseason, ROS et total final projeté,
  indicateurs de chance, verdict) ;
- injuries : les blessés de toute la ligue ;
- free_agents : les meilleurs FA selon la ROS, comparés à mon pire joueur à la même position ;
- standings : points actuels + ROS de l'alignement par équipe, et classement final simulé.
"""
import json
import math
import random
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
LINEUP = {"F": 10, "D": 5}
FA_SHOWN = {"F": 10, "D": 5}
SIMULATIONS = 5000
Z90 = 1.2816              # p90 d'une normale : l'intervalle p10-p90 fait 2 × Z90 écarts-types


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


def _ros(player: dict, priors: dict[int, dict], schedule: list[dict], today: date) -> dict | None:
    r = rules.ros(player, priors.get(player["espn_id"]), schedule, today)
    return {"mean": _round(r[0]), "p10": _round(r[1]), "p90": _round(r[2])} if r else None


def injuries(league: dict, team_id: int, schedule: list[dict], priors: dict[int, dict], today: date) -> list[dict]:
    """Les blessés des 12 équipes, les miens d'abord, puis par ROS. Un DTD qui ne manque aucun match est omis."""
    out = []
    for team in league["teams"]:
        for p in team["roster"]:
            missed = rules.games_missed(p, schedule, today)
            if p["injury_status"] == "ACTIVE" or (p["injury_status"] == "DAY_TO_DAY" and not missed):
                continue
            out.append({
                "espn_id": p["espn_id"], "name": p["name"], "pos": p["pos"], "team": p["pro_team"],
                "owner": team.get("abbrev"), "mine": team["team_id"] == team_id, "status": p["injury_status"],
                "type": p.get("injury_type"), "expected_return": p.get("expected_return"),
                "out_for_season": p.get("out_for_season", False), "games_missed": missed,
                "ros": _ros(p, priors, schedule, today),
            })
    out.sort(key=lambda i: (not i["mine"], -((i["ros"] or {}).get("mean") or 0)))
    return out


def free_agents(league: dict, team_id: int, players: list[dict], schedule: list[dict], priors: dict[int, dict],
                today: date) -> dict:
    """Meilleurs FA par ROS et gain vs mon pire joueur à la même position (hors IR). Seule la ROS compte :
    les points déjà faits par un FA ne me reviennent pas. Attention : un blessé sans date de retour a une ROS
    pleine (aucun match manqué connu), d'où le statut et la date à côté."""
    rostered = {p["espn_id"] for t in league["teams"] for p in t["roster"]}
    mine = next(t for t in league["teams"] if t["team_id"] == team_id)
    worst = {}
    for p in mine["roster"]:
        pos, r = pos_group(p["pos"]), _ros(p, priors, schedule, today)
        if p["slot"] != "IR" and r and pos in LINEUP and (pos not in worst or r["mean"] < worst[pos]["ros"]["mean"]):
            worst[pos] = {"espn_id": p["espn_id"], "name": p["name"], "ros": r}
    pool = {pos: [] for pos in LINEUP}
    for p in players:
        pos = pos_group(p["pos"])
        if p["espn_id"] in rostered or pos not in pool or not (r := _ros(p, priors, schedule, today)):
            continue
        gain = _round(r["mean"] - worst[pos]["ros"]["mean"]) if pos in worst else None
        pool[pos].append({"espn_id": p["espn_id"], "name": p["name"], "pos": p["pos"], "team": p["pro_team"],
                          "status": p["injury_status"], "expected_return": p.get("expected_return"),
                          "games_missed": rules.games_missed(p, schedule, today), "pct_owned": p.get("pct_owned"),
                          "ros": r, "gain": gain})
    used = mine.get("acquisitions")
    return {
        "moves_left": None if used is None else max(config.FA_MOVES - used, 0),
        "worst": worst,
        "players": {pos: sorted(fa, key=lambda f: -f["ros"]["mean"])[:FA_SHOWN[pos]] for pos, fa in pool.items()},
    }


def standings(league: dict, team_id: int, schedule: list[dict], priors: dict[int, dict], today: date,
              seed: int = 0) -> list[dict]:
    """Total final projeté de chaque équipe : ses points + la ROS de son meilleur alignement (10 F, 5 D),
    joueurs de l'IR compris (à leur retour, ils remplacent le pire). Gardiens ignorés.
    P(1er) par simulation, chaque joueur ~ normale ajustée à son p10-p90, indépendants."""
    rows = []
    for team in league["teams"]:
        by_pos = {pos: [] for pos in LINEUP}
        for p in team["roster"]:
            pos, r = pos_group(p["pos"]), _ros(p, priors, schedule, today)
            if pos in by_pos and r:
                by_pos[pos].append(r)
        lineup = [r for pos, rs in by_pos.items() for r in sorted(rs, key=lambda r: -r["mean"])[:LINEUP[pos]]]
        mean = (team.get("points") or 0) + sum(r["mean"] for r in lineup)
        sd = math.sqrt(sum(((r["p90"] - r["p10"]) / (2 * Z90)) ** 2 for r in lineup))
        rows.append({"team_id": team["team_id"], "abbrev": team.get("abbrev"), "name": team.get("name"),
                     "mine": team["team_id"] == team_id, "points": team.get("points") or 0,
                     "ros": _round(mean - (team.get("points") or 0)), "final": _round(mean), "sd": sd})
    rng = random.Random(seed)
    wins = [0] * len(rows)
    for _ in range(SIMULATIONS):
        totals = [rng.gauss(r["final"], r["sd"]) for r in rows]
        wins[totals.index(max(totals))] += 1
    for r, w in zip(rows, wins, strict=True):
        sd = r.pop("sd")
        r.update(p10=_round(r["final"] - Z90 * sd), p90=_round(r["final"] + Z90 * sd),
                 p_first=round(w / SIMULATIONS, 3))
    return sorted(rows, key=lambda r: -r["final"])


def build(league: dict | None, team_id: int, schedule: list[dict], priors: dict[int, dict], today: date,
          alerts: list[Event], players: list[dict] | None = None) -> dict:
    """`players` : le bassin public ESPN (pour les FA)."""
    team = next((t for t in (league or {}).get("teams", []) if t["team_id"] == team_id), None)
    cards = [card(p, priors.get(p["espn_id"]), schedule, today) for p in (team or {}).get("roster", [])]
    cards.sort(key=lambda c: (SLOT_ORDER.get(c["slot"], 9), -((c["final"] or {}).get("mean") or 0)))
    return {
        "day": today.isoformat(),
        "team": {"id": team_id, "name": team.get("name")} if team else None,
        "alerts": [{"kind": e.kind, "message": e.message, "priority": e.priority} for e in alerts],
        "players": cards,
        "injuries": injuries(league, team_id, schedule, priors, today) if team else [],
        "free_agents": free_agents(league, team_id, players or [], schedule, priors, today) if team else None,
        "standings": standings(league, team_id, schedule, priors, today) if team else [],
    }


def write(data: dict) -> None:
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
