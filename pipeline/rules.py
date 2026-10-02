"""Règles de la phase 1 : statut, date de retour et activation IR des joueurs de mon équipe.

Chaque règle compare le snapshot de la veille à celui du jour. Pas de snapshot la veille → pas d'événement.
"""
from datetime import date
from functools import cache

from model import ros as model_ros
from pipeline.events import HIGH, Event
from pipeline.ids import ESPN_TO_NHL_TEAM, pos_group

STATUS_LABELS = {"DAY_TO_DAY": "DTD", "OUT": "OUT", "INJURY_RESERVE": "IR", "SUSPENSION": "suspendu"}
INJURY_FR = {
    "Upper Body": "haut du corps", "Lower Body": "bas du corps", "Shoulder": "épaule", "Knee": "genou",
    "Ankle": "cheville", "Hand": "main", "Wrist": "poignet", "Foot": "pied", "Groin": "aine", "Hip": "hanche",
    "Back": "dos", "Neck": "cou", "Head": "tête", "Concussion": "commotion", "Illness": "maladie",
    "Personal": "raisons personnelles", "Undisclosed": "non divulguée",
}
MONTHS = ["janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"]
# Statuts qui ne permettent plus de rester dans un slot IR
ACTIVABLE = {"ACTIVE", "DAY_TO_DAY"}
RETURN_SHIFT_MIN_GAMES = 3
DROP_OPTIONS = 3


def my_roster(league: dict | None, team_id: int) -> dict[int, dict]:
    if not league:
        return {}
    team = next((t for t in league["teams"] if t["team_id"] == team_id), None)
    return {p["espn_id"]: p for p in team["roster"]} if team else {}


def _team_games(player: dict, schedule: list[dict], start: date, end: str | None = None) -> int:
    team = ESPN_TO_NHL_TEAM.get(player["pro_team"], player["pro_team"])
    start_iso = start.isoformat()
    return sum(1 for g in schedule
               if g["team"] == team and start_iso <= g["date"] and (end is None or g["date"] < end))


def games_missed(player: dict, schedule: list[dict], today: date) -> int | None:
    """Matchs de son équipe d'ici la date de retour prévue. None si la date est inconnue."""
    if player.get("out_for_season"):
        return _team_games(player, schedule, today)
    if not player.get("expected_return"):
        return None
    return _team_games(player, schedule, today, player["expected_return"])


def _short_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]}"


def _short_name(player: dict) -> str:
    return player["name"].split(" ", 1)[-1]


def describe(player: dict, missed: int | None) -> str:
    status = STATUS_LABELS.get(player["injury_status"], player["injury_status"])
    injury = player.get("injury_type")
    head = f"{_short_name(player)} → {status}"
    if injury and player["injury_status"] != "SUSPENSION":
        head += f" ({INJURY_FR.get(injury, injury.lower())})"
    if player.get("out_for_season"):
        return f"{head}, saison terminée"
    if player.get("expected_return"):
        return f"{head}, retour ~{_short_date(player['expected_return'])}, manque {missed} matchs"
    return f"{head}, retour inconnu"


def status_changes(prev: dict[int, dict], cur: dict[int, dict], schedule: list[dict], today: date) -> list[Event]:
    out = []
    for espn_id, p in cur.items():
        old = prev.get(espn_id)
        # Nouveau dans mon équipe : je viens de le prendre, je connais son statut.
        # Slot IR : seule son activation compte (règle activations).
        if old is None or old["injury_status"] == p["injury_status"] or p["slot"] == "IR":
            continue
        # Retour au jeu d'un joueur déjà dans mon alignement : aucune décision à prendre
        if p["injury_status"] == "ACTIVE":
            continue
        missed = games_missed(p, schedule, today)
        # DTD sans match manqué connu : du bruit
        if p["injury_status"] == "DAY_TO_DAY" and not missed:
            continue
        key = f"status:{espn_id}:{p['injury_status']}:{p.get('expected_return')}"
        out.append(Event("status", key, describe(p, missed)))
    return out


def return_date_changes(prev: dict[int, dict], cur: dict[int, dict], schedule: list[dict],
                        today: date) -> list[Event]:
    out = []
    for espn_id, p in cur.items():
        old = prev.get(espn_id)
        if (old is None or p["injury_status"] == "ACTIVE" or old["injury_status"] != p["injury_status"]
                or not (old.get("expected_return") and p.get("expected_return"))
                or old["expected_return"] == p["expected_return"]):
            continue
        before = games_missed(old | {"pro_team": p["pro_team"]}, schedule, today)
        after = games_missed(p, schedule, today)
        shift = after - before
        if abs(shift) < RETURN_SHIFT_MIN_GAMES:
            continue
        verb = "repoussé" if shift > 0 else "devancé"
        msg = (f"{_short_name(p)} : retour {verb} au ~{_short_date(p['expected_return'])} "
               f"(était ~{_short_date(old['expected_return'])}), manque {after} matchs")
        out.append(Event("return_date", f"return:{espn_id}:{p['expected_return']}", msg))
    return out


@cache
def ros_params() -> dict:
    return model_ros.load_params()


def ros(player: dict, prior: dict | None, schedule: list[dict], today: date) -> tuple[float, float, float] | None:
    """ROS (moyenne, p10, p90). `prior` : le prior préseason, avec les stats de la saison (`obs`) et
    les totaux de carrière (`career`) quand on les a. Pas de ROS pour les gardiens."""
    pos = pos_group(player["pos"])
    if not prior or not prior.get("gp") or pos == "G":
        return None
    games = max(_team_games(player, schedule, today) - (games_missed(player, schedule, today) or 0), 0)
    return model_ros.ros(prior["sim_mean"] / prior["gp"], prior.get("obs"), prior.get("career"), games, pos,
                         ros_params())


def _fmt_ros(player: dict, r: tuple | None) -> str:
    if r is None:
        return f"{_short_name(player)} : ROS ?"
    return f"{_short_name(player)} : ROS {r[0]:.0f} ({r[1]:.0f}-{r[2]:.0f})"


def activations(prev: dict[int, dict], cur: dict[int, dict], schedule: list[dict], priors: dict[int, dict],
                today: date) -> list[Event]:
    """Un joueur de mon slot IR n'y est plus admissible → les meilleures options de drop à sa position."""
    out = []
    for espn_id, p in cur.items():
        old = prev.get(espn_id)
        if (p["slot"] != "IR" or p["injury_status"] not in ACTIVABLE
                or old is None or old["injury_status"] in ACTIVABLE):
            continue
        candidates = [c for c in cur.values() if c["slot"] != "IR" and pos_group(c["pos"]) == pos_group(p["pos"])]
        ranked = sorted(((c, ros(c, priors.get(c["espn_id"]), schedule, today)) for c in candidates),
                        key=lambda cr: -1 if cr[1] is None else cr[1][0])
        msg = f"{_short_name(p)} activable"
        if ranked:
            msg += ". Meilleures options de drop :" + "".join(
                f"\n{i}. {_fmt_ros(*cr)}" for i, cr in enumerate(ranked[:DROP_OPTIONS], 1))
        out.append(Event("activation", f"activation:{espn_id}:{today.isoformat()}", msg, HIGH))
    return out


def evaluate(prev_league: dict | None, league: dict | None, team_id: int, schedule: list[dict],
             priors: dict[int, dict], today: date) -> list[Event]:
    prev, cur = my_roster(prev_league, team_id), my_roster(league, team_id)
    if not prev or not cur:
        return []
    return (status_changes(prev, cur, schedule, today)
            + return_date_changes(prev, cur, schedule, today)
            + activations(prev, cur, schedule, priors, today))
