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
ESPN_SEASON = 2027        # ESPN identifie la saison par l'année de fin
NHL_SEASON = "20262027"
MONEYPUCK_SEASON = 2026   # MoneyPuck l'identifie par l'année de début

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
