"""Backtest du rythme ROS sur 2022-23 à 2025-26 : compare les candidats, écrit model/params.json
et backtest/report.md.

    uv run python -m backtest.run

Candidats (tous des cas particuliers de model.ros.rate) :
1. prior seulement (k infini)   2. observé seulement (k = 0)
3. mélange prior + observé (k optimisé, w = 0)   4. mélange avec observé ajusté pour la chance (k, w et m optimisés)
5, 5b, 6. le 4 avec un prior ajusté au rôle (TOI hors PP et PP) : observé, récent, parfait. Non retenus (ADR 0001).

Le prior est un Marcel (pas de projections préseason historiques). Les recrues (aucun match dans les
3 saisons précédentes) sont exclues : en production, le consensus leur donne un vrai prior.
Le modèle ne prédit pas les blessures : on évalue le rythme sur les matchs réellement joués après la coupure.
k, w et m sont choisis par validation croisée « une saison de côté ».
"""
import csv
import itertools
import json
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

from backtest.fetch import BACKTEST_SEASONS, CACHE, GAMES_DIR, summary_path
from model import ros

CUTOFFS = (10, 20, 30, 41, 60)          # matchs d'équipe joués
MIN_GAMES_LEFT = 10                     # pour entrer dans l'évaluation
GAME_BUCKETS = [0, 20, 40, 60]          # tranches de GP restants pour les intervalles
RATE_BUCKETS = [0, 0.3, 0.5, 0.7]       # tranches de rythme prédit (P/GP) pour les intervalles
K_GRID = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 130, 160, 200]
W_GRID = [i / 10 for i in range(11)]
M_GRID = [0, 50, 100, 200, 400, 800, 1600, 10**6]   # GP de carrière pour peser autant que la moyenne de la ligue
TOP = 250
REPORT = Path(__file__).resolve().parent / "report.md"
STAT_KEYS = ("gp", "g", "a", "ixg", "sog", "on_goals", "on_sog", "toi", "pp_toi")
RECENT_GAMES = 5                                       # « rôle récent » : substitut des trios DailyFaceoff
B_EV_GRID = [0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08]          # P/GP par minute de plus par match, hors PP
B_PP_GRID = [0, 0.03, 0.06, 0.09, 0.12, 0.15, 0.2]     # idem, en avantage numérique


def pos_group(pos: str) -> str:
    return "D" if pos.upper().startswith("D") else "F"


def _with_pp(rows: list[dict], key: str) -> dict[str, dict]:
    """Ligne « all » de chaque clé, avec le TOI en avantage numérique (ligne 5on4) dans `pp_toi`."""
    out, pp = {}, {}
    for r in rows:
        if r["situation"] == "all":
            out[r[key]] = r
        elif r["situation"] == "5on4":
            pp[r[key]] = float(r["icetime"] or 0)
    return {k: r | {"pp_toi": pp.get(k, 0.0)} for k, r in out.items()}


def _stats(r: dict) -> dict:
    return ros.from_moneypuck(r) | {"pp_toi": r["pp_toi"]}


def load_summaries() -> dict[int, dict[str, dict]]:
    return {season: {pid: _stats(r) for pid, r in _with_pp(list(csv.DictReader(summary_path(season).open())),
                                                            "playerId").items()}
            for season in range(min(BACKTEST_SEASONS) - 3, max(BACKTEST_SEASONS))}


def load_birthdates() -> dict[str, date]:
    return {r["playerId"]: date.fromisoformat(r["birthDate"])
            for r in csv.DictReader((CACHE / "birthdates.csv").open())}


def load_games(season: int) -> dict[str, list[dict]]:
    """Matchs de la saison par joueur, triés par date."""
    out = {}
    for path in GAMES_DIR.glob("*.csv"):
        rows = [r for r in csv.DictReader(path.open()) if int(r["season"]) == season]
        if rows:
            out[path.stem] = sorted(_with_pp(rows, "gameId").values(), key=lambda r: r["gameDate"])
    return out


