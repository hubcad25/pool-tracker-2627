"""data/dashboard.json : tout ce que la PWA affiche, déjà calculé. L'app ne fait aucun calcul de modèle.

- teams_players : les mêmes cartes pour chaque équipe du pool (clé : team_id en texte), moi compris ;
- players : une carte par joueur de mon équipe (points, pace, bande préseason, ROS et total final projeté,
  indicateurs de chance, verdict) ;
- injuries : les blessés de toute la ligue (avec la chance de leur saison) ;
- free_agents : les meilleurs FA selon la ROS, comparés à mon pire joueur à la même position (gain, P(meilleur)) ;
- standings : points actuels + ROS de l'alignement par équipe, P(1er) et son delta par point, chance de la saison.
"""
import json
import math
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
SEASON_GAMES = config.SEASON_GAMES
LINEUP = {"F": 10, "D": 5, "G": 1}
FA_SHOWN = {"F": 10, "D": 5, "G": 5}
Z90 = 1.2816              # p90 d'une normale : l'intervalle p10-p90 fait 2 × Z90 écarts-types
MIN_SD = 1.0              # écart-type plancher d'une équipe sans ROS (évite une densité infinie)
GRID_STEP = 0.1           # pas de l'intégrale de P(1er), en écarts-types de l'équipe la moins incertaine
GRID_SDS = 8              # bornes de l'intégrale : ± 8 écarts-types


def _ratio(num: float, den: float) -> float | None:
    return num / den if den > 0 else None


def _round(x: float | None, n: int = 1) -> float | None:
    return None if x is None else round(x, n)


def _phi(z: float) -> float:
    return math.exp(-z * z / 2) / math.sqrt(2 * math.pi)


def _cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _binom_pmf(k: int, n: int, p: float) -> float:
    if p <= 0 or p >= 1:
        return float(k == (0 if p <= 0 else n))
    return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                    + k * math.log(p) + (n - k) * math.log(1 - p))


def percentile(k: float, n: int, p: float) -> float:
    """Centile mid-p de `k` succès sur `n` essais : P(X < k) + 0,5 P(X = k), X ~ Binomiale(n, p).
    0,5 = conforme ; près de 1 = chanceux ; près de 0 = malchanceux."""
    k = min(max(round(k), 0), n)
    return sum(_binom_pmf(i, n, p) for i in range(k)) + 0.5 * _binom_pmf(k, n, p)


def _sh_luck(goals: float, shots: float, p: float) -> dict | None:
    """Buts vs attendu sur `shots` tirs, au sh% attendu `p`."""
    n = round(shots)
    if n <= 0:
        return None
    p = min(max(p, 0.0), 1.0)
    return {"obs": round(goals), "expected": _round(n * p), "shots": n, "sh_obs": _round(goals / n, 3),
            "sh_expected": _round(p, 3), "percentile": round(percentile(goals, n, p), 3)}


def luck(obs: dict | None, career: dict | None, pos: str) -> dict | None:
    """Indicateurs de chance de la saison. `expected` : les points avec la finition de carrière (saison comprise,
    régressée vers 1) et des coéquipiers qui marquent leurs buts attendus, comme dans la ROS mais sans le poids w.

    Centiles (binomiale, mid-p) sur l'échantillon de la saison : `goals` sur ses tirs, au sh% attendu
    ixG × finition / tirs ; `assists` : buts des coéquipiers quand il est sur la glace, sur leurs tirs,
    au sh% attendu xG des coéquipiers / tirs."""
    if not obs or not obs["gp"] or pos == "G":
        return None
    m = rules.ros_params()[pos]["m"]
    expected = model_ros.luck_adjusted_points(obs, career, m)
    finishing = model_ros.finishing(career, obs, m)
    goals = _sh_luck(obs["g"], obs["sog"], obs["ixg"] * finishing / obs["sog"]) if obs["sog"] else None
    team_goals, team_xg = model_ros.teammate_goals(obs)
    team_shots = obs["on_sog"] - obs["sog"]
    assists = _sh_luck(team_goals, team_shots, team_xg / team_shots) if team_shots > 0 else None
    if assists:
        assists["obs_goals"], assists["expected_goals"] = assists.pop("obs"), assists.pop("expected")
    return {
        "expected_points": _round(expected),
        "net_points": _round(obs["g"] + obs["a"] - expected),
        "goals": goals,
        "assists": assists,
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
    """Gardien : `points` = points de pool (2 W + OTL + SO), avec `w`, `otl`, `so` ; le pace et la bande
    préseason se rapportent aux matchs de son équipe, puisque le prior inclut la part des départs."""
    pos = pos_group(player["pos"])
    obs = (prior or {}).get("obs")
    gp = obs["gp"] if obs else 0
    r = rules.ros(player, prior, schedule, today)
    games_left = rules.games_left(player, schedule, today)
    goalie = {}
    if pos == "G":
        g = a = 0
        goalie = {k: (obs or {}).get(k, 0) for k in ("w", "otl", "so")}
        points = (obs or {}).get("points", 0)
        basis = rules.team_games_played(player, schedule, today)
    else:
        g, a = (obs["g"], obs["a"]) if obs else (0, 0)
        points = g + a
        basis = gp
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
        "gp": gp, "g": g, "a": a, "points": points, **goalie,
        "pace": _round(points / basis * SEASON_GAMES) if basis else None,
        "prior": prior_band(prior, basis + games_left) if r else None,
        "ros_prior": prior_band(prior, games_left) if r else None,
        "ros": {"mean": _round(r[0]), "p10": _round(r[1]), "p90": _round(r[2]),
                "games_left": games_left} if r else None,
        "final": {"mean": _round(points + r[0]), "p10": _round(points + r[1]), "p90": _round(points + r[2])}
        if r else None,
        "luck": indicators,
        "verdict": verdict(gp, points, indicators, pos),
    }


