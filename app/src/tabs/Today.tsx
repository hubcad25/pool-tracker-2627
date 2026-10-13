import TeamLogo from '../components/TeamLogo'
import NightBar, { NightLegend } from '../components/NightBar'
import { SortBar, sortBy, useSort, type SortOption } from '../components/Sort'
import PlayerDetail from '../components/PlayerDetail'
import Sparkline from '../components/Sparkline'
import { clock, dec, lastName, prob, shortDate, signed } from '../format'
import { hasProxy, playerNight, projection, sumNights, teamNight, useLive, type Live, type Night } from '../live'
import { teamColor, teamTint } from '../teams'
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
const when = (p: TonightPlayer, n: Night) => n.clock ?? (n.state === 'FINAL' ? 'Final' : clock(p.start))

/** À droite d'une barre, lisible sans légende :
 *  avant le match « 1,2 / pts prévus » ; pendant « 2 pts / prévu 1,2 · fin ≈ 2,6 » ; fini « 2 pts / prévu 1,2 · ▲ +0,8 ».
 *  Fin ≈ fait + le prévu du temps qui reste. L'écart d'un match fini = réel − prévu. */
function Score({ n, big }: { n: ReturnType<typeof sumNights> & { started: boolean }; big?: boolean }) {
  const cls = `row-value num${big ? '' : ' is-small'}`
  if (!n.started) {
    return (
      <>
        <span className={`${cls} is-data`}>{dec(n.expected)}</span>
        <span className="row-sub">pts prévus</span>
      </>
    )
  }
  const playing = n.left > 0.005
  const gap = n.actual - (n.expected - n.left)
  return (
    <>
      <span className={cls}>
        {n.actual} <small>{n.actual >= 2 ? 'pts' : 'pt'}</small>
      </span>
      <span className="row-sub num">
        prévu <span className="is-data">{dec(n.expected)}</span> ·{' '}
        {playing ? (
          <>fin ≈ {dec(projection(n))}</>
        ) : (
          <span style={tone(gap, 2)}>{Math.abs(gap) < 0.05 ? '= prévu' : `${arrow(gap)}${signed(gap)}`}</span>
        )}
      </span>
    </>
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

/** Au bout de la barre « ce soir » d'une équipe : « 13,8 pts prévus » avant les matchs, « 2 pts » ensuite */
function TeamScore({ n }: { n: ReturnType<typeof sumNights> & { started: boolean } }) {
  return (
    <span className="row-value num team-score">
      {n.started ? (
        <>
          {n.actual} <small>{n.actual >= 2 ? 'pts' : 'pt'}</small>
        </>
      ) : (
        <>
          <span className="is-data">{dec(n.expected)}</span> <small>pts prévus</small>
        </>
      )}
    </span>
  )
}

/** Pendant la soirée, sur la ligne du haut : « prévu 13,8 · fin ≈ 14,1 », ou l'écart une fois tout fini */
function ScoreSub({ n }: { n: ReturnType<typeof sumNights> }) {
  const gap = n.actual - (n.expected - n.left)
  return (
    <span className="num">
      prévu <span className="is-data">{dec(n.expected)}</span> ·{' '}
      {n.left > 0.005 ? (
        <>fin ≈ {dec(projection(n))}</>
      ) : (
        <span style={tone(gap, 2)}>{Math.abs(gap) < 0.05 ? '= prévu' : `${arrow(gap)}${signed(gap)}`}</span>
      )}
    </span>
  )
}

/** Les joueurs d'un pooler ce soir, les meilleurs d'abord (projection) ; chacun se déplie sur son match */
function PoolerPlayers({ r, t, live }: { r: TodayTeam; t: T; live: Live }) {
  const [open, setOpen] = useState<number | null>(null)
  const rows = (r.players ?? []).map((p) => ({ p, n: playerNight(p, t, live) })).sort((a, b) => projection(b.n) - projection(a.n))
  const max = Math.max(1, ...rows.map(({ n }) => Math.max(n.expected, n.actual + n.left + n.lost)))
  if (!rows.length) return <div className="player-detail">Aucun joueur ce soir.</div>
  return (
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
          </div>
          <div className="row-side">
            <Score n={{ ...n, started: n.state !== 'FUT' }} />
          </div>
          {open === p.espn_id && <PlayerDetail p={p} n={n} live={live} />}
        </li>
      ))}
    </ul>
  )
}

