import Group from '../components/Group'
import TeamLogo from '../components/TeamLogo'
import NightBar, { NightLegend } from '../components/NightBar'
import DistBars from '../components/DistBars'
import { SortBar, sortBy, useSort, type SortOption, type SortState } from '../components/Sort'
import PlayerDetail from '../components/PlayerDetail'
import Sparkline from '../components/Sparkline'
import { clock, dec, lastName, prob, shortDate, signed } from '../format'
import { hasProxy, playerNight, projection, sumNights, teamNight, useLive, type Live, type Night } from '../live'
import { teamColor, teamTint } from '../teams'
import PoolerIcon from '../components/PoolerIcon'
import { firstPlaceOdds } from '../odds'
import { arrow, tone } from '../tone'
import { useState } from 'react'
import type { Today as T, TodayTeam, TonightPlayer } from '../types'

const where = (p: TonightPlayer) => (
  <>
    {p.pos && `${p.pos} · `}
    <TeamLogo team={p.team} /> {p.opp.startsWith('@') ? '@' : 'vs'} <TeamLogo team={p.opp.replace('@', '')} />
  </>
)

/** Heure du match, ou son état en direct (« 2e · 14:02 », « Final ») */
const when = (p: TonightPlayer, n: Night) => {
  const t = n.clock ?? (n.state === 'FINAL' ? 'Final' : clock(p.start))
  // Gardien : le pointage de son équipe, et s'il est sur le banc ou entré en relève
  const g = n.goalie
  if (!g || n.state === 'FUT') return t
  const role = g.started === false ? (g.inNet ? ' · relève' : ' · banc') : g.started && g.inNet === false ? ' · retiré' : ''
  return `${g.score.for}-${g.score.against} · ${t}${role}`
}

/** À droite d'une barre, lisible sans légende :
 *  avant le match « 1,2 / pts prévus » ; pendant « 2 pts → 2,6 » (faits → fin ≈, aussi gros l'un que l'autre)
 *  et « prévu 1,2 » effacé ; fini « 2 pts / prévu 1,2 · ▲ +0,8 ».
 *  Une fois le match commencé, ce qui compte : les faits et la fin ≈ ; le prévu passe au second plan.
 *  Fin ≈ fait + le prévu du temps qui reste. L'écart d'un match fini = réel − prévu. */
function Score({ n, big }: { n: Night & { started: boolean }; big?: boolean }) {
  const cls = `row-value num${big ? '' : ' is-small'}`
  if (!n.started) {
    return (
      <>
        <span className={`${cls} is-data`}>{dec(n.expected)}</span>
        <span className="row-sub">pts prévus</span>
        <OnePoint n={n} />
      </>
    )
  }
  const playing = n.left > 0.005
  const gap = n.actual - (n.expected - n.left)
  return (
    <>
      <span className={cls}>
        {n.actual} <small>{n.actual >= 2 ? 'pts' : 'pt'}</small>
        {playing && <> <small>→</small> <span className="fin">{dec(projection(n))}</span></>}
      </span>
      {playing ? (
        <span className="row-sub num">
          <b>reste {dec(n.left)}</b> <span className="is-faded">· prévu {dec(n.expected)}</span>
        </span>
      ) : (
        <span className="row-sub num">
          <span className="is-faded">prévu {dec(n.expected)}</span> ·{' '}
          <span style={tone(gap, 2)}>{Math.abs(gap) < 0.05 ? '= prévu' : `${arrow(gap)}${signed(gap)}`}</span>
        </span>
      )}
      <OnePoint n={n} />
    </>
  )
}

/** P(1+ pt) d'un joueur : avant le match, sa valeur ; ensuite « début → maintenant » tant qu'il a 0 pt et que
 *  le match continue ; ✓ vert dès qu'il a son point. Rien une fois le match fini sans point. */
function OnePoint({ n }: { n: Night }) {
  if (n.actual >= 1) return <span className="row-sub one-point is-done">✓ 1+ pt</span>
  if (n.state === 'FUT') return <span className="row-sub num">P(1+ pt) : {prob(n.p1Start)}</span>
  if (n.state === 'FINAL') return null
  return (
    <span className="row-sub num">
      P(1+ pt) : {prob(n.p1Start)} → <b>{prob(n.p1)}</b>
    </span>
  )
}

