"""Backtest des points d'un soir, 2022-23 à 2025-26 : écrit backtest/soir.md.

    uv run python -m backtest.soir

Patineurs. Base (le modèle actuel) : le rythme ROS du joueur la veille du match (model.ros.rate, paramètres de
model/params.json ; c'est ROS ÷ matchs restants). Les candidats le multiplient par exp(β · x) : une régression
de Poisson avec log(rythme) en décalage, les β estimés sans la saison évaluée. Signaux x :
- domicile ; défense adverse : log(buts accordés par match de l'adversaire à ce jour / moyenne de la ligue) ;
- back-to-back : l'équipe (ou l'adversaire) a joué la veille ;
- main chaude : points par match des 5 derniers matchs − rythme ;
- cotes : log(buts attendus de l'équipe ce soir selon les cotes / sa moyenne de buts attendus à ce jour).
Erreur : déviance de Poisson moyenne par joueur-match (la log-vraisemblance, à une constante près).

Gardiens : points de pool de l'équipe (2 victoire, 1 défaite en prolongation, 1 blanchissage), constante de la
ligue vs model.soir.goalie_points avec les buts attendus des cotes. Le départ (quel gardien) n'est pas testé.
"""
import json
import math
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from backtest.fetch import BACKTEST_SEASONS, ODDS_PATH
from backtest.run import _stats, career_totals, load_birthdates, load_games, load_summaries, pos_group
from model import ros
from model import soir as model

REPORT = Path(__file__).resolve().parent / "soir.md"
RECENT = 5           # main chaude : derniers matchs
SHRINK = model.SHRINK
MIN_RATE = 0.01
LOG_FEATURES = ("défense adverse", "cotes")      # log d'un ratio : β est un exposant
FEATURES = ("domicile", "défense adverse", "b2b", "b2b adverse", "main chaude", "cotes")
CANDIDATES = {
    "0. actuel": None,
    "1. actuel + calibrage": (),
    "2. + domicile, défense adverse": ("domicile", "défense adverse"),
    "3. + back-to-back": ("b2b", "b2b adverse"),
    "4. + main chaude": ("main chaude",),
    "5. + cotes": ("cotes",),
    "6. cotes + back-to-back": ("cotes", "b2b", "b2b adverse"),
    "7. tout": FEATURES,
}


# --- cotes ----------------------------------------------------------------------------------------

def _team(abbrev: str) -> str:
    """Abréviation MoneyPuck (N.J, L.A) ou ESPN (UTAH) → forme commune."""
    return {"UTAH": "UTA"}.get(abbrev, abbrev.replace(".", ""))


def load_team_games() -> dict[tuple[str, str], dict]:
    """(date AAAAMMJJ, équipe) → contexte du match, calculé avec ce qui était connu avant le match."""
    games = {}
    for line in ODDS_PATH.open():
        g = json.loads(line)
        if g["espn_id"]:
            games[g["espn_id"]] = g
    rows = []
    for g in games.values():
        odds = model.game_odds(g["books"])
        lam = model.split(odds[1], odds[0]) if odds else (None, None)
        for side, other, i in (("home", "away", 0), ("away", "home", 1)):
            rows.append({"day": g["day"], "team": _team(g[side]), "opp": _team(g[other]), "home": side == "home",
                         "gf": g[f"{side}_goals"], "ga": g[f"{other}_goals"], "ot": (g["periods"] or 3) > 3,
                         "lam": lam[i], "lam_opp": lam[1 - i]})
    league_goals = statistics.mean(r["gf"] for r in rows)
    league_lam = statistics.mean(r["lam"] for r in rows if r["lam"])
    by_team = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["day"]):
        by_team[(_season(r["day"]), r["team"])].append(r)
    played = {(r["day"], r["team"]) for r in rows}
    ga_before = {}
    for team_rows in by_team.values():
        ga = lam_sum = 0.0
        n_lam = 0
        for n, r in enumerate(team_rows):
            ga_before[(r["day"], r["team"])] = (ga + SHRINK * league_goals) / (n + SHRINK)
            r["lam_mean"] = (lam_sum + SHRINK * league_lam) / (n_lam + SHRINK)
            r["n"] = n
            ga += r["ga"]
            if r["lam"]:
                lam_sum, n_lam = lam_sum + r["lam"], n_lam + 1
    out = {}
    for r in rows:
        eve = (date.fromisoformat(r["day"]) - timedelta(days=1)).isoformat()
        r |= {"b2b": (eve, r["team"]) in played, "opp_b2b": (eve, r["opp"]) in played,
              "opp_ga": ga_before[(r["day"], r["opp"])] / league_goals}
        out[(r["day"].replace("-", ""), r["team"])] = r
    return out


