"""Le contexte d'un match à partir des cotes : buts attendus de chaque équipe et points attendus des gardiens.

Cotes américaines (-150, +130). La marge du livre est retirée en normalisant les probabilités implicites.
Buts d'une équipe ~ Poisson, indépendants. Égalité après 60 min : chaque équipe gagne en prolongation à 50 %
(la prolongation est sous-estimée : 16 % prédite, 22 % réelle ; sans effet notable sur les ratios ci-dessous).

Points attendus ce soir = rythme ROS × facteur (backtest : backtest/soir.md, 2022-23 à 2025-26) :
- patineur : (buts attendus de son équipe ce soir ÷ sa moyenne à ce jour) ^ ODDS_EXPONENT, × B2B si son équipe
  a joué la veille. Exposant estimé : 0,62 (×1,86 pour un ratio de e), plus faible en début de saison (0,4 sur
  les 10 premiers matchs, 0,74 après 30) ; arrondi à 0,6. B2B estimé : ×0,953 ;
- gardien : ses points d'équipe attendus ce soir ÷ ceux avec les moyennes de son équipe (pas de b2b : il joue
  surtout sur qui commence, qu'on ne connaît pas).
Moyenne à ce jour : SHRINK matchs fictifs à la moyenne de la ligue, puis les matchs de la saison.
Testés et non retenus : main chaude (5 derniers matchs), b2b de l'adversaire (×1,02).
"""
import math
import statistics

MAX_GOALS = 20
ODDS_EXPONENT = 0.6
B2B = 0.95
SHRINK = 10


def implied(ml: float) -> float:
    """Probabilité implicite d'une cote américaine (marge comprise)."""
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)


def fair(a: float, b: float) -> tuple[float, float] | None:
    """Probabilités sans la marge des deux côtés d'un marché, ou None si les cotes sont incohérentes
    (marge négative ou de plus de 15 % : cote périmée chez ESPN)."""
    pa, pb = implied(a), implied(b)
    if not 1.0 <= pa + pb <= 1.15:
        return None
    return pa / (pa + pb), pb / (pa + pb)


def game_odds(books: list[dict]) -> tuple[float, float] | None:
    """(P(victoire à domicile), total de buts attendu) : médianes sur les livres aux cotes cohérentes. Les livres
    « Live Odds » sont exclus : ESPN y garde la cote de la fin du match.

    books : [{"book", "home_ml", "away_ml", "total", "over", "under"}] (cf. espn.odds_book)."""
    books = [b for b in books if "live" not in b["book"].lower()]
    wins = [f[0] for b in books if b["home_ml"] and b["away_ml"] and (f := fair(b["home_ml"], b["away_ml"]))]
    totals = [total_goals(b["total"], f[0]) for b in books
              if b["total"] and b["over"] and b["under"] and (f := fair(b["over"], b["under"]))]
    if not wins or not totals:
        return None
    return statistics.median(wins), statistics.median(totals)


def pmf(lam: float) -> list[float]:
    p = [math.exp(-lam)]
    for k in range(1, MAX_GOALS + 1):
        p.append(p[-1] * lam / k)
    return p


def p_over(line: float, lam: float) -> float:
    """P(buts > line) pour une ligne en demi (5,5 ; 6,5)."""
    return 1 - sum(pmf(lam)[: math.floor(line) + 1])


def _bisect(f, lo: float, hi: float, target: float) -> float:
    """x dans [lo, hi] tel que f(x) = target, f croissante."""
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < target else (lo, mid)
    return (lo + hi) / 2


def total_goals(line: float, prob_over: float) -> float:
    """Total de buts attendu dans le match qui donne P(plus de `line`) = prob_over."""
    if line == math.floor(line):        # ligne entière : la poussée est remboursée, on décale d'un demi-but
        line -= 0.5
    return _bisect(lambda lam: p_over(line, lam), 0.5, 15.0, prob_over)


def outcomes(lam_a: float, lam_b: float) -> tuple[float, float]:
    """(P(a mène après 60 min), P(égalité après 60 min))."""
    pa, pb = pmf(lam_a), pmf(lam_b)
    lead = sum(pa[i] * pb[j] for i in range(len(pa)) for j in range(i))
    tie = sum(x * y for x, y in zip(pa, pb, strict=True))
    return lead, tie


def p_win(lam_a: float, lam_b: float) -> float:
    lead, tie = outcomes(lam_a, lam_b)
    return lead + tie / 2


def split(total: float, prob_a: float) -> tuple[float, float]:
    """Buts attendus (a, b) : leur somme vaut `total` et a gagne avec la probabilité `prob_a`."""
    share = _bisect(lambda s: p_win(s * total, (1 - s) * total), 0.05, 0.95, prob_a)
    return share * total, (1 - share) * total


def goalie_points(lam_for: float, lam_against: float) -> float:
    """Points de pool attendus des gardiens d'une équipe pour un match : 2 par victoire, 1 par défaite en
    prolongation, 1 par blanchissage."""
    lead, tie = outcomes(lam_for, lam_against)
    return 2 * (lead + tie / 2) + tie / 2 + math.exp(-lam_against)


def shrunk_mean(values: list[float], league: float) -> float:
    return (sum(values) + SHRINK * league) / (len(values) + SHRINK)


def skater_factor(lam: float | None, lam_mean: float, b2b: bool) -> float:
    """`lam` : buts attendus de l'équipe ce soir (None sans cotes) ; `lam_mean` : sa moyenne à ce jour."""
    return (1.0 if lam is None else (lam / lam_mean) ** ODDS_EXPONENT) * (B2B if b2b else 1.0)


def goalie_factor(lam: float | None, lam_opp: float | None, lam_mean: float, lam_opp_mean: float) -> float:
    if lam is None or lam_opp is None:
        return 1.0
    return goalie_points(lam, lam_opp) / goalie_points(lam_mean, lam_opp_mean)
