"""Notifs de soirée : avant le premier match, vers 23 h (fin des matchs de l'Est) et le lendemain à 6 h.

Elles répondent à : combien de points devrais-je faire ce soir, et comment ça se compare aux équipes
qui peuvent me dépasser (ou que je peux dépasser) cette semaine.

- Points attendus d'un joueur pour un match de son équipe : sa ROS ÷ ses matchs restants (`data/rates.json`, écrit
  par la job quotidienne), × le facteur du match de ce soir (cotes et back-to-back, `pipeline/contexte.py`).
  Pour un gardien, ça inclut sa part des départs, sauf si MoneyPuck nomme le partant probable
  (`pipeline/partants.py` : P(partant) × points du gardien de son équipe ce soir).
- Rivaux : les équipes dont la probabilité d'échanger leur rang avec le mien d'ici RIVAL_DAYS jours dépasse
  RIVAL_P. Les points d'une équipe sur la période suivent une loi de Poisson (approchée par une normale).
- Le bilan de 23 h ne compte que les matchs terminés. S'ils le sont tous, c'est le bilan final et le matin
  n'envoie rien.
- Chaque notif envoyée réécrit aussi data/today.json (la soirée dans la PWA, avec les points réels).
- Entre les notifs, chaque run réécrit data/today.json si un alignement de la ligue a changé pour ce soir
  (ex. un joueur activé de l'IR). Pas avant midi si today.json est encore la soirée d'hier (bilan du matin).

uv run python -m pipeline.soiree                                   # dry-run de la notif due maintenant
uv run python -m pipeline.soiree --moment fin --day 2026-10-10     # force une notif (rien n'est enregistré)
"""
import argparse
import json
import math
from datetime import date, datetime, timedelta

from pipeline import config, contexte, ids, menaces, notify, partants, today
from pipeline.events import LOW, NORMAL, Event
from pipeline.http import AuthError
from pipeline.ids import ESPN_TO_NHL_TEAM
from pipeline.sources import espn, nhl

RATES = config.ROOT / "data" / "rates.json"
SENT = config.STATE_DIR / "soirees.json"
# La notif « avant » part entre 15 et 5 min avant le premier match (visée : 10 min). Le cron GitHub peut prendre
# des heures de retard : une exécution plus tôt (dès PREPARE_AHEAD) la calcule et ntfy la livre à l'heure.
# Passé 5 min avant le match, rien ne part.
PREPARE_AHEAD = timedelta(hours=5)
DELIVER_BEFORE = timedelta(minutes=10)
LATEST_BEFORE = timedelta(minutes=5)
EVENING_HOUR = 23
MORNING_HOURS = range(6, 12)
RIVAL_DAYS = 7
RIVAL_P = 0.10
MAX_RIVALS = 4
RIVALS_SHOWN = 3      # notif « avant » : équipes les plus menaçantes ce soir
WATCH_SHOWN = 3       # et joueurs adverses à surveiller
DONE = {"OVER", "OFF", "FINAL"}
LINEUP_SLOTS = {"F", "D", "G"}
# Gardien sans rythme (sans prior) : ~1,15 pt par match d'équipe (2 la victoire, 1 la défaite en prolongation
# dans ~22 % des matchs, 1 le blanchissage dans ~7 %, divisé entre les deux équipes), × ~60 % des départs
GOALIE_RATE = 0.7
MOMENTS = ("avant", "soir", "fin")


def write_rates(players: list[dict], ros, games_left) -> dict[str, float]:
    """Points attendus par match de chaque joueur qui a une ROS. `ros` et `games_left` : fonctions du joueur."""
    rates = {}
    for p in players:
        r, n = ros(p), games_left(p)
        if r and n:
            rates[str(p["espn_id"])] = round(r[0] / n, 4)
    RATES.write_text(json.dumps(rates, indent=0, sort_keys=True) + "\n")
    return rates


def _key(day: date, kind: str) -> str:
    return f"{day.isoformat()}:{kind}"


