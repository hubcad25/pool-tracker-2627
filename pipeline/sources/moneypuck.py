"""MoneyPuck : stats avancées de la saison, mises à jour chaque nuit, et gardiens partants probables du jour."""
import csv
import io
import re
from datetime import date

from pipeline import config
from pipeline.http import get

SEASON_URL = (f"https://moneypuck.com/moneypuck/playerData/seasonSummary/"
              f"{config.MONEYPUCK_SEASON}/regular/skaters.csv")
GAME_BY_GAME_URL = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/regular/skaters/{nhl_id}.csv"


def _csv(url: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(get(url).text)))


def fetch_season_summary() -> list[dict]:
    """Une ligne par (joueur, situation) : all, 5on5, 5on4, 4on5, other."""
    return _csv(SEASON_URL)


def fetch_game_by_game(nhl_id: int) -> list[dict]:
    return _csv(GAME_BY_GAME_URL.format(nhl_id=nhl_id))


STARTERS_URL = "https://moneypuck.com/moneypuck/dates/{day}.htm"
_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_LOGO = re.compile(r"logos/([A-Z]{3})\.png")
_STARTER = re.compile(r"Starter:<BR>([^:<]+):\s*([\d.]+)%")


def parse_starters(page: str) -> dict[str, tuple[str, float]]:
    """Équipe LNH → (nom de famille du partant probable, sa probabilité de commencer) d'après la page du jour.
    Une ligne par match : visiteur à gauche, receveur à droite ; le partant est sous le pourcentage de chaque
    côté (seulement avant le match)."""
    out = {}
    for row in _ROW.findall(page):
        logos = list(_LOGO.finditer(row))
        if len(logos) != 2:
            continue
        sides = {logos[0].group(1): row[:logos[0].start()], logos[1].group(1): row[logos[1].end():]}
        for team, html in sides.items():
            if m := _STARTER.search(html):
                out[team] = (m.group(1).strip(), float(m.group(2)) / 100)
    return out


def fetch_starters(day: date) -> dict[str, tuple[str, float]]:
    return parse_starters(get(STARTERS_URL.format(day=day.strftime("%Y%m%d"))).text)
