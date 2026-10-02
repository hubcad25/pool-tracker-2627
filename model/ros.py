"""Projection ROS : rythme (P/GP) × GP restants. Le même code sert au backtest et en production.

Rythme = (k × prior + points observés) / (k + GP observés), avec des points observés en partie
ajustés pour la chance (poids w) :
- buts : ixG × finition de carrière (G / ixG, régressée vers 1) ;
- passes : × sh% des coéquipiers sur la glace en carrière / sh% des coéquipiers cette saison.

Les paramètres (k, w par position, quantiles des résidus) sont estimés par le backtest
et lus dans model/params.json.

Stats attendues (dict) : gp, g, a, ixg, sog, on_goals, on_sog (situation « all »).
"""
import csv
import json
from bisect import bisect_right
from pathlib import Path

PARAMS_PATH = Path(__file__).resolve().parent / "params.json"
CAREER_PATH = Path(__file__).resolve().parent.parent / "priors" / "career.csv"   # 2023-24 à 2025-26, figé
MARCEL_WEIGHTS = (5, 4, 3)       # saison précédente d'abord
FINISHING_SHRINK = 10.0          # en buts : G / ixG de carrière est régressé vers 1 avec ce poids


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


def _teammate_sh(s: dict) -> float | None:
    shots = s["on_sog"] - s["sog"]
    return (s["on_goals"] - s["g"]) / shots if shots > 0 else None


def luck_adjusted_points(obs: dict, career: dict | None) -> float:
    """Points observés si la finition et le sh% des coéquipiers avaient été ceux de la carrière."""
    points = obs["g"] + obs["a"]
    if not career:
        return points
    finishing = (career["g"] + FINISHING_SHRINK) / (career["ixg"] + FINISHING_SHRINK)
    goals = obs["ixg"] * finishing
    cur, past = _teammate_sh(obs), _teammate_sh(career)
    assists = obs["a"] * past / cur if cur and past else obs["a"]
    return goals + assists


def rate(prior: float, obs: dict | None, career: dict | None, k: float, w: float) -> float:
    if not obs or obs["gp"] == 0:
        return prior
    points = (1 - w) * (obs["g"] + obs["a"]) + w * luck_adjusted_points(obs, career)
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
    return interval(rate(prior, obs, career, p["k"], p["w"]), games_left, p["quantiles"])