def moment(now: datetime, today_games: list[dict], yesterday_games: list[dict],
           sent: set[str]) -> tuple[str, date] | None:
    """La notif due à `now` (heure de Montréal) : (avant | soir | fin, journée des matchs), ou None."""
    day = now.date()
    yesterday = day - timedelta(days=1)
    if (now.hour in MORNING_HOURS and any(g["state"] in DONE for g in yesterday_games)
            and _key(yesterday, "fin") not in sent
            and not any(g["state"] in {"PRE", "LIVE", "CRIT"} for g in yesterday_games)):
        return "fin", yesterday
    if not today_games:
        return None
    done = [g for g in today_games if g["state"] in DONE]
    if now.hour >= EVENING_HOUR:
        if done and not sent & {_key(day, "soir"), _key(day, "fin")}:
            return ("fin" if len(done) == len(today_games) else "soir"), day
        return None
    first = first_start(today_games)
    if first - PREPARE_AHEAD <= now < first - LATEST_BEFORE and _key(day, "avant") not in sent:
        return "avant", day
    return None


def all_due(now: datetime, today_games: list[dict], yesterday_games: list[dict],
            sent: set[str]) -> list[tuple[str, date]]:
    """Toutes les notifs dues à `now`. Le cron GitHub saute souvent des heures : une même exécution peut
    devoir envoyer le « fin » d'hier et le « avant » d'aujourd'hui."""
    dues = []
    while (due := moment(now, today_games, yesterday_games, sent)) is not None:
        dues.append(due)
        sent = sent | {_key(due[1], due[0])}
    return dues


def first_start(games: list[dict]) -> datetime:
    return min(datetime.fromisoformat(g["start"].replace("Z", "+00:00")) for g in games)


def delivery(now: datetime, games: list[dict]) -> datetime | None:
    """Heure de livraison de la notif « avant » par ntfy (DELIVER_BEFORE avant le premier match), ou None :
    tout de suite, quand on est déjà dans la fenêtre."""
    at = first_start(games) - DELIVER_BEFORE
    return at if at > now + timedelta(minutes=1) else None


def _nhl_team(player: dict) -> str:
    return ESPN_TO_NHL_TEAM.get(player["pro_team"], player["pro_team"])


def _lineup(team: dict) -> list[dict]:
    return [p for p in team["roster"] if p["slot"] in LINEUP_SLOTS]


def _rate(player: dict, rates: dict[str, float]) -> float:
    return rates.get(str(player["espn_id"]), GOALIE_RATE if player["slot"] == "G" else 0.0)


def tonight_rate(player: dict, rates: dict[str, float], factors: dict[str, tuple[float, float]] | None,
                 starts: dict[int, tuple[float, float]] | None = None) -> float:
    """Points attendus ce soir : rythme × facteur du match (patineur ou gardien, cf. contexte.factors), ou ceux
    de partants.load pour un gardien dont on connaît la chance de commencer."""
    if player["slot"] == "G" and player["espn_id"] in (starts or {}):
        return starts[player["espn_id"]][1]
    skater, goalie = (factors or {}).get(_nhl_team(player), (1.0, 1.0))
    return _rate(player, rates) * (goalie if player["slot"] == "G" else skater)


def night(team: dict, rates: dict[str, float], games: list[dict], points: dict[int, tuple[int, str]],
          nhl_of: dict[int, int], factors: dict[str, tuple[float, float]] | None = None,
          starts: dict[int, tuple[float, float]] | None = None) -> dict:
    """La soirée d'une équipe : points attendus (total, matchs terminés, matchs à venir) et points réels
    dans les matchs terminés. `factors` : contexte.factors (sans : le rythme seul) ; `starts` : partants.load."""
    state = {t: g["state"] for g in games for t in g["teams"]}
    out = {"expected": 0.0, "expected_done": 0.0, "expected_left": 0.0, "actual": 0, "players": [], "scorers": []}
    for p in _lineup(team):
        if _nhl_team(p) not in state:
            continue
        rate = tonight_rate(p, rates, factors, starts)
        out["expected"] += rate
        out["players"].append((p, rate))
        if state[_nhl_team(p)] not in DONE:
            out["expected_left"] += rate
            continue
        out["expected_done"] += rate
        pts, label = points.get(nhl_of.get(p["espn_id"]), (0, ""))
        out["actual"] += pts
        if pts:
            out["scorers"].append((p, pts, label))
    return out


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def swap_probability(gap: float, mu_me: float, mu_them: float) -> float:
    """P(l'ordre entre moi et l'autre équipe change d'ici la fin de la période). `gap` = mes points − les siens."""
    if gap == 0:
        return 1.0
    sd = math.sqrt(mu_me + mu_them) or 1e-9
    mean = gap + mu_me - mu_them
    return _phi(-mean / sd) if gap > 0 else _phi(mean / sd)