def season(player: dict, prior: dict | None) -> dict:
    """GP, points de la saison, indicateurs de chance et verdict d'un joueur hors de mon équipe (FA, blessés).
    Gardien : pas d'indicateurs de chance (comme mes cartes)."""
    pos = pos_group(player["pos"])
    obs = (prior or {}).get("obs")
    if pos == "G":
        return {"gp": obs["gp"] if obs else 0, "points": (obs or {}).get("points", 0), "luck": None, "verdict": None}
    gp, points = (obs["gp"], obs["g"] + obs["a"]) if obs else (0, 0)
    indicators = luck(obs, (prior or {}).get("career"), pos)
    return {"gp": gp, "points": points, "luck": indicators, "verdict": verdict(gp, points, indicators, pos)}


def p_better(a: dict, b: dict) -> float:
    """P(ROS a > ROS b), normales indépendantes ajustées aux p10-p90 : Φ((μa − μb) / √(σa² + σb²))."""
    sd = math.sqrt(sum(((r["p90"] - r["p10"]) / (2 * Z90)) ** 2 for r in (a, b)))
    if sd == 0:
        return 0.5 if a["mean"] == b["mean"] else float(a["mean"] > b["mean"])
    return _cdf((a["mean"] - b["mean"]) / sd)


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
                **season(p, priors.get(p["espn_id"])),
            })
    out.sort(key=lambda i: (not i["mine"], -((i["ros"] or {}).get("mean") or 0)))
    return out


def free_agents(league: dict, team_id: int, players: list[dict], schedule: list[dict], priors: dict[int, dict],
                today: date) -> dict:
    """Meilleurs FA par ROS et gain vs mon pire joueur à la même position (hors IR), avec `p_better` =
    P(sa ROS dépasse celle de mon pire joueur), et la chance de sa saison (`luck`, `verdict`, comme mes cartes).
    Seule la ROS compte : les points déjà faits par un FA ne me reviennent pas. Attention : un blessé sans date
    de retour a une ROS pleine (aucun match manqué connu), d'où le statut et la date à côté."""
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
        better = round(p_better(r, worst[pos]["ros"]), 3) if pos in worst else None
        pool[pos].append({"espn_id": p["espn_id"], "name": p["name"], "pos": p["pos"], "team": p["pro_team"],
                          "status": p["injury_status"], "expected_return": p.get("expected_return"),
                          "games_missed": rules.games_missed(p, schedule, today), "pct_owned": p.get("pct_owned"),
                          "ros": r, "gain": gain, "p_better": better, **season(p, priors.get(p["espn_id"]))})
    used = mine.get("acquisitions")
    return {
        "moves_left": None if used is None else max(config.FA_MOVES - used, 0),
        "worst": worst,
        "players": {pos: sorted(fa, key=lambda f: -f["ros"]["mean"])[:FA_SHOWN[pos]] for pos, fa in pool.items()},
    }