/** Sous la barre d'un joueur, chaque chiffre à son endroit : ses points au bout du plein, la fin estimée au bout
 *  du clair (pendant le match) ; avant le match, le prévu sous le trait (ensuite, le trait seul). Une étiquette trop près d'une autre saute. */
function NightMarks({ n, max }: { n: Night; max: number }) {
  const marks: { x: number; text: string; cls: string }[] = []
  if (n.state !== 'FUT' && n.actual > 0) marks.push({ x: n.actual, text: `${n.actual}`, cls: 'is-end is-actual' })
  if (n.state === 'FUT') marks.push({ x: n.expected, text: `prévu ${dec(n.expected)}`, cls: 'is-tick' })
  if (n.state !== 'FUT' && n.left > 0.005) marks.push({ x: projection(n), text: `fin ≈ ${dec(projection(n))}`, cls: 'is-proj' })
  const shown = marks.filter((m, i) => marks.slice(0, i).every((o) => Math.abs(o.x - m.x) / max > 0.22))
  // Le prévu, centré sous son trait, ne doit pas déborder : collé à gauche près de 0, à droite près du bout.
  // La fin ≈, alignée à droite sur le bout du clair, part vers la droite quand elle est trop près de 0.
  const edge = (m: (typeof marks)[number]) => {
    const r = m.x / max
    if (m.cls === 'is-proj') return r < 0.3 ? ' is-left' : ''
    if (m.cls !== 'is-tick') return ''
    return r < 0.15 ? ' is-left' : r > 0.85 ? ' is-right' : ''
  }
  return (
    <div className="season-marks night-marks num">
      {shown.map((m) => (
        <span key={m.cls} className={`season-mark ${m.cls}${edge(m)}`} style={{ left: `${(Math.max(0, m.x) / max) * 100}%` }}>{m.text}</span>
      ))}
    </div>
  )
}

/** La barre « ce soir » d'une équipe, son total collé au bout. L'échelle commune (`max`) vaut la zone sans la
 *  place réservée au total à droite (padding de .night-line). */
function NightLine({ n, max, teamId }: { n: ReturnType<typeof teamNight>; max: number; teamId: number }) {
  const end = Math.max(n.expected, n.actual + n.left + n.lost, 0.01)
  const at = `${(end / max) * 100}%`
  return (
    <div className="night-line">
      <div className="night-area">
        <div style={{ width: at }}>
          <NightBar n={n} max={end} teamId={teamId} />
        </div>
        <span className="night-total" style={{ left: at }}>
          <TeamScore n={n} />
        </span>
      </div>
    </div>
  )
}

/** Au bout de la barre « ce soir » d'une équipe : « 13,8 pts prévus » avant les matchs, « 2 pts → 13,1 »
 *  pendant (faits → fin ≈), « 14 pts » une fois tout fini */
function TeamScore({ n }: { n: ReturnType<typeof sumNights> & { started: boolean } }) {
  return (
    <span className="row-value num team-score">
      {n.started ? (
        <>
          {n.actual} <small>{n.actual >= 2 ? 'pts' : 'pt'}</small>
          {n.left > 0.005 && <> <small>→</small> <span className="fin">{dec(projection(n))}</span></>}
        </>
      ) : (
        <>
          <span className="is-data">{dec(n.expected)}</span> <small>pts prévus</small>
        </>
      )}
    </span>
  )
}

/** Pendant la soirée, sur la ligne du haut : « fin ≈ 14,1 · prévu 13,8 », ou l'écart une fois tout fini */
function ScoreSub({ n }: { n: ReturnType<typeof sumNights> }) {
  const gap = n.actual - (n.expected - n.left)
  return (
    <span className="num">
      {n.left > 0.005 ? (
        <><b className="fin">fin ≈ {dec(projection(n))}</b> · reste {dec(n.left)} · <span className="is-faded">prévu {dec(n.expected)}</span></>
      ) : (
        <><span className="is-faded">prévu {dec(n.expected)}</span> ·{' '}
          <span style={tone(gap, 2)}>{Math.abs(gap) < 0.05 ? '= prévu' : `${arrow(gap)}${signed(gap)}`}</span></>
      )}
    </span>
  )
}

