"""Notifs des menaces : chaque point d'un joueur de la liste « À surveiller » de la PWA, au plus 15 min plus tard
(passe à chaque run de soirée). Une notif par pooler, avec son icône (app/public/poolers/<team_id>.png).

- La liste est celle de la PWA (Today.tsx), avec les points attendus d'avant le match : les WATCH_EACH joueurs
  adverses les plus nuisibles à ma P(1er) (attendu × impact d'un point), puis les WATCH_EACH meilleurs des
  équipes à CLOSE_PTS points ou moins de moi. Elle ne bouge donc pas pendant la soirée.
- Points : boxscores LNH des matchs commencés (les gardiens seulement à la fin du match, comme ESPN).
- État : data/state/menaces.json, les clés « jour:nhl_id:points » déjà envoyées (seulement hier et aujourd'hui).
"""
import json
from datetime import datetime, timedelta

from pipeline import config, notify, today
from pipeline.events import NORMAL, Event
from pipeline.sources import nhl

SENT = config.STATE_DIR / "menaces.json"
WATCH_EACH = 5
CLOSE_PTS = 10
STARTED = {"LIVE", "CRIT", "OFF", "FINAL"}


def watch_list(data: dict) -> list[dict]:
    """Les joueurs à surveiller d'un today.json, chacun avec son pooler (`owner`) et `ratio` : l'impact d'un de
    ses points en équivalent de mes points (négatif), ou None sans P(1er)."""
    me = next(t for t in data["teams"] if t["mine"])
    my_delta = me.get("delta_p_first_per_point")
    candidates = []
    for t in data["teams"]:
        if t["mine"]:
            continue
        d = t.get("delta_p_first_per_point")
        ratio = d / my_delta if d is not None and my_delta else None
        candidates += [{**p, "owner": t, "ratio": ratio, "gap": t["points"] - me["points"]}
                       for p in t.get("players", [])]
    season = sorted((c for c in candidates if c["ratio"] is not None),
                    key=lambda c: c["expected"] * c["ratio"])[:WATCH_EACH]
    seen = {c["espn_id"] for c in season}
    close = sorted((c for c in candidates if abs(c["gap"]) <= CLOSE_PTS and c["espn_id"] not in seen),
                   key=lambda c: -c["expected"])[:WATCH_EACH]
    return season + close


def notified(sent: set[str], day: str, nhl_id: int) -> int:
    """Le plus de points déjà notifiés pour ce joueur ce jour-là."""
    prefix = f"{day}:{nhl_id}:"
    return max((int(k.removeprefix(prefix)) for k in sent if k.startswith(prefix)), default=0)


def _detail(label: str) -> str:
    """« 1+1 » → « 1 but, 1 passe » ; un libellé de gardien (« victoire ») tel quel."""
    if "+" not in label:
        return label
    g, a = (int(x) for x in label.split("+"))
    parts = [f"{g} but{'s' if g > 1 else ''}" if g else "", f"{a} passe{'s' if a > 1 else ''}" if a else ""]
    return ", ".join(p for p in parts if p)


def _n(x: float) -> str:
    return f"{x:.1f}".replace(".", ",").replace("-", "−")


def events(watch: list[dict], points: dict[int, tuple[int, str]], sent: set[str],
           day: str) -> tuple[list[Event], set[str]]:
    """Une notif par pooler dont un joueur a fait un point depuis la dernière, et les clés à enregistrer."""
    by_owner: dict[int, list[tuple[dict, int, str]]] = {}
    for c in watch:
        pts, label = points.get(c.get("nhl_id"), (0, ""))
        if pts > notified(sent, day, c.get("nhl_id")):
            by_owner.setdefault(c["owner"]["team_id"], []).append((c, pts, label))
    out, keys = [], set()
    for team_id, rows in by_owner.items():
        owner = rows[0][0]["owner"]
        title = f"{owner['abbrev']} : " + ", ".join(f"{c['name'].split(' ', 1)[-1]} {label}" for c, _, label in rows)
        lines = []
        for c, pts, label in rows:
            impact = pts * c["ratio"] if c["ratio"] is not None else 0.0
            lines.append(f"{c['name']} ({c['team']} {c['opp']}) : {_detail(label)} ce soir"
                         + (f" ≈ {_n(impact)} de tes pts" if abs(impact) >= 0.05 else ""))
            keys.add(f"{day}:{c['nhl_id']}:{pts}")
        out.append(Event("menace", f"{day}:{team_id}:" + ",".join(f"{c['nhl_id']}={p}" for c, p, _ in rows),
                         "\n".join(lines), NORMAL, title, icon=f"{config.DASHBOARD_URL}poolers/{team_id}.png"))
    return out, keys


def run(now: datetime, today_games: list[dict], yesterday_games: list[dict], *, target: str, dry_run: bool) -> None:
    if not today.PATH.exists():
        return
    data = json.loads(today.PATH.read_text())
    games = {now.date().isoformat(): today_games,
             (now.date() - timedelta(days=1)).isoformat(): yesterday_games}.get(data["date"])
    if games is None:
        return
    watch = watch_list(data)
    wanted = {c["game_id"] for c in watch}
    points = {}
    for g in games:
        if g["game_id"] in wanted and g["state"] in STARTED:
            points |= nhl.fetch_points(g["game_id"])
    sent = {k for k in notify.load_sent(SENT) if k[:10] >= (now.date() - timedelta(days=1)).isoformat()}
    evts, keys = events(watch, points, sent, data["date"])
    if not evts:
        print("Aucun point des menaces")
        return
    for e in evts:
        notify.send([e], target=target, dry_run=dry_run, record=False)
    if not dry_run:
        notify.save_sent(sent | keys, SENT)