def horizon_points(team: dict, rates: dict[str, float], schedule: list[dict], day: date) -> float:
    """Points attendus de l'alignement d'ici RIVAL_DAYS jours (aujourd'hui compris)."""
    start, end = day.isoformat(), (day + timedelta(days=RIVAL_DAYS)).isoformat()
    games = {}
    for g in schedule:
        if start <= g["date"] < end:
            games[g["team"]] = games.get(g["team"], 0) + 1
    return sum(_rate(p, rates) * games.get(_nhl_team(p), 0) for p in _lineup(team))


def rivals(league: dict, team_id: int, base: dict[int, float], rates: dict[str, float], schedule: list[dict],
           day: date) -> list[tuple[dict, float]]:
    """Les équipes qui peuvent échanger leur rang avec moi d'ici RIVAL_DAYS jours, les plus probables d'abord.
    `base` : les points de chaque équipe avant la soirée."""
    mu = {t["team_id"]: horizon_points(t, rates, schedule, day) for t in league["teams"]}
    out = []
    for t in league["teams"]:
        if t["team_id"] == team_id:
            continue
        p = swap_probability(base[team_id] - base[t["team_id"]], mu[team_id], mu[t["team_id"]])
        if p >= RIVAL_P:
            out.append((t, p))
    out.sort(key=lambda tp: -tp[1])
    return out[:MAX_RIVALS]


