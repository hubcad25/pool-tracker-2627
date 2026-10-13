"""Le contexte du match de ce soir : facteur appliqué au rythme de chaque joueur (cotes ESPN et back-to-back).

Calcul : model/soir.py (backtest : backtest/soir.md).
- Buts attendus de chaque équipe ce soir : cotes ESPN (victoire et total de buts) d'avant le match. La job
  quotidienne les garde dans l'historique ; la soirée les y relit (mêmes attendus toute la soirée) et ne va chez
  ESPN que pour les matchs qui manquent.
- Moyenne d'une équipe à ce jour : ses soirs précédents de la saison dans data/state/buts_attendus.json, écrit
  par la job quotidienne (un jour → équipe → [buts attendus pour, contre]).
- Back-to-back : l'équipe a un match la veille dans data/schedule.json.
Sans cotes (ESPN en panne, match sans ligne), le facteur ne garde que le back-to-back.
"""
import json
from datetime import date, timedelta

from model import soir as model
from pipeline import config
from pipeline.sources import espn

HISTORY = config.STATE_DIR / "buts_attendus.json"
LEAGUE_GOALS = 3.1        # buts par équipe et par match, 2022-23 à 2025-26 (tirs de barrage compris)


def expected_goals(games: list[dict]) -> dict[str, tuple[float, float]]:
    """Équipe LNH → (buts attendus pour, contre), d'après les cotes de espn.fetch_game_odds. Matchs commencés
    exclus : la cote d'un match en cours suit le pointage."""
    out = {}
    for g in games:
        if g.get("state", "pre") != "pre":
            continue
        odds = model.game_odds(g["books"])
        if odds:
            home, away = model.split(odds[1], odds[0])
            out[g["home"]], out[g["away"]] = (home, away), (away, home)
    return out


def tonight(day: date) -> dict[str, tuple[float, float]]:
    try:
        return expected_goals(espn.fetch_game_odds(day.isoformat()))
    except Exception as e:  # noqa: BLE001 — les cotes sont un plus : la soirée doit partir sans elles
        print(f"Cotes ESPN inaccessibles ({e}) : facteurs sans les cotes")
        return {}


def load_history() -> dict[str, dict[str, list[float]]]:
    return json.loads(HISTORY.read_text()) if HISTORY.exists() else {}


def record(day: date, goals: dict[str, tuple[float, float]]) -> None:
    """Les buts attendus du jour dans l'historique (ajoutés à ceux déjà gardés pour ce jour)."""
    if not goals:
        return
    history = load_history()
    history[day.isoformat()] = history.get(day.isoformat(), {}) | {t: [round(f, 3), round(a, 3)]
                                                                     for t, (f, a) in goals.items()}
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(dict(sorted(history.items())), indent=0, sort_keys=True) + "\n")


def factors(day: date, goals: dict[str, tuple[float, float]], history: dict[str, dict[str, list[float]]],
            schedule: list[dict]) -> dict[str, tuple[float, float]]:
    """Équipe LNH qui joue ce soir → (facteur patineur, facteur gardien). `history` : les soirs de la saison
    (ceux d'avant `day` comptent)."""
    season_start = date(day.year if day.month >= 8 else day.year - 1, 8, 1).isoformat()
    past = [teams for d, teams in history.items() if season_start <= d < day.isoformat()]
    eve = (day - timedelta(days=1)).isoformat()
    played_eve = {g["team"] for g in schedule if g["date"] == eve}
    playing = {g["team"] for g in schedule if g["date"] == day.isoformat()} | set(goals)
    out = {}
    for team in playing:
        mine = [teams[team] for teams in past if team in teams]
        lam_mean = model.shrunk_mean([f for f, _ in mine], LEAGUE_GOALS)
        opp_mean = model.shrunk_mean([a for _, a in mine], LEAGUE_GOALS)
        lam, lam_opp = goals.get(team, (None, None))
        out[team] = (model.skater_factor(lam, lam_mean, team in played_eve),
                     model.goalie_factor(lam, lam_opp, lam_mean, opp_mean))
    return out


def load_goals(day: date) -> dict[str, tuple[float, float]]:
    """Les buts attendus (pour, contre) gardés pour ce soir, par équipe LNH (vide sans cotes)."""
    return {t: (f, a) for t, (f, a) in load_history().get(day.isoformat(), {}).items()}


def load(day: date, schedule: list[dict], *, save: bool = False) -> dict[str, tuple[float, float]]:
    """Les facteurs de ce soir. `save` : garder les buts attendus du jour (job quotidienne seulement)."""
    history = load_history()
    known = {t: tuple(v) for t, v in history.get(day.isoformat(), {}).items()}
    playing = {g["team"] for g in schedule if g["date"] == day.isoformat()}
    goals = known if known and playing <= set(known) else tonight(day) | known
    if save:
        record(day, goals)
        history = load_history()
    return factors(day, goals, history, schedule)
