"""Projection ROS : rythme (P/GP) × GP restants. Le même code sert au backtest et en production.

Rythme = (k × prior + points observés) / (k + GP observés), avec des points observés en partie
ajustés pour la chance (poids w) :
- buts : ixG × finition de carrière (G / ixG) ;
- passes : × sh% des coéquipiers sur la glace en carrière / sh% des coéquipiers cette saison.
Les taux de carrière sont régressés vers la moyenne (finition 1, sh% des coéquipiers de la ligue) avec le poids
GP / (GP + m) : une recrue est un finisseur moyen.

Les paramètres (k, w, m par position, quantiles des résidus, sh% des coéquipiers de la ligue) sont estimés
par le backtest et lus dans model/params.json.

Stats attendues (dict) : gp, g, a, ixg, sog, on_goals, on_sog (situation « all »).
"""
import csv
import json
from bisect import bisect_right
from pathlib import Path

PARAMS_PATH = Path(__file__).resolve().parent / "params.json"
CAREER_PATH = Path(__file__).resolve().parent.parent / "priors" / "career.csv"   # 2023-24 à 2025-26, figé
MARCEL_WEIGHTS = (5, 4, 3)       # saison précédente d'abord


def _f(x: str | None) -> float:
    return float(x) if x else 0.0


def from_moneypuck(row: dict) -> dict:
    """Ligne MoneyPuck (résumé de saison ou match, situation « all ») → stats du modèle."""
    g, a = _f(row["I_F_goals"]), _f(row["I_F_primaryAssists"]) + _f(row["I_F_secondaryAssists"])
    return {"gp": _f(row.get("games_played", "1")), "g": g, "a": a, "points": g + a,
            "ixg": _f(row["I_F_xGoals"]), "sog": _f(row["I_F_shotsOnGoal"]),
            "on_goals": _f(row["OnIce_F_goals"]), "on_sog": _f(row["OnIce_F_shotsOnGoal"])}


def load_career(path: Path = CAREER_PATH) -> dict[int, dict]:
    return {int(r["nhl_id"]): {k: float(v) for k, v in r.items() if k not in ("nhl_id", "name")}
            for r in csv.DictReader(path.open())}


def marcel_rate(seasons: list[dict], age: float | None, age_slope: float, age_peak: float) -> float | None:
    """P/GP des 3 saisons précédentes (la plus récente d'abord), pondéré 5/4/3 et par les GP."""
    num = sum(w * s["points"] for w, s in zip(MARCEL_WEIGHTS, seasons, strict=False))
    den = sum(w * s["gp"] for w, s in zip(MARCEL_WEIGHTS, seasons, strict=False))
    if den == 0:
        return None
    factor = 1.0 if age is None else 1 + age_slope * (age_peak - age)
    return num / den * factor


def teammate_sh(s: dict) -> float | None:
    """sh% des coéquipiers quand le joueur est sur la glace (sans ses propres tirs ni buts)."""
    shots = s["on_sog"] - s["sog"]
    return (s["on_goals"] - s["g"]) / shots if shots > 0 else None


def luck_adjusted_points(obs: dict, career: dict | None, m: float, league_sh: float) -> float:
    """Points observés si la finition et le sh% des coéquipiers avaient été ceux de la carrière,
    régressés vers la moyenne selon les GP de carrière."""
    weight = career["gp"] / (career["gp"] + m) if career and career["gp"] else 0.0
    finishing, past_sh = 1.0, league_sh
    if weight:
        if career["ixg"] > 0:
            finishing = weight * career["g"] / career["ixg"] + (1 - weight)
        if (sh := teammate_sh(career)) is not None:
            past_sh = weight * sh + (1 - weight) * league_sh
    cur_sh = teammate_sh(obs)
    assists = obs["a"] * past_sh / cur_sh if cur_sh else obs["a"]
    return obs["ixg"] * finishing + assists


def rate(prior: float, obs: dict | None, luck_points: float | None, k: float, w: float) -> float:
    """`luck_points` : luck_adjusted_points(obs, ...), ou None si w = 0."""
    if not obs or obs["gp"] == 0:
        return prior
    points = obs["g"] + obs["a"]
    if w:
        points = (1 - w) * points + w * luck_points
    return (k * prior + points) / (k + obs["gp"])


def interval(mean_rate: float, games_left: float, quantiles: dict) -> tuple[float, float, float]:
    """(moyenne, p10, p90) des points ROS, à partir des ratios réel / prédit du backtest.

    quantiles = {"rates": [bornes des tranches de rythme prédit], "games": [bornes des tranches de GP restants],
                 "q10": [[...] par tranche de GP] par tranche de rythme, "q90": idem}
    """
    i = max(bisect_right(quantiles["rates"], mean_rate) - 1, 0)
    j = max(bisect_right(quantiles["games"], games_left) - 1, 0)
    mean = mean_rate * games_left
    return mean, mean * quantiles["q10"][i][j], mean * quantiles["q90"][i][j]


def load_params(path: Path = PARAMS_PATH) -> dict:
    return json.loads(path.read_text())


def ros(prior: float, obs: dict | None, career: dict | None, games_left: float, position: str,
        params: dict) -> tuple[float, float, float]:
    p = params[position]
    luck = luck_adjusted_points(obs, career, p["m"], params["league_teammate_sh"]) if obs else None
    return interval(rate(prior, obs, luck, p["k"], p["w"]), games_left, p["quantiles"])