def _n(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _short(p: dict) -> str:
    return p["name"].split(" ", 1)[-1]


def _gap(gap: float) -> str:
    return f"+{gap:.0f}" if gap > 0 else f"{gap:.0f}".replace("-", "−")


def _position(gap: float) -> str:
    """La position d'un rival par rapport à moi, `gap` = mes points − les siens."""
    if gap == 0:
        return "à égalité"
    return f"{abs(gap):.0f} pts {'derrière' if gap > 0 else 'devant'}"


def _hour(iso: str) -> str:
    t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(config.TZ)
    return f"{t.hour} h" + (f" {t.minute:02d}" if t.minute else "")


def build(kind: str, day: date, league: dict, team_id: int, rates: dict[str, float], schedule: list[dict],
          games: list[dict], points: dict[int, tuple[int, str]], nhl_of: dict[int, int],
          morning: bool = False, odds: dict[int, tuple[float | None, float | None]] | None = None,
          history: list[dict] | None = None, factors: dict[str, tuple[float, float]] | None = None,
          starts: dict[int, tuple[float, float]] | None = None) -> Event:
    """`odds` : team_id → (P(1er), delta de ma P(1er) par point), cf. today.load_odds ;
    `history` : mes P(1er) passées (today.load_history) ; `factors` : contexte.factors du soir ;
    `starts` : partants.load."""
    nights = {t["team_id"]: night(t, rates, games, points, nhl_of, factors, starts) for t in league["teams"]}
    # Points de chaque équipe avant la soirée (ESPN compte déjà les matchs terminés)
    base = {t["team_id"]: (t.get("points") or 0) - nights[t["team_id"]]["actual"] for t in league["teams"]}
    me = nights[team_id]
    close = rivals(league, team_id, base, rates, schedule, day)
    avg = lambda field: sum(n[field] for n in nights.values()) / len(nights)  # noqa: E731
    scorers = ", ".join(f"{_short(p)} {label}" for p, _, label in sorted(me["scorers"], key=lambda s: -s[1]))
    lines = []

    if kind == "avant":
        when = "Ce soir" if datetime.fromisoformat(min(g["start"] for g in games).replace("Z", "+00:00")) \
            .astimezone(config.TZ).hour >= 17 else "Aujourd'hui"
        title = f"{when} : {len(games)} matchs, 1er à {_hour(min(g['start'] for g in games))}"
        odds = odds or {}
        mine, my_delta = odds.get(team_id, (None, None))
        if mine is not None:
            title += f" · P(1er) {round(mine * 100)} %"
            before = [h["p_first"] for h in (history or []) if h["day"] < day.isoformat()]
            if before and (move := round((mine - before[-1]) * 100)):
                title += f" ({'↑' if move > 0 else '↓'}{abs(move)})"
        players = sorted(me["players"], key=lambda x: -x[1])
        lines.append(f"Toi : {_n(me['expected'])} att." + (
            " · " + " · ".join(f"{_short(p)} {_n(r)}" for p, r in players) if players else ""))
        # Impact d'un point adverse en équivalent de mes points : delta de ma P(1er) par point de son équipe
        # ÷ delta par point des miens. Sans ces deltas (pas de today.json), on garde les rivaux proches.
        ratio = {tid: d / my_delta for tid, (_, d) in odds.items()
                 if tid != team_id and d is not None and my_delta}
        if ratio:
            others = [t for t in league["teams"] if t["team_id"] in ratio]
            threat = lambda t: nights[t["team_id"]]["expected"] * ratio[t["team_id"]]  # noqa: E731
            for t in sorted(others, key=threat)[:RIVALS_SHOWN]:
                lines.append(f"{t['abbrev']} : {_n(nights[t['team_id']]['expected'])} att."
                             f" ≈ {_n(threat(t)).replace('-', '−')} de tes pts")
            watch = sorted(((p, r * ratio[t["team_id"]], t) for t in others
                            for p, r in nights[t["team_id"]]["players"]), key=lambda x: x[1])[:WATCH_SHOWN]
            if watch:
                lines.append("À surveiller : " + " · ".join(f"{_short(p)} ({t['abbrev']})" for p, _, t in watch))
        else:
            for t, _ in close:
                lines.append(f"{t['abbrev']} ({_position(base[team_id] - base[t['team_id']])}) :"
                             f" {_n(nights[t['team_id']]['expected'])} att.")
        return Event("soiree", _key(day, kind), "\n".join(lines), NORMAL, title)

    if kind == "soir":
        done = sum(g["state"] in DONE for g in games)
        title = f"23 h : {me['actual']} pts (attendu {_n(me['expected_done'])})"
        lines.append(f"{done} matchs terminés sur {len(games)}")
        lines.append(f"Toi : {me['actual']} ({_n(me['expected_done'])}) · reste {_n(me['expected_left'])}")
        for t, _ in close:
            n = nights[t["team_id"]]
            lines.append(f"{t['abbrev']} : {n['actual']} ({_n(n['expected_done'])}) · reste {_n(n['expected_left'])}")
        lines.append(f"Ligue : {_n(avg('actual'))} en moyenne ({_n(avg('expected_done'))} attendus)")
        if scorers:
            lines.append(f"Tes points : {scorers}")
        return Event("soiree", _key(day, kind), "\n".join(lines), NORMAL, title)

    title = f"Soirée : {me['actual']} pts (attendu {_n(me['expected'])})"
    lines.append(f"Toi : {me['actual']} ({_n(me['expected'])})" + (f" · {scorers}" if scorers else ""))
    for t, _ in close:
        n = nights[t["team_id"]]
        before = base[team_id] - base[t["team_id"]]
        after = before + me["actual"] - n["actual"]
        lines.append(f"{t['abbrev']} : {n['actual']} ({_n(n['expected'])}) · écart {_gap(before)} → {_gap(after)}")
    lines.append(f"Ligue : {_n(avg('actual'))} en moyenne ({_n(avg('expected'))} attendus)")
    return Event("soiree", _key(day, "fin"), "\n".join(lines), LOW if morning else NORMAL, title)


def lineups(data: dict | None) -> dict[int, list[int]]:
    """team_id → joueurs de l'alignement qui jouent ce soir (ids ESPN), d'après un today.json."""
    return {t["team_id"]: sorted(p["espn_id"] for p in t.get("players", [])) for t in (data or {}).get("teams", [])}


def should_refresh(now: datetime, current: dict | None, today_games: list[dict]) -> bool:
    """Vérifier les alignements maintenant ? Oui s'il y a des matchs ce soir, sauf si today.json montre encore
    la soirée d'hier avant midi (le bilan du matin reste affiché)."""
    if not today_games:
        return False
    return (current or {}).get("date") == now.date().isoformat() or now.hour >= MORNING_HOURS.stop


def refresh(now: datetime, today_games: list[dict]) -> None:
    """Réécrit data/today.json si un alignement de ce soir a changé depuis la dernière écriture."""
    current = json.loads(today.PATH.read_text()) if today.PATH.exists() else None
    if not should_refresh(now, current, today_games):
        return
    try:
        league = espn.fetch_league()
    except AuthError as e:
        print(f"Ligue ESPN inaccessible ({e}) : alignements pas vérifiés")
        return
    goals = contexte.load_goals(now.date())
    data = today.build(now.date(), league, config.MY_TEAM_ID, json.loads(RATES.read_text()), today_games,
                       fetch_points(today_games), nhl_ids(), today.load_odds(), today.load_history(), now,
                       contexte.load(now.date(), load_schedule()), today.load_finals(), goals,
                       partants.load(now.date(), league, goals, current))
    if (current and current.get("date") == data["date"] and lineups(current) == lineups(data)
            and partants.previous(current, now.date()) == partants.previous(data, now.date())):
        print("Alignements et partants inchangés")
        return
    print("Alignements ou partants changés : today.json réécrit")
    today.write(data)


def run(now: datetime, *, target: str, dry_run: bool, forced: tuple[str, date] | None = None) -> None:
    if forced:
        _send(now, forced, nhl.fetch_games(forced[1].isoformat()), target=target, dry_run=dry_run, forced=True)
        return
    today_games = nhl.fetch_games(now.date().isoformat())
    yesterday_games = nhl.fetch_games((now.date() - timedelta(days=1)).isoformat())
    dues = all_due(now, today_games, yesterday_games, notify.load_sent(SENT))
    if not dues:
        print("Aucune notif de soirée due")
    for due in dues:
        games = today_games if due[1] == now.date() else yesterday_games
        _send(now, due, games, target=target, dry_run=dry_run, forced=False)
    menaces.run(now, today_games, yesterday_games, target=target, dry_run=dry_run)
    if not dry_run:
        refresh(now, today_games)


def load_schedule() -> list[dict]:
    return json.loads((config.ROOT / "data" / "schedule.json").read_text())


def nhl_ids() -> dict[int, int]:
    """espn_id → nhl_id, d'après data/id_map.csv et les corrections à la main."""
    return {k: int(v["nhl_id"]) for k, v in ids.resolved(ids.read_map(ids.ID_MAP)).items() if v.get("nhl_id")}


def fetch_points(games: list[dict]) -> dict[int, tuple[int, str]]:
    """Points de pool par nhl_id dans les matchs terminés (boxscores LNH)."""
    points = {}
    for g in games:
        if g["state"] in DONE:
            points |= nhl.fetch_points(g["game_id"])
    return points


def _send(now: datetime, due: tuple[str, date], games: list[dict], *, target: str, dry_run: bool,
          forced: bool) -> None:
    try:
        league = espn.fetch_league()
    except AuthError as e:
        print(f"Ligue ESPN inaccessible ({e}) : la job quotidienne s'en occupe")
        return
    rates = json.loads(RATES.read_text())
    schedule = load_schedule()
    nhl_of = nhl_ids()
    points = fetch_points(games)
    factors = contexte.load(due[1], schedule)
    goals = contexte.load_goals(due[1])
    starts = partants.load(due[1], league, goals, json.loads(today.PATH.read_text()) if today.PATH.exists() else None)
    evt = build(*due, league, config.MY_TEAM_ID, rates, schedule, games, points, nhl_of,
                morning=now.hour in MORNING_HOURS and due[1] < now.date(), odds=today.load_odds(),
                history=today.load_history(), factors=factors, starts=starts)
    at = delivery(now, games) if due[0] == "avant" and not forced else None
    sent = notify.send([evt], target=target, dry_run=dry_run, record=not forced, path=SENT, at=at)
    if sent and not forced:
        today.write(today.build(due[1], league, config.MY_TEAM_ID, rates, games, points, nhl_of,
                                today.load_odds(), today.load_history(), now, factors, today.load_finals(),
                                goals, starts))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="envoyer réellement la notif (sinon dry-run)")
    parser.add_argument("--target", choices=["test", "prod"], default="test")
    parser.add_argument("--moment", choices=MOMENTS, help="forcer une notif, sans rien enregistrer")
    parser.add_argument("--day", type=date.fromisoformat, help="journée des matchs (avec --moment)")
    args = parser.parse_args()
    config.load_dotenv()
    now = datetime.now(config.TZ)
    forced = (args.moment, args.day or now.date()) if args.moment else None
    run(now, target=args.target, dry_run=not args.send, forced=forced)


if __name__ == "__main__":
    main()