/** Les joueurs d'un pooler ce soir, triés comme les équipes (« Saison + ce soir » et « P(1er) » : par fin ≈) ;
 *  chacun se déplie sur son match */
function PoolerPlayers({ r, t, live, sort }: { r: TodayTeam; t: T; live: Live; sort: SortState<TeamKey> }) {
  const [open, setOpen] = useState<number | null>(null)
  const rows = sortBy((r.players ?? []).map((p) => ({ p, n: playerNight(p, t, live) })), sort, ({ p, n }, k) =>
    k === 'left' ? n.left : k === 'expected' ? n.expected : k === 'actual' ? n.actual : k === 'name' ? lastName(p.name) : projection(n),
  )
  const max = Math.max(1, ...rows.map(({ n }) => Math.max(n.expected, n.actual + n.left + n.lost)))
  if (!rows.length) return <div className="player-detail">Aucun joueur ce soir.</div>
  const total = sumNights(rows.map(({ n }) => n))
  return (
    <>
    <DistBars actual={total.actual} left={total.left} teamId={r.team_id} />
    <ul className="rows pooler-players" onClick={(e) => e.stopPropagation()}>
      {rows.map(({ p, n }) => (
        <li key={p.espn_id} className={`row is-clickable${open === p.espn_id ? ' is-open' : ''}`}
          onClick={() => setOpen((o) => (o === p.espn_id ? null : p.espn_id))} aria-expanded={open === p.espn_id}>
          <div className="row-main">
            <span className="row-name">{lastName(p.name)}</span>
            <span className="row-meta">
              {where(p)} · <span className={n.state === 'LIVE' ? 'is-live' : undefined}>{when(p, n)}</span>
            </span>
            <NightBar n={n} max={max} teamId={r.team_id} thin />
            <NightMarks n={n} max={max} />
          </div>
          <div className="row-side">
            <Score n={{ ...n, started: n.state !== 'FUT' }} />
          </div>
          {open === p.espn_id && <PlayerDetail p={p} n={n} live={live} />}
        </li>
      ))}
    </ul>
    </>
  )
}