def _season(day: str) -> int:
    d = date.fromisoformat(day)
    return d.year if d.month >= 8 else d.year - 1


# --- patineurs ------------------------------------------------------------------------------------

def build_rows(team_games: dict) -> list[dict]:
    """Une ligne par joueur-match (joueurs avec un historique, comme le backtest ROS)."""
    params, summaries, born = ros.load_params(), load_summaries(), load_birthdates()
    rows, missing = [], 0
    for season in BACKTEST_SEASONS:
        past = [summaries[season - i] for i in (1, 2, 3)]
        for pid, games in load_games(season).items():
            history = [p.get(pid, {"points": 0.0, "gp": 0.0}) for p in past]
            if sum(h["gp"] for h in history) == 0:
                continue    # recrue
            age = (date(season, 10, 1) - born[pid]).days / 365.25 if pid in born else None
            prior = ros.marcel_rate(history, age, params["age_slope"], params["age_peak"])
            pos = params[pos_group(games[0]["position"])]
            career = career_totals(summaries, pid, season)
            obs, points = None, []
            for g in games:
                st = _stats(g)
                luck = ros.luck_adjusted_points(obs, career, pos["m"]) if obs else None
                rate = max(ros.rate(prior, obs, luck, pos["k"], pos["w"]), MIN_RATE)
                ctx = team_games.get((g["gameDate"], _team(g["playerTeam"])))
                if ctx is None:
                    missing += 1
                else:
                    hot = sum(points[-RECENT:]) / RECENT - rate if len(points) >= RECENT else 0.0
                    rows.append({"season": season, "n": ctx["n"], "y": st["points"], "rate": rate, "x": {
                        "domicile": 1.0 if ctx["home"] else 0.0, "défense adverse": math.log(ctx["opp_ga"]),
                        "b2b": float(ctx["b2b"]), "b2b adverse": float(ctx["opp_b2b"]), "main chaude": hot,
                        "cotes": math.log(ctx["lam"] / ctx["lam_mean"]) if ctx["lam"] else 0.0}})
                points.append(st["points"])
                obs = st if obs is None else {k: obs[k] + st[k] for k in st}
    print(f"{len(rows)} joueurs-matchs, {missing} sans match ESPN")
    return rows


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Élimination de Gauss (petits systèmes)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c], strict=True)]
    return [m[i][n] / m[i][i] for i in range(n)]


def _design(r: dict, features: tuple) -> list[float]:
    return [1.0, *(r["x"][f] for f in features)]


def fit_poisson(rows: list[dict], features: tuple) -> list[float]:
    """β de la régression de Poisson y ~ rythme × exp(β0 + β · x), par Newton."""
    beta = [0.0] * (len(features) + 1)
    for _ in range(25):
        n = len(beta)
        grad, hess = [0.0] * n, [[0.0] * n for _ in range(n)]
        for r in rows:
            x = _design(r, features)
            mu = r["rate"] * math.exp(sum(b * v for b, v in zip(beta, x, strict=True)))
            for i in range(n):
                grad[i] += x[i] * (r["y"] - mu)
                for j in range(n):
                    hess[i][j] += mu * x[i] * x[j]
        step = _solve(hess, grad)
        beta = [b + s for b, s in zip(beta, step, strict=True)]
        if max(abs(s) for s in step) < 1e-7:
            break
    return beta


def predict(r: dict, features: tuple | None, beta: list[float] | None) -> float:
    if features is None:
        return r["rate"]
    return r["rate"] * math.exp(sum(b * v for b, v in zip(beta, _design(r, features), strict=True)))


def deviance(y: float, mu: float) -> float:
    return 2 * ((y * math.log(y / mu) if y else 0.0) - (y - mu))


def evaluate(rows: list[dict]) -> tuple[dict, dict]:
    """Déviance moyenne hors échantillon par candidat et par saison ; β estimés sur toutes les saisons."""
    dev = {name: {} for name in CANDIDATES}
    for season in BACKTEST_SEASONS:
        train = [r for r in rows if r["season"] != season]
        test = [r for r in rows if r["season"] == season]
        for name, features in CANDIDATES.items():
            beta = fit_poisson(train, features) if features is not None else None
            dev[name][season] = statistics.mean(deviance(r["y"], predict(r, features, beta)) for r in test)
    full = {name: fit_poisson(rows, f) for name, f in CANDIDATES.items() if f is not None}
    return dev, full


# --- gardiens -------------------------------------------------------------------------------------

