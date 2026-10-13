import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
PRIORS_DIR = ROOT / "priors"
SEASON_DIR = ROOT / "data" / "season"
STATE_DIR = ROOT / "data" / "state"

LEAGUE_ID = 1213664531
MY_TEAM_ID = 5
# Matchs joués avant le draft : ESPN ne les ajoutera qu'à la fin de la saison. On ajoute les points tout de suite
# aux points ESPN de chaque équipe (`espn.fetch_league`). À enlever quand ESPN les aura ajoutés.
PRE_DRAFT = {  # team_id : (matchs, points)
    9: (8, 6),     # Laurent Lebrun
    12: (10, 10),  # Eric Chemin
    3: (10, 4),    # Alexis Cuzo
    1: (4, 6),     # Gabriel St-Pierre
    10: (5, 0),    # Ian Manangan
    11: (7, 4),    # Audrey St-Pierre
    2: (11, 4),    # Frederic Bosse
    4: (10, 14),   # Miguel Mathieu-Fernandez
    6: (7, 0),     # Pierre-olivier Gagnon
    5: (9, 4),     # Hubert Cadieux
    7: (9, 5),     # Vincent Lambert
    8: (8, 5),     # Nicolas Lapointe
}
FA_MOVES = 3              # signatures de FA permises pour la saison
ESPN_SEASON = 2027        # ESPN identifie la saison par l'année de fin
NHL_SEASON = "20262027"
MONEYPUCK_SEASON = 2026   # MoneyPuck l'identifie par l'année de début
SEASON_GAMES = 84         # depuis 2026-27

TZ = ZoneInfo("America/Toronto")
DASHBOARD_URL = "https://hubcad25.github.io/pool-tracker-2627/"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Charge .env en local, sans écraser les variables déjà définies (CI)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def env(name: str) -> str | None:
    return os.environ.get(name) or None


def today() -> date:
    """La date à Montréal (le runner GitHub est en UTC)."""
    return datetime.now(TZ).date()