type TeamKey = 'proj' | 'left' | 'season' | 'expected' | 'actual' | 'p_first' | 'name'
const TEAM_SORT: SortOption<TeamKey>[] = [
  { key: 'proj', label: 'Fin ≈', dir: 'desc' },
  { key: 'left', label: 'Restant', dir: 'desc' },
  { key: 'season', label: 'Saison + ce soir', dir: 'desc' },
  { key: 'expected', label: 'Prévu', dir: 'desc' },
  { key: 'actual', label: 'Réel', dir: 'desc' },
  { key: 'p_first', label: 'P(1er)', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

/** Points de la saison avant la soirée (today.json réécrit pendant la soirée compte déjà les matchs terminés) */
const base = (r: TodayTeam) => r.points - (r.actual_tonight ?? 0)

/** « 5 pts devant moi », « 3 pts derrière moi », d'après les points en direct */
const gapText = (g: number) => {
  const x = Math.round(Math.abs(g))
  return x === 0 ? 'à égalité avec moi' : `${x} pt${x > 1 ? 's' : ''} ${g > 0 ? 'devant' : 'derrière'} moi`
}

const ord = (n: number) => (n === 1 ? '1er' : `${n}e`)

/** Sous la barre saison, chaque chiffre à son endroit : les points maintenant finissent au bout du plein, la
 *  projection du soir commence au bout de la barre (l'échelle garde de la place pour elle à droite). */
function SeasonMarks({ now, proj, max }: { now: number; proj: number; max: number }) {
  const at = (x: number) => `${(x / max) * 100}%`
  const a = Math.round(now)
  const b = Math.round(proj)
  return (
    <div className="season-marks num">
      <span className="season-mark is-end" style={{ left: at(now) }}>{a}</span>
      {b !== a && <b className="season-mark" style={{ left: at(proj) }}>{b}</b>}
    </div>
  )
}

// Restant : les points encore possibles ce soir (le prévu avant le match, 0 une fois fini)
type PlayerKey = 'start' | 'left' | 'proj' | 'expected' | 'actual' | 'name'
const PLAYER_SORT: SortOption<PlayerKey>[] = [
  { key: 'start', label: 'Heure', dir: 'asc' },
  { key: 'left', label: 'Restant', dir: 'desc' },
  { key: 'proj', label: 'Fin ≈', dir: 'desc' },
  { key: 'expected', label: 'Prévu', dir: 'desc' },
  { key: 'actual', label: 'Réel', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

type WatchKey = 'threat' | 'left' | 'expected' | 'start'
const WATCH_EACH = 5

const nextDay = (iso: string) => new Date(Date.parse(`${iso}T12:00:00Z`) + 86_400_000).toISOString().slice(0, 10)

/** P(1er) de chaque équipe avec la soirée (team_id → P) : chaque total final du matin − l'attendu de ce soir + réel
 *  + encore possible. On ajoute à la P(1er) du matin l'écart entre les deux calculs (mêmes arrondis des deux côtés :
 *  0 avant les matchs). Vide sans les totaux du matin (vieux today.json) ou avant le premier match. */
function liveFirst(teams: { r: TodayTeam; n: ReturnType<typeof teamNight> }[]): Map<number, number> {
  if (!teams.some(({ n }) => n.started)) return new Map()
  if (teams.some(({ r }) => r.final == null || r.sd == null || r.p_first == null)) return new Map()
  const sds = teams.map(({ r }) => r.sd!)
  const before = firstPlaceOdds(teams.map(({ r }) => r.final!), sds)
  const after = firstPlaceOdds(teams.map(({ r, n }) => r.final! - n.expected + projection(n)), sds)
  return new Map(teams.map(({ r }, i) => [r.team_id, Math.min(1, Math.max(0, r.p_first! + after[i] - before[i]))]))
}
const CLOSE_PTS = 10
const WATCH_SORT: SortOption<WatchKey>[] = [
  { key: 'threat', label: 'Menace', dir: 'asc' },
  { key: 'left', label: 'Restant', dir: 'desc' },
  { key: 'expected', label: 'Prévu', dir: 'desc' },
  { key: 'start', label: 'Heure', dir: 'asc' },
]

function LiveStatus({ live, t }: { live: Live; t: T }) {
  const anyLive = t.games.some((g) => (live.games.get(g.id)?.state ?? g.state) === 'LIVE')
  if (!hasProxy) return null
  if (live.status === 'error') return <p className="live-status is-off">Direct indisponible : points des matchs terminés seulement.</p>
  if (!live.at) return null
  return (
    <p className={`live-status${anyLive ? ' is-on' : ''}`}>
      {anyLive && <i className="live-dot" />}
      {anyLive ? 'En direct' : 'Pointage LNH'} · {clock(live.at.toISOString())}
    </p>
  )
}

export default function Today({ today: t }: { today: T }) {
  const live = useLive(t)
  const [teamSort, setTeamSort] = useSort('aujourdhui-equipes', TEAM_SORT)
  const [playerSort, setPlayerSort] = useSort('aujourdhui-joueurs', PLAYER_SORT)
  const [watchSort, setWatchSort] = useSort('aujourdhui-surveiller', WATCH_SORT)
  // Joueur déplié (« m-<id> » mes joueurs, « w-<id> » à surveiller) : son match en détail
  const [open, setOpen] = useState<string | null>(null)
  const toggle = (key: string) => setOpen((o) => (o === key ? null : key))
  const pf = t.p_first
  const diff = pf?.now != null && pf.yesterday != null ? pf.now - pf.yesterday : null
  const noGames = t.games.length === 0

  // Saison : les points d'avant la soirée (today.json réécrit pendant la soirée compte déjà les matchs terminés),
  // + le réel en direct, + la projection du soir. Rang = classement par points, avant et après la projection.
  const teams = t.teams.map((r) => {
    const n = teamNight(r, t, live)
    return { r, n, now: base(r) + n.actual, proj: base(r) + projection(n) }
  })
  const max = Math.max(1, ...teams.map(({ n }) => Math.max(n.expected, n.actual + n.left + n.lost)))
  const rankBy = (key: 'now' | 'proj') => {
    const order = [...teams].sort((a, b) => b[key] - a[key])
    return new Map(teams.map((x) => [x.r.team_id, order.findIndex((y) => y[key] <= x[key]) + 1]))
  }
  const liveOdds = liveFirst(teams)
  const pLive = liveOdds.get(t.teams.find((r) => r.mine)?.team_id ?? -1) ?? null
  const allDone = t.games.length > 0 && t.games.every((g) => (live.games.get(g.id)?.state ?? g.state) === 'FINAL')
  const liveDiff = pLive != null && pf?.now != null ? pLive - pf.now : null
  // Matchs terminés : la P(1er) d'après la soirée devient le point (provisoire) du lendemain, jusqu'à la job du midi
  const history = pf?.history ?? []
  const provisional = allDone && pLive != null && !history.some((h) => h.day > t.date)
  const sparkPoints = provisional ? [...history, { day: nextDay(t.date), p_first: pLive! }] : history
  const rankNow = rankBy('now')
  const rankProj = rankBy('proj')
  const seasonMax = Math.max(1, ...teams.map((x) => x.proj)) * 1.08
  const sortedTeams = sortBy(teams, teamSort, ({ r, n, proj }, k) =>
    k === 'proj' ? projection(n)
    : k === 'left' ? n.left
    : k === 'season' ? proj
    : k === 'p_first' ? (liveOdds.get(r.team_id) ?? r.p_first)
    : k === 'expected' ? n.expected
    : k === 'actual' ? n.actual
    : (r.name ?? r.abbrev ?? ''),
  )

  const me = t.teams.find((r) => r.mine)
  const mineId = me?.team_id ?? 0
  const mine = t.my_players.map((p) => ({ p, n: playerNight(p, t, live) }))
  const playerMax = Math.max(1, ...mine.map(({ n }) => Math.max(n.expected, n.actual + n.left + n.lost)))
  const sortedMine = sortBy(mine, playerSort, ({ p, n }, k) =>
    k === 'start' ? p.start : k === 'left' ? n.left : k === 'proj' ? projection(n) : k === 'expected' ? n.expected : k === 'actual' ? n.actual : lastName(p.name),
  )

  // Impact d'un point adverse en équivalent de MES points : delta de ma P(1er) quand il marque ÷ quand je marque
  const myDelta = me?.delta_p_first_per_point ?? null
  const ratio = (d: number | null) => (d != null && myDelta ? d / myDelta : null)
  // À surveiller, deux listes mêlées : les pires pour ma P(1er) sur la saison (menace) et les meilleurs des équipes
  // proches de moi au classement en direct (à CLOSE_PTS points ou moins), même si leur P(1er) bouge peu
  const myNow = teams.find((x) => x.r.mine)?.now ?? 0
  const candidates = t.teams.filter((r) => !r.mine).flatMap((r) =>
    (r.players ?? []).map((p) => {
      const n = playerNight(p, t, live)
      const rr = ratio(r.delta_p_first_per_point ?? null)
      const now = teams.find((x) => x.r.team_id === r.team_id)?.now ?? r.points
      return {
        p: { ...p, owner: { team_id: r.team_id, abbrev: r.abbrev, name: r.name }, delta_p_first_per_point: r.delta_p_first_per_point ?? null },
        n,
        ratio: rr,
        // Menace = ses points projetés de la soirée (réel + ce qui reste possible) × l'impact d'un de ses points
        threat: rr == null ? null : (n.actual + n.left) * rr,
        gap: now - myNow,
      }
    }),
  )
  const bySeason = [...candidates].filter((w) => w.threat != null).sort((a, b) => a.threat! - b.threat!).slice(0, WATCH_EACH)
  const close = candidates
    .filter((w) => Math.abs(w.gap) <= CLOSE_PTS && !bySeason.includes(w))
    .sort((a, b) => projection(b.n) - projection(a.n))
    .slice(0, WATCH_EACH)
  const watch = [
    ...bySeason.map((w) => ({ ...w, why: 'saison' as const })),
    ...close.map((w) => ({ ...w, why: 'classement' as const })),
  ]
  const sortedWatch = sortBy(watch, watchSort, (w, k) =>
    k === 'threat' ? w.threat : k === 'left' ? w.n.left : k === 'expected' ? w.p.expected : w.p.start,
  )

  // Matchs à regarder : ce qui reste à jouer dans chaque match, en équivalent de MES points. Poids d'un joueur :
  // 1 s'il est à moi ; pour un rival, le plus grand de sa menace sur ma P(1er) (|ratio|) et de sa proximité au
  // classement (1 à égalité, 0 à CLOSE_PTS points ou plus). `left` fond déjà avec le temps réglementaire qui reste.
  const weightOf = (r: TodayTeam) => {
    if (r.mine) return 1
    const now = teams.find((x) => x.r.team_id === r.team_id)?.now ?? r.points
    const near = Math.max(0, 1 - Math.abs(now - myNow) / CLOSE_PTS)
    return Math.max(Math.abs(ratio(r.delta_p_first_per_point ?? null) ?? 0), near)
  }
  const stakes = t.teams.flatMap((r) => {
    const w = weightOf(r)
    return (r.players ?? []).map((p) => {
      const n = playerNight(p, t, live)
      return { p, r, n, stake: w * n.left, mine: r.mine }
    })
  })
  const toWatch = t.games
    .map((g) => {
      const lg = live.games.get(g.id)
      const ps = stakes.filter((x) => x.p.game_id === g.id && x.stake > 0.005).sort((a, b) => b.stake - a.stake)
      const forMe = ps.filter((x) => x.mine).reduce((s, x) => s + x.stake, 0)
      const against = ps.filter((x) => !x.mine).reduce((s, x) => s + x.stake, 0)
      return { g, state: lg?.state ?? g.state, clock: lg?.clock ?? null, score: lg?.score, ps, forMe, against, total: forMe + against }
    })
    .filter((x) => x.state !== 'FINAL' && x.total >= 0.05)
    .sort((a, b) => b.total - a.total)
  const watchMax = Math.max(0.01, ...toWatch.map((x) => x.total))

  return (
    <>
      {pf?.now != null && (
        <section className="hero">
          <div>
            <p className="hero-label">Mes chances de finir 1er</p>
            <p className="hero-value num">{prob(pf.now)}</p>
            {diff != null && (
              <p className="hero-sub">
                hier {prob(pf.yesterday!)}{' '}
                <span style={tone(diff, 0.05)}>
                  ({arrow(diff, 0.0005)}{signed(diff * 100)} pt)
                </span>
              </p>
            )}
            {liveDiff != null && (
              <p className="hero-sub">
                {allDone ? 'après ce soir' : 'en direct'} {prob(pLive!)}{' '}
                <span style={tone(liveDiff, 0.05)}>
                  ({arrow(liveDiff, 0.0005)}{signed(liveDiff * 100)} pt)
                </span>
              </p>
            )}
          </div>
          <Sparkline points={sparkPoints} provisional={provisional} />
        </section>
      )}

      {noGames ? (
        <p className="empty">Pas de matchs ce soir.</p>
      ) : (
        <>
          {toWatch.length > 0 && (
            <Group id="soir-matchs" title="Matchs à regarder">
              <p className="group-note">
                Ce qui reste à jouer dans chaque match, en équivalent de mes points : mes joueurs (vert) plus ceux des
                rivaux (rouge) qui menacent ma 1re place ou sont à 10 pts ou moins de moi. Fond avec le temps qui reste.
              </p>
              <ul className="rows">
                {toWatch.map(({ g, state, clock: c, score, ps, forMe, against, total }) => (
                  <li key={g.id} className="row">
                    <div className="row-main">
                      <span className="row-name">
                        <TeamLogo team={g.away} /> {state !== 'FUT' && score ? `${score[g.away] ?? 0}-${score[g.home] ?? 0}` : '@'}{' '}
                        <TeamLogo team={g.home} />
                      </span>
                      <span className="row-meta">
                        <span className={state === 'LIVE' ? 'is-live' : undefined}>{c ?? clock(g.start)}</span>
                      </span>
                      <div className="nightbar-track watch-bar" role="img" aria-label={`${dec(forMe)} pour moi, ${dec(against)} contre`}>
                        {forMe > 0 && <span className="nightbar-seg" style={{ width: `${(forMe / watchMax) * 100}%`, background: 'var(--good)' }} />}
                        {against > 0 && <span className="nightbar-seg" style={{ width: `${(against / watchMax) * 100}%`, background: 'var(--danger)' }} />}
                      </div>
                      <span className="row-meta">
                        {ps.slice(0, 3).map(({ p, r, mine: m }, i) => (
                          <span key={p.espn_id}>
                            {i > 0 && ' · '}
                            <PoolerIcon teamId={r.team_id} />
                            <span style={tone(m ? 1 : -1, 1)}>{lastName(p.name)}</span>
                          </span>
                        ))}
                        {ps.length > 3 && <> · +{ps.length - 3}</>}
                      </span>
                    </div>
                    <div className="row-side">
                      <span className="row-value num is-small">{dec(total)}</span>
                      <span className="row-sub">de mes pts en jeu</span>
                      <span className="row-sub num">
                        <span style={tone(1, 1)}>{dec(forMe)}</span> · <span style={tone(-1, 1)}>{dec(against)}</span>
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </Group>
          )}

          <Group id="soir-equipes" title={`Ce soir · ${shortDate(t.date)}`}>
            <LiveStatus live={live} t={t} />
            <p className="group-note">Même échelle pour toutes les équipes.</p>
            <NightLegend />
            <p className="legend-line">
              « ce soir » et « saison » n'ont pas la même échelle. Saison : les points d'avant ce soir (pâle), puis la soirée au bout. « 71 → 74 » : maintenant → fin ≈ de la soirée.
            </p>
            <SortBar options={TEAM_SORT} sort={teamSort} onChange={setTeamSort} />
            <ul className="rows">
              {sortedTeams.map(({ r, n, now, proj }) => {
                const before = rankNow.get(r.team_id)!
                const after = rankProj.get(r.team_id)!
                return (
                <li key={r.team_id} className={`row tonight is-clickable${r.mine ? ' is-mine' : ''}${open === `t-${r.team_id}` ? ' is-open' : ''}`}
                  onClick={() => toggle(`t-${r.team_id}`)} aria-expanded={open === `t-${r.team_id}`}>
                  <div className="row-main">
                    <a className="row-name team-link" href={`#equipe/${r.team_id}`} onClick={(e) => e.stopPropagation()}>
                      <PoolerIcon teamId={r.team_id} />
                      {r.name}
                    </a>
                    <span className="row-meta">
                      {r.p_first != null && (liveOdds.has(r.team_id)
                        ? <>P(1er) {prob(r.p_first)} → {prob(liveOdds.get(r.team_id)!)} · </>
                        : <>P(1er) {prob(r.p_first)} · </>)}
                      {r.playing_tonight} joueur{r.playing_tonight > 1 ? 's' : ''}
                      {n.started && <> · <ScoreSub n={n} /></>}
                    </span>
                    <div className="labeled-bar">
                      <span className="bar-label">ce soir</span>
                      <NightLine n={n} max={max} teamId={r.team_id} />
                    </div>
                    <div className="labeled-bar">
                      <span className="bar-label">saison</span>
                      <div>
                        <div className="ptsbar" role="img" aria-label={`Saison : ${dec(base(r))} pts avant ce soir, puis la soirée`}>
                          <div className="nightbar-track">
                            <span className="nightbar-seg ptsbar-base" style={{ width: `${(base(r) / seasonMax) * 100}%`, background: teamColor(r.team_id) }} />
                            {n.actual > 0 && <span className="nightbar-seg" style={{ width: `${(n.actual / seasonMax) * 100}%`, background: teamColor(r.team_id) }} />}
                            {n.left > 0.005 && <span className="nightbar-seg" style={{ width: `${(n.left / seasonMax) * 100}%`, background: teamTint(r.team_id) }} />}
                          </div>
                        </div>
                        <SeasonMarks now={now} proj={proj} max={seasonMax} />
                      </div>
                    </div>
                    <span className="row-meta num season-meta">
                      fin ≈ : {ord(after)}
                      {after !== before && (
                        <span className="seasonline-move" style={tone(before - after, 2)}>
                          {' '}
                          {after < before ? '▲' : '▼'} {ord(before)}→{ord(after)}
                        </span>
                      )}
                    </span>
                  </div>
                  {open === `t-${r.team_id}` && <PoolerPlayers r={r} t={t} live={live} sort={teamSort} />}
                </li>
                )
              })}
            </ul>
          </Group>

          <Group id="soir-mes-joueurs" title="Mes joueurs">
            {mine.length ? (
              <>
                <p className="legend-line">« 1 pt → 1,6 » : faits → fin ≈ du match.</p>
                <SortBar options={PLAYER_SORT} sort={playerSort} onChange={setPlayerSort} />
                <ul className="rows">
                  {sortedMine.map(({ p, n }) => (
                    <li key={p.espn_id} className={`row is-clickable${open === `m-${p.espn_id}` ? ' is-open' : ''}`}
                      onClick={() => toggle(`m-${p.espn_id}`)} aria-expanded={open === `m-${p.espn_id}`}>
                      <div className="row-main">
                        <span className="row-name">
                          {lastName(p.name)} {p.injury && <span className="chip is-injury">DTD</span>}
                        </span>
                        <span className="row-meta">
                          {where(p)} · <span className={n.state === 'LIVE' ? 'is-live' : undefined}>{when(p, n)}</span>
                        </span>
                        <NightBar n={n} max={playerMax} teamId={mineId} thin />
                        <NightMarks n={n} max={playerMax} />
                      </div>
                      <div className="row-side">
                        <Score n={{ ...n, started: n.state !== 'FUT' }} />
                      </div>
                      {open === `m-${p.espn_id}` && <PlayerDetail p={p} n={n} live={live} />}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="empty">Aucun de mes joueurs ne joue ce soir.</p>
            )}
          </Group>

          {watch.length > 0 && (
            <Group id="soir-surveiller" title="À surveiller">
              <p className="group-note">
                Les adversaires qui menacent le plus ma 1re place sur la saison, plus les meilleurs joueurs des équipes à
                10 pts ou moins de moi ce soir. À droite : combien sa soirée me nuit, en points à moi (−0,5 = comme si
                je perdais un demi-point). Touche un joueur pour le détail.
              </p>
              <SortBar options={WATCH_SORT} sort={watchSort} onChange={setWatchSort} />
              <ul className="rows">
                {sortedWatch.map(({ p, n, ratio: r, threat, why, gap }) => (
                  <li key={p.espn_id} className={`row is-clickable${open === `w-${p.espn_id}` ? ' is-open' : ''}`}
                    onClick={() => toggle(`w-${p.espn_id}`)} aria-expanded={open === `w-${p.espn_id}`}>
                    <div className="row-main">
                      <span className="row-name">{lastName(p.name)}</span>
                      <span className="row-meta">
                        <PoolerIcon teamId={p.owner.team_id} />
                        {p.owner.name ?? p.owner.abbrev} · {why === 'saison' ? 'menace ma 1re place' : gapText(gap)}
                      </span>
                      <span className="row-meta">
                        {where(p)} · <span className={n.state === 'LIVE' ? 'is-live' : undefined}>{when(p, n)}</span>
                      </span>
                    </div>
                    <div className="row-side">
                      {threat != null ? (
                        <>
                          <span className="row-value num is-small" style={tone(threat, 0.5)}>{signed(threat, 1)}</span>
                          <span className="row-sub">de mes pts</span>
                        </>
                      ) : (
                        <span className="row-sub num">prévu {dec(p.expected)}</span>
                      )}
                      {n.state !== 'FUT' && (
                        <span className="row-sub num">
                          {n.actual} {n.actual >= 2 ? 'pts' : 'pt'}
                          {n.left > 0.005 && <> · reste {dec(n.left)} · <b className="fin">fin ≈ {dec(projection(n))}</b></>}
                        </span>
                      )}
                      <OnePoint n={n} />
                    </div>
                    {open === `w-${p.espn_id}` && (
                      <PlayerDetail p={p} n={n} live={live}>
                        <p className="detail-line num">
                          {r != null && <>1 de ses pts ≈ {signed(r, 2)} de mes pts · </>}
                          <a className="team-link" href={`#equipe/${p.owner.team_id}`} onClick={(e) => e.stopPropagation()}>
                            voir {p.owner.name ?? p.owner.abbrev}
                          </a>
                        </p>
                      </PlayerDetail>
                    )}
                  </li>
                ))}
              </ul>
            </Group>
          )}
        </>
      )}
      <p className="foot">Données de la soirée mises à jour à {clock(t.updated)}</p>
    </>
  )
}