type TeamKey = 'proj' | 'season' | 'expected' | 'actual' | 'p_first' | 'name'
const TEAM_SORT: SortOption<TeamKey>[] = [
  { key: 'proj', label: 'Projection', dir: 'desc' },
  { key: 'season', label: 'Saison + ce soir', dir: 'desc' },
  { key: 'expected', label: 'Attendu (avant-match)', dir: 'desc' },
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

type PlayerKey = 'start' | 'proj' | 'expected' | 'actual' | 'name'
const PLAYER_SORT: SortOption<PlayerKey>[] = [
  { key: 'start', label: 'Heure', dir: 'asc' },
  { key: 'proj', label: 'Projection', dir: 'desc' },
  { key: 'expected', label: 'Attendu', dir: 'desc' },
  { key: 'actual', label: 'Réel', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

type WatchKey = 'threat' | 'expected' | 'start'
const WATCH_EACH = 5

const nextDay = (iso: string) => new Date(Date.parse(`${iso}T12:00:00Z`) + 86_400_000).toISOString().slice(0, 10)

/** Ma P(1er) avec la soirée : chaque total final du matin − l'attendu de ce soir + réel + encore possible.
 *  On ajoute à la P(1er) du matin l'écart entre les deux calculs (mêmes arrondis des deux côtés : 0 avant les matchs).
 *  null sans les totaux du matin (vieux today.json) ou avant le premier match. */
function liveFirst(morning: number | null | undefined, teams: { r: TodayTeam; n: ReturnType<typeof teamNight> }[]) {
  if (morning == null || !teams.some(({ n }) => n.started)) return null
  if (teams.some(({ r }) => r.final == null || r.sd == null)) return null
  const me = teams.findIndex(({ r }) => r.mine)
  if (me < 0) return null
  const sds = teams.map(({ r }) => r.sd!)
  const before = firstPlaceOdds(teams.map(({ r }) => r.final!), sds)[me]
  const after = firstPlaceOdds(teams.map(({ r, n }) => r.final! - n.expected + projection(n)), sds)[me]
  return Math.min(1, Math.max(0, morning + after - before))
}
const CLOSE_PTS = 10
const WATCH_SORT: SortOption<WatchKey>[] = [
  { key: 'threat', label: 'Menace', dir: 'asc' },
  { key: 'expected', label: 'Attendu', dir: 'desc' },
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
  const pLive = liveFirst(pf?.now, teams)
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
    : k === 'season' ? proj
    : k === 'p_first' ? r.p_first
    : k === 'expected' ? n.expected
    : k === 'actual' ? n.actual
    : (r.name ?? r.abbrev ?? ''),
  )

  const me = t.teams.find((r) => r.mine)
  const mineId = me?.team_id ?? 0
  const mine = t.my_players.map((p) => ({ p, n: playerNight(p, t, live) }))
  const playerMax = Math.max(1, ...mine.map(({ n }) => Math.max(n.expected, n.actual + n.left + n.lost)))
  const sortedMine = sortBy(mine, playerSort, ({ p, n }, k) =>
    k === 'start' ? p.start : k === 'proj' ? projection(n) : k === 'expected' ? n.expected : k === 'actual' ? n.actual : lastName(p.name),
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
    k === 'threat' ? w.threat : k === 'expected' ? w.p.expected : w.p.start,
  )

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
          <section className="group">
            <h2 className="group-title">Ce soir · {shortDate(t.date)}</h2>
            <LiveStatus live={live} t={t} />
            <p className="group-note">Même échelle pour toutes les équipes.</p>
            <NightLegend />
            <p className="legend-line">
              « ce soir » et « saison » n'ont pas la même échelle. Saison : les points d'avant ce soir (pâle), puis la soirée au bout. « 71 → 74,3 » : maintenant → avec la projection du soir.
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
                      <i className="swatch" style={{ background: teamColor(r.team_id) }} />
                      {r.name}
                    </a>
                    <span className="row-meta">
                      {r.p_first != null && <>P(1er) {prob(r.p_first)} · </>}
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
                      {ord(after)} avec la projection
                      {after !== before && (
                        <span className="seasonline-move" style={tone(before - after, 2)}>
                          {' '}
                          {after < before ? '▲' : '▼'} {ord(before)}→{ord(after)}
                        </span>
                      )}
                    </span>
                  </div>
                  {open === `t-${r.team_id}` && <PoolerPlayers r={r} t={t} live={live} />}
                </li>
                )
              })}
            </ul>
          </section>

          <section className="group">
            <h2 className="group-title">Mes joueurs</h2>
            {mine.length ? (
              <>
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
          </section>

          {watch.length > 0 && (
            <section className="group">
              <h2 className="group-title">À surveiller</h2>
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
                        <i className="swatch" style={{ background: teamColor(p.owner.team_id) }} />
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
                    </div>
                    {open === `w-${p.espn_id}` && (
                      <PlayerDetail p={p} n={n} live={live}>
                        <p className="detail-line num">
                          {n.state === 'FUT' ? <>Prévu {dec(p.expected)} pt</> : <>{n.actual} {n.actual >= 2 ? 'pts' : 'pt'} · prévu {dec(p.expected)}</>}
                          {r != null && <> · 1 de ses pts ≈ {signed(r, 2)} de mes pts</>}
                          {' · '}
                          <a className="team-link" href={`#equipe/${p.owner.team_id}`} onClick={(e) => e.stopPropagation()}>
                            voir {p.owner.name ?? p.owner.abbrev}
                          </a>
                        </p>
                      </PlayerDetail>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      <p className="foot">Données de la soirée mises à jour à {clock(t.updated)}</p>
    </>
  )
}
