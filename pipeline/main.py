"""Exécution quotidienne.

uv run python -m pipeline.main                  # dry-run : imprime la notif sans l'envoyer
uv run python -m pipeline.main --send --target prod
uv run python -m pipeline.main --scenario activation --send   # notif fictive, ne touche à aucun état
"""
import argparse
import copy
import json
from datetime import date, timedelta

import requests

from model import ros
from pipeline import config, dashboard, events, ids, notify, rules, snapshot
from pipeline.http import AuthError
from pipeline.sources import espn, moneypuck, nhl

HEALTH = config.STATE_DIR / "health.json"
MONEYPUCK_HEALTH = config.STATE_DIR / "moneypuck.json"
FAILURES_BEFORE_ALERT = 2
# Sous ce seuil, un joueur absent des rosters LNH est presque toujours un espoir de la AHL
MIN_PCT_OWNED_SEARCH = 1.0


def run(day: date) -> list[events.Event]:
    out: list[events.Event] = []
    players = espn.fetch_players()
    snapshot.write(day, "injuries", [p for p in players if p["injury_status"] != "ACTIVE"])

    league = None
    if not espn.has_cookies():
        print("ESPN_S2/SWID absents : rosters de la ligue ignorés")
    else:
        try:
            league = espn.fetch_league()
        except AuthError:
            out.append(events.cookies_expired())
    if league:
        snapshot.write(day, "league", league)
        notify.forget("cookies_expired")

    rostered = [p for t in (league or {}).get("teams", []) for p in t["roster"]]
    by_id = {p["espn_id"]: p for p in players}
    by_id.update({p["espn_id"]: p for p in rostered})
    rostered_ids = {p["espn_id"] for p in rostered}
    id_map = ids.update_map(
        list(by_id.values()), nhl.fetch_rosters(), search=nhl.search,
        worth_search=lambda p: p["espn_id"] in rostered_ids or p.get("pct_owned", 0) >= MIN_PCT_OWNED_SEARCH,
    )
    out += events.unmatched_ids(ids.missing(id_map, rostered))

    season = season_stats()
    out += moneypuck_health(season is not None)

    schedule = fetch_schedule()
    prev_day = snapshot.previous_day(day)
    prev_league = snapshot.read(prev_day, "league") if prev_day else None
    priors = priors_by_espn(id_map, season or {})
    out += rules.evaluate(prev_league, league, config.MY_TEAM_ID, schedule, priors, day)
    # Sans la ligue du jour (cookies), le dashboard garde les rosters de la veille
    dashboard.write(dashboard.build(league or prev_league, config.MY_TEAM_ID, schedule, priors, day, out))
    return out


def fetch_schedule() -> list[dict]:
    """Calendrier de la saison, aussi gardé dans data/ (sans l'état des matchs, pour des diffs propres)."""
    schedule = [{k: g[k] for k in ("game_id", "date", "team")} for g in nhl.fetch_schedule()]
    (config.ROOT / "data" / "schedule.json").write_text(json.dumps(schedule, indent=0) + "\n")
    return schedule


def priors_by_espn(id_map: dict[int, dict], season: dict[int, dict]) -> dict[int, dict]:
    """Prior préseason de chaque joueur, avec ses stats de la saison (`obs`) et de carrière (`career`) pour la ROS."""
    priors = {p["player_id"]: p for p in json.loads((config.PRIORS_DIR / "priors.json").read_text())}
    career = ros.load_career()
    out = {}
    for espn_id, r in id_map.items():
        if r.get("canonical_id") in priors:
            nhl_id = int(r["nhl_id"]) if r.get("nhl_id") else None
            out[espn_id] = priors[r["canonical_id"]] | {"obs": season.get(nhl_id), "career": career.get(nhl_id)}
    return out


def season_stats() -> dict[int, dict] | None:
    """Stats MoneyPuck de la saison par nhl_id. None en cas de panne : la ROS se rabat alors sur le prior."""
    try:
        rows = moneypuck.fetch_season_summary()
    except requests.RequestException as e:
        print(f"MoneyPuck indisponible ({e}) : ROS sur le prior seulement")
        return None
    return {int(r["playerId"]): ros.from_moneypuck(r) for r in rows if r["situation"] == "all"}


SCENARIOS = ("activation", "status")


def run_scenario(name: str, day: date) -> list[events.Event]:
    """Applique un changement fictif à la ligue du jour et passe les vraies règles dessus.

    Rien n'est écrit (ni snapshot, ni état de déduplication) : on peut le relancer à volonté.
    """
    league = espn.fetch_league()
    fake = copy.deepcopy(league)
    mine = rules.my_roster(fake, config.MY_TEAM_ID)
    if name == "activation":
        target = next(p for p in mine.values() if p["slot"] == "IR")
        target.update(injury_status="ACTIVE", injury_type=None, expected_return=None)
    else:
        target = next(p for p in mine.values() if p["slot"] == "F" and p["injury_status"] == "ACTIVE")
        target.update(injury_status="INJURY_RESERVE", injury_type="Upper Body",
                      expected_return=(day + timedelta(days=21)).isoformat())
    schedule = [{k: g[k] for k in ("game_id", "date", "team")} for g in nhl.fetch_schedule()]
    id_map = ids.resolved(ids.read_map(ids.ID_MAP))
    priors = priors_by_espn(id_map, season_stats() or {})
    evts = rules.evaluate(league, fake, config.MY_TEAM_ID, schedule, priors, day)
    return [events.Event(e.kind, e.key, f"[SCÉNARIO] {e.message}", e.priority) for e in evts]


def _streak(path, ok: bool) -> int:
    """Échecs consécutifs, gardés dans data/state."""
    failures = 0 if ok else (json.loads(path.read_text())["failures"] + 1 if path.exists() else 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"failures": failures, "last_run": config.today().isoformat(), "ok": ok}) + "\n")
    return failures


def _source_health(path, ok: bool, event: events.Event) -> list[events.Event]:
    """Une journée de panne d'une source passe ; à partir de deux, une notif (une seule, réarmée au retour)."""
    if _streak(path, ok) >= FAILURES_BEFORE_ALERT:
        return [event]
    if ok:
        notify.forget(event.key)
    return []


def moneypuck_health(ok: bool) -> list[events.Event]:
    return _source_health(MONEYPUCK_HEALTH, ok, events.moneypuck_down())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="envoyer réellement la notif (sinon dry-run)")
    parser.add_argument("--target", choices=["test", "prod"], default="test")
    parser.add_argument("--scenario", choices=SCENARIOS)
    args = parser.parse_args()
    config.load_dotenv()

    if args.scenario:
        notify.send(run_scenario(args.scenario, config.today()), target=args.target,
                    dry_run=not args.send, record=False)
        return

    try:
        evts = run(config.today())
    except Exception:
        failures = _streak(HEALTH, ok=False)
        if failures == FAILURES_BEFORE_ALERT:
            notify.send([events.repeated_failures(failures)], target=args.target, dry_run=not args.send)
        raise
    _streak(HEALTH, ok=True)
    notify.forget("failures")
    notify.send(evts, target=args.target, dry_run=not args.send)


if __name__ == "__main__":
    main()
