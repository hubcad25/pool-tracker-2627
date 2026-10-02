"""Exécution quotidienne.

uv run python -m pipeline.main                  # dry-run : imprime la notif sans l'envoyer
uv run python -m pipeline.main --send --target prod
"""
import argparse
import json
from datetime import date

from pipeline import config, events, ids, notify, snapshot
from pipeline.http import AuthError
from pipeline.sources import espn, nhl

HEALTH = config.STATE_DIR / "health.json"
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

    # Phase 1 : règles de statut / date de retour / activation IR (diff avec snapshot.previous_day)
    return out


def _health(ok: bool) -> int:
    failures = 0 if ok else (json.loads(HEALTH.read_text())["failures"] + 1 if HEALTH.exists() else 1)
    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH.write_text(json.dumps({"failures": failures, "last_run": config.today().isoformat(), "ok": ok}) + "\n")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="envoyer réellement la notif (sinon dry-run)")
    parser.add_argument("--target", choices=["test", "prod"], default="test")
    args = parser.parse_args()
    config.load_dotenv()

    try:
        evts = run(config.today())
    except Exception:
        failures = _health(ok=False)
        if failures == FAILURES_BEFORE_ALERT:
            notify.send([events.repeated_failures(failures)], target=args.target, dry_run=not args.send)
        raise
    _health(ok=True)
    notify.forget("failures")
    notify.send(evts, target=args.target, dry_run=not args.send)


if __name__ == "__main__":
    main()
