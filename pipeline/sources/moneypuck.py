"""MoneyPuck : stats avancées de la saison, mises à jour chaque nuit."""
import csv
import io

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