def goalie_actual(ctx: dict) -> int:
    won = ctx["gf"] > ctx["ga"]
    return 2 * won + (not won and ctx["ot"]) + (ctx["ga"] == 0)


def goalies(team_games: dict) -> dict:
    rows = [r for r in team_games.values() if r["lam"]]
    league = statistics.mean(goalie_actual(r) for r in rows)
    preds = [model.goalie_points(r["lam"], r["lam_opp"]) for r in rows]
    actual = [goalie_actual(r) for r in rows]
    mse = lambda p: statistics.mean((a - x) ** 2 for a, x in zip(actual, p, strict=True))  # noqa: E731
    bins = defaultdict(list)
    for p, a in zip(preds, actual, strict=True):
        bins[min(int(p * 5) / 5, 1.6)].append((p, a))
    return {"n": len(rows), "league": league, "mse_league": mse([league] * len(rows)), "mse_odds": mse(preds),
            "calibration": [(b, len(v), statistics.mean(p for p, _ in v), statistics.mean(a for _, a in v))
                            for b, v in sorted(bins.items())],
            "lam_vs_goals": (statistics.mean(r["lam"] for r in rows), statistics.mean(r["gf"] for r in rows)),
            "ot": (statistics.mean(model.outcomes(r["lam"], r["lam_opp"])[1] for r in rows),
                   statistics.mean(r["ot"] for r in rows))}


# --- rapport --------------------------------------------------------------------------------------

def report(rows: list[dict], dev: dict, full: dict, g: dict) -> str:
    seasons = list(BACKTEST_SEASONS)
    base = dev["0. actuel"]
    with_odds = sum(r["x"]["cotes"] != 0 for r in rows) / len(rows)
    out = ["# Backtest des points d'un soir", "",
           f"Saisons 2022-23 à 2025-26, {len(rows)} joueurs-matchs (patineurs avec un historique), "
           f"{with_odds:.0%} avec des cotes. Hors échantillon : β estimés sans la saison évaluée.", "",
           "Δ : variation de la déviance de Poisson moyenne vs le modèle actuel (négatif = mieux).", "",
           "| candidat | déviance | Δ global | " + " | ".join(f"Δ {s}-{s - 1999}" for s in seasons) + " |",
           "|---|---|---|" + "---|" * len(seasons)]
    for name in CANDIDATES:
        mean = statistics.mean(dev[name].values())
        cells = " | ".join(f"{(dev[name][s] / base[s] - 1):+.2%}" for s in seasons)
        out.append(f"| {name} | {mean:.5f} | {mean / statistics.mean(base.values()) - 1:+.2%} | {cells} |")
    out += ["", "## Effets estimés (toutes les saisons)", "",
            "× : multiplicateur des points attendus (domicile, b2b : oui vs non ; main chaude : +1 pt/match "
            "au-dessus du rythme). ^ : exposant du ratio (défense adverse, cotes).", "",
            "| candidat | calibrage | " + " | ".join(FEATURES) + " |", "|---|---|" + "---|" * len(FEATURES)]
    for name, beta in full.items():
        feats = CANDIDATES[name]
        cells = [("" if f not in feats else f"^{beta[1 + feats.index(f)]:.2f}" if f in LOG_FEATURES
                  else f"×{math.exp(beta[1 + feats.index(f)]):.3f}") for f in FEATURES]
        out.append(f"| {name} | ×{math.exp(beta[0]):.3f} | " + " | ".join(cells) + " |")
    lam, goals = g["lam_vs_goals"]
    out += ["", "## Gardiens", "",
            f"{g['n']} matchs-équipes avec cotes. Points de pool des gardiens d'une équipe par match : "
            f"{g['league']:.3f} en moyenne.", "",
            f"- Erreur quadratique : constante {g['mse_league']:.4f}, cotes {g['mse_odds']:.4f} "
            f"({g['mse_odds'] / g['mse_league'] - 1:+.1%}).",
            f"- Buts attendus selon les cotes : {lam:.3f} par équipe (réels : {goals:.3f}, tirs de barrage compris).",
            f"- Prolongation : {g['ot'][0]:.1%} prédite (Poisson), {g['ot'][1]:.1%} réelle.", "",
            "| prédit | matchs | prédit moyen | réel moyen |", "|---|---|---|---|"]
    out += [f"| {b:.1f}+ | {n} | {p:.3f} | {a:.3f} |" for b, n, p, a in g["calibration"]]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    team_games = load_team_games()
    rows = build_rows(team_games)
    dev, full = evaluate(rows)
    REPORT.write_text(report(rows, dev, full, goalies(team_games)))
    print(REPORT.read_text())
