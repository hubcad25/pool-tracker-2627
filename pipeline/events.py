"""Événements produits par le pipeline. Chaque règle de notification retourne une liste d'Event."""
from dataclasses import dataclass

# Priorités ntfy : 3 = normale, 4 = haute, 5 = max (son distinct, réservé aux alertes FA)
NORMAL, HIGH, MAX = 3, 4, 5


@dataclass(frozen=True)
class Event:
    kind: str          # status, return_date, activation, fa_alert, digest, health
    key: str           # clé de déduplication : (joueur, type, valeur)
    message: str
    priority: int = NORMAL


def unmatched_ids(missing: list[dict]) -> list[Event]:
    if not missing:
        return []
    names = ", ".join(f"{p['name']} ({'/'.join(p['missing'])})" for p in missing)
    key = "ids:" + ",".join(sorted(f"{p['espn_id']}:{'/'.join(p['missing'])}" for p in missing))
    return [Event("health", key, f"Ids à compléter dans data/id_overrides.csv : {names}")]


def cookies_expired() -> Event:
    return Event("health", "cookies_expired",
                 "Cookies ESPN expirés : remplacer le secret ESPN_S2. Les blessures continuent de fonctionner.",
                 HIGH)


def repeated_failures(n: int) -> Event:
    return Event("health", "failures", f"Le pipeline a échoué {n} fois de suite. Voir GitHub Actions.", HIGH)


def moneypuck_down() -> Event:
    return Event("health", "moneypuck_down",
                 "MoneyPuck indisponible depuis 2 jours : la ROS ignore les stats de la saison.", HIGH)