def cutoff_dates(games: dict[str, list[dict]]) -> dict[int, str]:
    """Pour chaque coupure, la date médiane (sur les équipes) du n-ième match d'équipe."""
    team_games = defaultdict(set)
    for rows in games.values():
        for r in rows:
            team_games[r["playerTeam"]].add((r["gameDate"], r["gameId"]))
    out = {}
    for n in CUTOFFS:
        dates = sorted(sorted(g)[n - 1][0] for g in team_games.values() if len(g) >= n)
        out[n] = dates[len(dates) // 2]
    return out


def _sum(rows: list[dict]) -> dict:
    stats = [_stats(r) for r in rows]
    return {k: sum(st[k] for st in stats) for k in (*STAT_KEYS, "points")}


def build_rows() -> list[dict]:
    """Une ligne par (saison, coupure, joueur avec un historique et ≥ MIN_GAMES_LEFT matchs après la coupure)."""
    summaries, born = load_summaries(), load_birthdates()
    rows = []
    for season in BACKTEST_SEASONS:
        games = load_games(season)
        past = [summaries[season - i] for i in (1, 2, 3)]
        for pid, player_games in games.items():
            history = [p.get(pid, {"points": 0.0, "gp": 0.0}) for p in past]
            if sum(h["gp"] for h in history) == 0:
                continue    # recrue
            career = {k: sum(h.get(k, 0.0) for h in history) for k in STAT_KEYS}
            age = (date(season, 10, 1) - born[pid]).days / 365.25 if pid in born else None
            pos = pos_group(player_games[0]["position"])
            for n, day in cutoff_dates(games).items():
                before = [r for r in player_games if r["gameDate"] <= day]
                after = _sum([r for r in player_games if r["gameDate"] > day])
                if after["gp"] < MIN_GAMES_LEFT:
                    continue
                obs = _sum(before)
                rows.append({"season": season, "cutoff": n, "player": pid, "pos": pos, "age": age,
                             "history": history, "career": career, "obs": obs,
                             "gp_left": after["gp"], "rate_left": after["points"] / after["gp"],
                             "toi_left": after["toi"] / after["gp"],
                             "role_ref": _role(history[0] if history[0]["gp"] >= 20 else career),
                             "role_now": _role(obs), "role_recent": _role(_sum(before[-RECENT_GAMES:])),
                             "role_future": _role(after)})
    return rows


def _role(s: dict) -> dict | None:
    """TOI par match, en minutes : hors PP (`ev`) et en avantage numérique (`pp`)."""
    if not s.get("gp"):
        return None
    pp = s["pp_toi"] / s["gp"] / 60
    return {"ev": s["toi"] / s["gp"] / 60 - pp, "pp": pp}


# --- prior Marcel -------------------------------------------------------------------------------

def fit_age(rows: list[dict]) -> tuple[float, float]:
    """Pente et pic de l'ajustement d'âge, sur la saison complète (une ligne par joueur-saison)."""
    full = {(r["season"], r["player"]): r for r in rows if r["cutoff"] == CUTOFFS[0]}.values()
    full = [r for r in full if r["age"] is not None]
    target = {id(r): (r["obs"]["g"] + r["obs"]["a"] + r["rate_left"] * r["gp_left"]) / (r["obs"]["gp"] + r["gp_left"])
              for r in full}

    def err(slope, peak):
        return sum((r["obs"]["gp"] + r["gp_left"])
                   * (ros.marcel_rate(r["history"], r["age"], slope, peak) - target[id(r)]) ** 2 for r in full)

    return min(itertools.product([i / 200 for i in range(0, 9)], [24, 25, 26, 27, 28, 29]), key=lambda p: err(*p))


# --- évaluation ---------------------------------------------------------------------------------

def role_prior(prior: float, role: dict | None, ref: dict | None, b_ev: float, b_pp: float) -> float:
    """Candidats 5-6 (non retenus, voir docs/adr/0001) : prior ajusté au rôle, + b_ev par minute de plus
    par match hors PP, + b_pp par minute de plus en PP.

    role, ref : {"ev": min/match hors PP, "pp": min/match en avantage numérique}, cette saison et l'an passé.
    """
    if not role or not ref:
        return prior
    return max(prior + b_ev * (role["ev"] - ref["ev"]) + b_pp * (role["pp"] - ref["pp"]), 0.0)


def predict(rows: list[dict], k: float | None, w: float, m: float, b_ev: float = 0, b_pp: float = 0,
            role: str = "role_now") -> list[float]:
    """k = None : prior seulement. Les points « sans chance » sont précalculés pour chaque m (r["luck"]).
    role : TOI utilisé pour ajuster le prior (« role_now » observé, « role_future » le vrai reste de saison)."""
    if k is None:
        return [r["prior"] for r in rows]
    return [ros.rate(role_prior(r["prior"], r[role], r["role_ref"], b_ev, b_pp),
                     r["obs"], r["luck"] and r["luck"][m], k, w) for r in rows]


def sse(rows, preds) -> float:
    return sum(r["gp_left"] * (p - r["rate_left"]) ** 2 for r, p in zip(rows, preds, strict=True))


def fit(rows: list[dict], ws: list[float], ms: list[float]) -> tuple[float, float, float]:
    return min(itertools.product(K_GRID, ws, ms), key=lambda kwm: sse(rows, predict(rows, *kwm)))


def fit_role(rows: list[dict], k: float, w: float, m: float, role: str) -> tuple[float, float, float, float, float]:
    b = min(itertools.product(B_EV_GRID, B_PP_GRID),
            key=lambda b: sse(rows, predict(rows, k, w, m, *b, role=role)))
    return k, w, m, *b


def league_teammate_sh() -> float:
    """sh% des coéquipiers sur la glace, toute la ligue, saisons des résumés en cache."""
    seasons = load_summaries().values()
    goals = sum(s["on_goals"] - s["g"] for season in seasons for s in season.values())
    shots = sum(s["on_sog"] - s["sog"] for season in seasons for s in season.values())
    return goals / shots


def pair_accuracy(rows: list[dict], preds: list[float]) -> float:
    """Sur le top 250 (selon le prior) de chaque (saison, coupure) : bon gagnant pour le rythme ROS ?"""
    groups = defaultdict(list)
    for r, p in zip(rows, preds, strict=True):
        groups[(r["season"], r["cutoff"])].append((r, p))
    hits = total = 0
    for members in groups.values():
        top = sorted(members, key=lambda m: -m[0]["prior"])[:TOP]
        for (r1, p1), (r2, p2) in itertools.combinations(top, 2):
            if r1["rate_left"] != r2["rate_left"]:
                total += 1
                hits += (p1 > p2) == (r1["rate_left"] > r2["rate_left"])
    return hits / total


def wrmse(rows, preds) -> float:
    return (sse(rows, preds) / sum(r["gp_left"] for r in rows)) ** 0.5


def quantiles(rows, preds) -> dict:
    """Quantiles 10/90 du ratio points réels / points prédits, par tranche de rythme prédit et de GP restants."""
    out = {"rates": RATE_BUCKETS, "games": GAME_BUCKETS, "q10": [], "q90": []}
    for rlo, rhi in zip(RATE_BUCKETS, [*RATE_BUCKETS[1:], 99], strict=True):
        q10, q90 = [], []
        for glo, ghi in zip(GAME_BUCKETS, [*GAME_BUCKETS[1:], 999], strict=True):
            ratios = sorted(r["rate_left"] / p for r, p in zip(rows, preds, strict=True)
                            if glo <= r["gp_left"] < ghi and rlo <= p < rhi and p > 0)
            q = statistics.quantiles(ratios, n=10)
            q10.append(round(q[0], 3))
            q90.append(round(q[-1], 3))
        out["q10"].append(q10)
        out["q90"].append(q90)
    return out


def coverage(rows, preds, q) -> float:
    inside = 0
    for r, p in zip(rows, preds, strict=True):
        _, lo, hi = ros.interval(p, r["gp_left"], q)
        inside += lo <= r["rate_left"] * r["gp_left"] <= hi
    return inside / len(rows)


CANDIDATES = ["1. prior", "2. observé", "3. mélange", "4. mélange + chance", "5. + rôle observé (saison)",
              "5b. + rôle récent (5 derniers matchs)", "6. + rôle parfait (plafond)"]


def cross_validate(rows: list[dict]) -> dict[str, list[float]]:
    """Prédictions hors échantillon : k, w et m estimés sur les 3 autres saisons."""
    preds = {name: [0.0] * len(rows) for name in CANDIDATES}
    index = {id(r): i for i, r in enumerate(rows)}
    for season in BACKTEST_SEASONS:
        test = [r for r in rows if r["season"] == season]
        for pos in ("F", "D"):
            train = [r for r in rows if r["season"] != season and r["pos"] == pos]
            sub = [r for r in test if r["pos"] == pos]
            luck = fit(train, W_GRID, M_GRID)
            fitted = {"1. prior": ((None, 0.0, 0), "role_now"), "2. observé": ((0, 0.0, 0), "role_now"),
                      "3. mélange": (fit(train, [0.0], [0]), "role_now"), "4. mélange + chance": (luck, "role_now"),
                      "5. + rôle observé (saison)": (fit_role(train, *luck, "role_now"), "role_now"),
                      "5b. + rôle récent (5 derniers matchs)": (fit_role(train, *luck, "role_recent"), "role_recent"),
                      "6. + rôle parfait (plafond)": (fit_role(train, *luck, "role_future"), "role_future")}
            for name, (params, role) in fitted.items():
                for r, p in zip(sub, predict(sub, *params, role=role), strict=True):
                    preds[name][index[id(r)]] = p
    return preds


def main() -> None:
    rows = build_rows()
    slope, peak = fit_age(rows)
    for r in rows:
        r["prior"] = ros.marcel_rate(r["history"], r["age"], slope, peak)
    league_sh = league_teammate_sh()
    for r in rows:
        r["luck"] = {m: ros.luck_adjusted_points(r["obs"], r["career"], m, league_sh) for m in M_GRID} \
            if r["obs"]["gp"] else None
    print(f"{len(rows)} lignes ; âge : pente {slope}, pic {peak} ; sh% des coéquipiers de la ligue {league_sh:.4f}")

    preds = cross_validate(rows)
    lines = ["# Backtest du rythme ROS", "",
             f"Saisons {min(BACKTEST_SEASONS)}-{min(BACKTEST_SEASONS) - 1999} à {max(BACKTEST_SEASONS)}-"
             f"{max(BACKTEST_SEASONS) - 1999}, coupures après {', '.join(map(str, CUTOFFS))} matchs d'équipe, "
             f"{len(rows)} lignes (joueur × coupure, ≥ {MIN_GAMES_LEFT} matchs joués ensuite). "
             f"Prior Marcel 5/4/3 pondéré par les GP, âge : × (1 + {slope} × ({peak} − âge)).",
             "Hors échantillon : k, w et m estimés sans la saison évaluée.", "",
             "Erreur : RMSE du P/GP ROS pondérée par les GP restants. Ordre : % de paires du top 250 "
             "(selon le prior) où le meilleur rythme ROS est bien prédit.", ""]

    lines += ["## Global", "", "| candidat | RMSE P/GP | ordre |", "|---|---|---|"]
    for name, p in preds.items():
        lines.append(f"| {name} | {wrmse(rows, p):.4f} | {pair_accuracy(rows, p):.1%} |")

    lines += ["", "## RMSE P/GP par coupure", "",
              "| candidat | " + " | ".join(f"{n} m" for n in CUTOFFS) + " |",
              "|---|" + "---|" * len(CUTOFFS)]
    for name, p in preds.items():
        cells = []
        for n in CUTOFFS:
            sel = [(r, x) for r, x in zip(rows, p, strict=True) if r["cutoff"] == n]
            cells.append(f"{wrmse(*zip(*sel, strict=True)):.4f}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    # Paramètres finaux : tout l'échantillon, par position ; intervalles sur les prédictions hors échantillon
    best = "4. mélange + chance"
    params = {"age_slope": slope, "age_peak": peak, "league_teammate_sh": round(league_sh, 5)}
    lines += ["", "## Paramètres retenus", "",
              "| position | k | w | m | couverture 80 % : " + " | ".join(f"≥ {b} P/GP" for b in RATE_BUCKETS) + " |",
              "|---|---|---|---|" + "---|" * len(RATE_BUCKETS)]
    for pos in ("F", "D"):
        sub = [(r, x) for r, x in zip(rows, preds[best], strict=True) if r["pos"] == pos]
        sub_rows, sub_preds = (list(t) for t in zip(*sub, strict=True))
        k, w, m = fit(sub_rows, W_GRID, M_GRID)
        q = quantiles(sub_rows, sub_preds)
        params[pos] = {"k": k, "w": w, "m": m, "quantiles": q}
        cells = []
        for lo, hi in zip(RATE_BUCKETS, [*RATE_BUCKETS[1:], 99], strict=True):
            sel = [(r, x) for r, x in zip(sub_rows, sub_preds, strict=True) if lo <= x < hi]
            cells.append(f"{coverage(*(list(t) for t in zip(*sel, strict=True)), q):.1%}")
        lines.append(f"| {pos} | {k} | {w} | {m} | " + " | ".join(cells) + " |")

    ros.PARAMS_PATH.write_text(json.dumps(params, indent=1) + "\n")
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
