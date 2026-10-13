import { SortBar, sortBy, useSort, type SortOption } from '../components/Sort'
import { int, prob, signed } from '../format'
import { teamColor, teamTint } from '../teams'
import { teamLuckPhrase } from '../luck'
import { arrow, tone, toneFill } from '../tone'
import type { Standing } from '../types'

type Key = 'final' | 'p_first' | 'points' | 'ros' | 'name'
const SORT: SortOption<Key>[] = [
  { key: 'final', label: 'Total', dir: 'desc' },
  { key: 'p_first', label: 'P(1er)', dir: 'desc' },
  { key: 'points', label: 'Pts', dir: 'desc' },
  { key: 'ros', label: 'ROS', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

type LuckKey = 'luck' | 'name'
const LUCK_SORT: SortOption<LuckKey>[] = [
  { key: 'luck', label: 'Chance', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

const at = (x: number, max: number) => `${(Math.max(0, x) / max) * 100}%`
const name = (r: Standing) => r.name ?? r.abbrev ?? ''

/** Points acquis (plein) + ROS (clair) et fourchette p10–p90 du total. */
function SeasonBar({ r, max }: { r: Standing; max: number }) {
  const lo = r.points + (r.ros_p10 ?? r.p10 - r.points)
  const hi = r.points + (r.ros_p90 ?? r.p90 - r.points)
  const label = `${int(r.points)} pts acquis + ROS ${int(r.ros)} = ${int(r.final)} (${int(lo)}–${int(hi)})`
  return (
    <div className="seasonbar" role="img" aria-label={label} title={label}>
      <div className="seasonbar-track">
        <span className="nightbar-seg" style={{ width: at(r.points, max), background: teamColor(r.team_id) }} />
        <span className="nightbar-seg" style={{ width: at(r.ros, max), background: teamTint(r.team_id) }} />
      </div>
      <span className="seasonbar-range" style={{ left: at(lo, max), width: at(hi - lo, max) }} />
    </div>
  )
}

function Luck({ rows }: { rows: Standing[] }) {
  const [sort, setSort] = useSort('ligue-chance', LUCK_SORT)
  const withLuck = rows.filter((r) => r.luck_points != null)
  if (!withLuck.length) return null
  const maxAbs = Math.max(1, ...withLuck.map((r) => Math.abs(r.luck_points!)))
  const sorted = sortBy(withLuck, sort, (r, k) => (k === 'luck' ? r.luck_points! : name(r)))
  return (
    <section className="group">
      <h2 className="group-title">Chance de la saison</h2>
      <p className="group-note">
        Les points que la chance a donnés (+) ou enlevés (−) à chaque équipe cette saison, joueurs de l'alignement
        actuel.
      </p>
      <SortBar options={LUCK_SORT} sort={sort} onChange={setSort} />
      <ul className="rows">
        {sorted.map((r) => {
          const x = r.luck_points!
          const full = Math.max(6, maxAbs)
          return (
            <li key={r.team_id} className={`row luckrow${r.mine ? ' is-mine' : ''}`} title={`${name(r)} : ${teamLuckPhrase(x)}`}>
              <a className="luckrow-name team-link" href={`#equipe/${r.team_id}`}>
                <i className="swatch" style={{ background: teamColor(r.team_id) }} />
                {name(r)}
              </a>
              <div className="diverge" aria-hidden="true">
                <span className="diverge-mid" />
                <span
                  className={`diverge-bar${x >= 0 ? ' is-right' : ' is-left'}`}
                  style={{
                    ...(x >= 0 ? { left: '50%', width: `${(x / maxAbs) * 50}%` } : { right: '50%', width: `${(-x / maxAbs) * 50}%` }),
                    background: toneFill(x, full),
                  }}
                />
              </div>
              <span className="luckrow-value num" style={tone(x, full)}>
                {arrow(x, 0.5)}
                {signed(x)}
              </span>
            </li>
          )
        })}
      </ul>
      <div className="diverge-ends">
        <span>◀ malchanceuse</span>
        <span>chanceuse ▶</span>
      </div>
    </section>
  )
}

export default function Standings({ rows }: { rows: Standing[] }) {
  const [sort, setSort] = useSort('ligue', SORT)
  const max = Math.max(...rows.map((r) => r.points + (r.ros_p90 ?? r.p90 - r.points)))
  const me = rows.find((r) => r.mine)
  const sorted = sortBy(rows, sort, (r, k) =>
    k === 'final' ? r.final : k === 'p_first' ? r.p_first : k === 'points' ? r.points : k === 'ros' ? r.ros : name(r),
  )
  return (
    <>
      <section className="group">
        <h2 className="group-title">Fin de saison projetée</h2>
        <p className="legend-line">
          <i className="lg-swatch" style={{ background: 'var(--text-dim)' }} /> points acquis +{' '}
          <i className="lg-swatch" style={{ background: 'color-mix(in oklab, var(--text-dim) 35%, var(--surface-1))' }} /> ROS =
          total estimé <i className="lg-range" /> fourchette.
        </p>
        <SortBar options={SORT} sort={sort} onChange={setSort} />
        <ol className="rows standings">
          {sorted.map((r) => {
            const gap = me && !r.mine ? r.final - me.final : null
            return (
              <li key={r.team_id} className={`row standing${r.mine ? ' is-mine' : ''}`}>
                <div className="row-main">
                  <a className="row-name team-link" href={`#equipe/${r.team_id}`}>
                    <i className="swatch" style={{ background: teamColor(r.team_id) }} />
                    {name(r)}
                  </a>
                  <span className="row-meta num">
                    {int(r.points)} + ROS <b className="is-data">{int(r.ros)}</b> = <b>{int(r.final)}</b>
                    {gap != null && <> · {signed(gap, 0)} vs moi</>}
                  </span>
                  <SeasonBar r={r} max={max} />
                </div>
                <div className="row-side">
                  <span className="row-value num">{prob(r.p_first)}</span>
                  <span className="row-sub">P(1er)</span>
                </div>
              </li>
            )
          })}
        </ol>
      </section>
      <Luck rows={rows} />
    </>
  )
}
