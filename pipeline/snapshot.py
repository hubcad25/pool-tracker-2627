"""Snapshots quotidiens : data/season/YYYY-MM-DD/{league,injuries}.json."""
import json
from datetime import date
from pathlib import Path

from pipeline import config


def write(day: date, name: str, data) -> Path:
    path = config.SEASON_DIR / day.isoformat() / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    return path


def previous_day(day: date) -> date | None:
    """Le snapshot le plus récent avant `day`."""
    days = sorted(p.name for p in config.SEASON_DIR.glob("????-??-??") if p.name < day.isoformat())
    return date.fromisoformat(days[-1]) if days else None


def read(day: date, name: str):
    path = config.SEASON_DIR / day.isoformat() / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None
