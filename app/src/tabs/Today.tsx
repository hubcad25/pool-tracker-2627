import NightBar, { NightLegend } from '../components/NightBar'
import { SortBar, sortBy, useSort, type SortOption } from '../components/Sort'
import Sparkline from '../components/Sparkline'
import { clock, dec, lastName, prob, shortDate, signed } from '../format'
import { hasProxy, playerNight, projection, sumNights, teamNight, useLive, type Live, type Night } from '../live'
import { gridTicks } from '../components/Band'
import { teamColor, teamTint } from '../teams'
import { arrow, tone } from '../tone'
import type { Today as T, TodayTeam, TonightPlayer } from '../types'

const where = (p: TonightPlayer) => `${p.pos ? `${p.pos} · ` : ''}${p.team} ${p.opp.startsWith('@') ? p.opp : `vs ${p.opp}`}`

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

type TeamKey = 'proj' | 'expected' | 'actual' | 'p_first' | 'name'
const TEAM_SORT: SortOption<TeamKey>[] = [
  { key: 'proj', label: 'Projection', dir: 'desc' },
  { key: 'expected', label: 'Attendu (avant-match)', dir: 'desc' },
  { key: 'actual', label: 'Réel', dir: 'desc' },
  { key: 'p_first', label: 'P(1er)', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

type SeasonKey = 'proj' | 'now' | 'name'
const SEASON_SORT: SortOption<SeasonKey>[] = [
  { key: 'proj', label: 'Avec ce soir', dir: 'desc' },
  { key: 'now', label: 'Points', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

/** Points de la saison avant la soirée (today.json réécrit pendant la soirée compte déjà les matchs terminés) */
const base = (r: TodayTeam) => r.points - (r.actual_tonight ?? 0)

const ord = (n: number) => (n === 1 ? '1er' : `${n}e`)

type PlayerKey = 'start' | 'proj' | 'expected' | 'actual' | 'name'
const PLAYER_SORT: SortOption<PlayerKey>[] = [
  { key: 'start', label: 'Heure', dir: 'asc' },
  { key: 'proj', label: 'Projection', dir: 'desc' },
  { key: 'expected', label: 'Attendu', dir: 'desc' },
  { key: 'actual', label: 'Réel', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

type WatchKey = 'threat' | 'expected' | 'start'
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
  const pf = t.p_first
  const diff = pf?.now != null && pf.yesterday != null ? pf.now - pf.yesterday : null
  const noGames = t.games.length === 0

  const teams = t.teams.map((r) => ({ r, n: teamNight(r, t, live) }))
  const max = Math.max(1, ...teams.map(({ n }) => Math.max(n.expected, n.actual + n.left + n.lost)))
  const sortedTeams = sortBy(teams, teamSort, ({ r, n }, k) =>
    k === 'proj' ? projection(n)
    : k === 'p_first' ? r.p_first
    : k === 'expected' ? n.expected
    : k === 'actual' ? n.actual
    : (r.name ?? r.abbrev ?? ''),
  )

  // Saison : les points d'avant la soirée (today.json réécrit pendant la soirée compte déjà les matchs terminés),
  // + le réel en direct, + la projection du soir. Rang = classement par points, avant et après la projection.
  const [seasonSort, setSeasonSort] = useSort('aujourdhui-saison', SEASON_SORT)
  const season = teams.map(({ r, n }) => {
    return { r, n, now: base(r) + n.actual, proj: base(r) + projection(n) }
  })
  const rankBy = (key: 'now' | 'proj') => {
    const order = [...season].sort((a, b) => b[key] - a[key])
    return new Map(season.map((x) => [x.r.team_id, order.findIndex((y) => y[key] <= x[key]) + 1]))
  }
  const rankNow = rankBy('now')
  const rankProj = rankBy('proj')
  const seasonMax = Math.max(1, ...season.map((x) => base(x.r) + x.n.actual + x.n.left + x.n.lost))
  const sortedSeason = sortBy(season, seasonSort, (x, k) => (k === 'proj' ? x.proj : k === 'now' ? x.now : (x.r.name ?? x.r.abbrev ?? '')))

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
  const watch = t.watch.map((p) => {
    const r = ratio(p.delta_p_first_per_point)
    const n = playerNight(p, t, live)
    // Menace = ses points projetés de la soirée (réel + ce qui reste possible) × l'impact d'un de ses points
    return { p, n, ratio: r, threat: r == null ? null : (n.actual + n.left) * r }
  })
  const sortedWatch = sortBy(watch, watchSort, (w, k) =>
    k === 'threat' ? (w.threat ?? w.p.threat) : k === 'expected' ? w.p.expected : w.p.start,
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
          </div>
          <Sparkline points={pf.history} />
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
            <SortBar options={TEAM_SORT} sort={teamSort} onChange={setTeamSort} />
            <ul className="rows">
              {sortedTeams.map(({ r, n }) => (
                <li key={r.team_id} className={`row tonight${r.mine ? ' is-mine' : ''}`}>
                  <div className="row-main">
                    <a className="row-name team-link" href={`#equipe/${r.team_id}`}>
                      <i className="swatch" style={{ background: teamColor(r.team_id) }} />
                      {r.name}
                    </a>
                    <span className="row-meta">
                      {r.p_first != null && <>P(1er) {prob(r.p_first)} · </>}
                      {r.playing_tonight} joueur{r.playing_tonight > 1 ? 's' : ''}
                    </span>
                    <NightBar n={n} max={max} teamId={r.team_id} />
                  </div>
                  <div className="row-side">
                    <Score n={n} big />
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="group">
            <h2 className="group-title">Saison</h2>
            <p className="legend-line">
              Points de la saison, puis au bout la soirée (mêmes couleurs qu'en haut). « 71 → 74,3 » : maintenant → avec la
              projection du soir.
            </p>
            <SortBar options={SEASON_SORT} sort={seasonSort} onChange={setSeasonSort} />
            <ul className="rows">
              {sortedSeason.map(({ r, n, now, proj }) => {
                const before = rankNow.get(r.team_id)!
                const after = rankProj.get(r.team_id)!
                return (
                  <li key={r.team_id} className={`row seasonline${r.mine ? ' is-mine' : ''}`}>
                    <div className="seasonline-top">
                      <a className="seasonline-name team-link" href={`#equipe/${r.team_id}`}>
                        <span className="seasonline-rank num">{ord(after)}</span>
                        <i className="swatch" style={{ background: teamColor(r.team_id) }} />
                        {r.name}
                      </a>
                      <span className="seasonline-value num">
                        {dec(now, Number.isInteger(now) ? 0 : 1)} → <b className="is-data">{dec(proj)}</b>
                        {after !== before && (
                          <span className="seasonline-move" style={tone(before - after, 2)}>
                            {' '}
                            {after < before ? '▲' : '▼'} {ord(before)}→{ord(after)}
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="ptsbar" role="img" aria-label={`${dec(base(r))} pts avant ce soir, puis la soirée`}>
                      {gridTicks(seasonMax).map((g) => (
                        <span key={g} className="band-tick" style={{ left: `${(g / seasonMax) * 100}%` }} />
                      ))}
                      <div className="nightbar-track">
                        <span className="nightbar-seg ptsbar-base" style={{ width: `${(base(r) / seasonMax) * 100}%`, background: teamColor(r.team_id) }} />
                        {n.actual > 0 && <span className="nightbar-seg" style={{ width: `${(n.actual / seasonMax) * 100}%`, background: teamColor(r.team_id) }} />}
                        {n.left > 0.005 && <span className="nightbar-seg" style={{ width: `${(n.left / seasonMax) * 100}%`, background: teamTint(r.team_id) }} />}
                        {n.lost > 0.005 && <span className="nightbar-seg is-lost" style={{ width: `${(n.lost / seasonMax) * 100}%` }} />}
                      </div>
                    </div>
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
                    <li key={p.espn_id} className="row">
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
                Les joueurs adverses de ce soir qui menacent le plus ma 1re place, en équivalent de mes points :
                « 1 pt ≈ −0,3 » veut dire qu'un point de ce joueur me nuit comme si je perdais 0,3 point. À droite, la
                menace de sa soirée (points réels + encore possibles, convertis en mes points).
              </p>
              <SortBar options={WATCH_SORT} sort={watchSort} onChange={setWatchSort} />
              <ul className="rows">
                {sortedWatch.map(({ p, n, ratio: r, threat }) => (
                  <li key={p.espn_id} className="row">
                    <div className="row-main">
                      <span className="row-name">
                        {lastName(p.name)}{' '}
                        <a className="row-owner team-link" href={`#equipe/${p.owner.team_id}`}>
                          <i className="swatch" style={{ background: teamColor(p.owner.team_id) }} />
                          {p.owner.name ?? p.owner.abbrev}
                        </a>
                      </span>
                      <span className="row-meta">
                        {where(p)} · <span className={n.state === 'LIVE' ? 'is-live' : undefined}>{when(p, n)}</span>
                      </span>
                      {r != null ? (
                        <span className="row-meta">
                          1 pt ≈ <b className="nowrap" style={tone(r, 0.6)}>{signed(r, 2)}</b> de mes pts
                          {p.delta_p_first_per_point != null && (
                            <span className="row-fine"> · P(1er) {signed(p.delta_p_first_per_point * 100, 2)} pt</span>
                          )}
                        </span>
                      ) : (
                        p.delta_p_first_per_point != null && (
                          <span className="row-meta">S'il fait 1 pt : ma P(1er) {signed(p.delta_p_first_per_point * 100)} pt</span>
                        )
                      )}
                    </div>
                    <div className="row-side">
                      {threat != null && (
                        <span className="row-value num is-small" style={tone(threat, 0.5)} title="Menace : points projetés ce soir (réel + reste) × impact d'un point">
                          {arrow(threat, 0.005)}{signed(threat, 2)}
                        </span>
                      )}
                      <span className="row-sub num">
                        {n.state === 'FUT' ? <>prévu {dec(p.expected)}</> : <>{n.actual} {n.actual >= 2 ? 'pts' : 'pt'} · prévu {dec(p.expected)}</>}
                      </span>
                    </div>
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