def first_place_odds(means: list[float], sds: list[float]) -> list[float]:
    """P(1er) de chaque équipe, totaux finaux ~ normales indépendantes :
    P_i = ∫ φ_i(x) ∏_{j≠i} Φ_j(x) dx, par une somme de Riemann sur une grille fine (déterministe)."""
    sds = [max(sd, MIN_SD) for sd in sds]
    lo = min(m - GRID_SDS * sd for m, sd in zip(means, sds, strict=True))
    hi = max(m + GRID_SDS * sd for m, sd in zip(means, sds, strict=True))
    step = GRID_STEP * min(sds)
    odds = [0.0] * len(means)
    for k in range(int((hi - lo) / step) + 1):
        x = lo + (k + 0.5) * step
        zs = [(x - m) / sd for m, sd in zip(means, sds, strict=True)]
        cdfs = [_cdf(z) for z in zs]
        for i, (z, sd) in enumerate(zip(zs, sds, strict=True)):
            density = _phi(z) / sd
            if density < 1e-300:
                continue
            others = math.prod(c for j, c in enumerate(cdfs) if j != i)
            odds[i] += density * others * step
    return odds


def p_first_deltas(means: list[float], sds: list[float], me: int) -> list[float]:
    """Variation de MA P(1er) si chaque équipe fait 1 point de plus (négative pour un rival, positive pour moi)."""
    base = first_place_odds(means, sds)[me]
    return [first_place_odds([m + (j == i) for j, m in enumerate(means)], sds)[me] - base
            for i in range(len(means))]


def team_luck(team: dict, priors: dict[int, dict]) -> float:
    """Chance de la saison d'une équipe : la somme des `net_points` (points réels − attendus sans la chance) des
    patineurs de son alignement actuel (hors IR et gardiens). Les points faits par d'anciens joueurs n'y sont pas."""
    total = 0.0
    for p in team["roster"]:
        pos, prior = pos_group(p["pos"]), priors.get(p["espn_id"]) or {}
        if p["slot"] in ("F", "D") and pos != "G" and (ind := luck(prior.get("obs"), prior.get("career"), pos)):
            total += ind["net_points"]
    return total


def standings(league: dict, team_id: int, schedule: list[dict], priors: dict[int, dict], today: date) -> list[dict]:
    """Total final projeté de chaque équipe : ses points + la ROS de son meilleur alignement (10 F, 5 D, 1 G),
    joueurs de l'IR compris (à leur retour, ils remplacent le pire).
    P(1er) : chaque joueur ~ normale ajustée à son p10-p90, indépendants. `delta_p_first_per_point` : variation de
    MA P(1er) si l'équipe fait 1 point de plus. `luck_points` : voir team_luck."""
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
                     "ros": _round(mean - (team.get("points") or 0)), "final": _round(mean), "sd": sd,
                     "luck_points": _round(team_luck(team, priors))})
    means, sds = [r["final"] for r in rows], [r["sd"] for r in rows]
    odds = first_place_odds(means, sds)
    me = next((i for i, r in enumerate(rows) if r["mine"]), None)
    deltas = p_first_deltas(means, sds, me) if me is not None else [None] * len(rows)
    for r, p, d in zip(rows, odds, deltas, strict=True):
        sd = r["sd"]
        r.update(sd=_round(sd, 2), p10=_round(r["final"] - Z90 * sd), p90=_round(r["final"] + Z90 * sd),
                 ros_p10=_round(r["ros"] - Z90 * sd), ros_p90=_round(r["ros"] + Z90 * sd),
                 p_first=round(p, 3), delta_p_first_per_point=_round(d, 5))
    return sorted(rows, key=lambda r: -r["final"])


def team_cards(team: dict, schedule: list[dict], priors: dict[int, dict], today: date) -> list[dict]:
    """Les cartes d'une équipe du pool (mêmes que les miennes), par slot puis total final projeté."""
    cards = [card(p, priors.get(p["espn_id"]), schedule, today) for p in team.get("roster", [])]
    cards.sort(key=lambda c: (SLOT_ORDER.get(c["slot"], 9), -((c["final"] or {}).get("mean") or 0)))
    return cards


def build(league: dict | None, team_id: int, schedule: list[dict], priors: dict[int, dict], today: date,
          alerts: list[Event], players: list[dict] | None = None) -> dict:
    """`players` : le bassin public ESPN (pour les FA)."""
    team = next((t for t in (league or {}).get("teams", []) if t["team_id"] == team_id), None)
    teams_players = {str(t["team_id"]): team_cards(t, schedule, priors, today) for t in (league or {}).get("teams", [])}
    cards = teams_players.get(str(team_id), [])
    return {
        "day": today.isoformat(),
        "team": {"id": team_id, "name": team.get("name")} if team else None,
        "alerts": [{"kind": e.kind, "message": e.message, "priority": e.priority} for e in alerts],
        "players": cards,
        "teams_players": teams_players,
        "injuries": injuries(league, team_id, schedule, priors, today) if team else [],
        "free_agents": free_agents(league, team_id, players or [], schedule, priors, today) if team else None,
        "standings": standings(league, team_id, schedule, priors, today) if team else [],
    }


def write(data: dict) -> None:
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
