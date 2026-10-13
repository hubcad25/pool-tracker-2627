import Group from '../components/Group'
import { SortBar, sortBy, useSort, type SortOption } from '../components/Sort'
import { dec, int, prob, signed } from '../format'
import { teamNight, useLive } from '../live'
import { teamColor, teamTint } from '../teams'
import { teamLuckPhrase } from '../luck'
import { arrow, tone, toneFill } from '../tone'
import type { Standing, Today } from '../types'

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

/** Points acquis (plein) + ROS (clair) et fourchette p10–p90 du total. `tonight` : points encore attendus ce
 *  soir (barre mince juste après les acquis, prise à même la ROS : elle les compte déjà). */
function SeasonBar({ r, max, tonight }: { r: Standing; max: number; tonight: number }) {
  const lo = r.points + (r.ros_p10 ?? r.p10 - r.points)
  const hi = r.points + (r.ros_p90 ?? r.p90 - r.points)
  const night = Math.min(tonight, r.ros)
  const label = `${int(r.points)} pts acquis + ROS ${int(r.ros)} = ${int(r.final)} (${int(lo)}–${int(hi)})`
    + (night > 0.005 ? ` · ${dec(night)} pts encore possibles ce soir` : '')
  return (
    <div className="seasonbar" role="img" aria-label={label} title={label}>
      <div className="seasonbar-track">
        <span className="nightbar-seg" style={{ width: at(r.points, max), background: teamColor(r.team_id) }} />
        {night > 0.005 && <span className="nightbar-seg seasonbar-tonight" style={{ width: at(night, max), background: teamColor(r.team_id) }} />}
        <span className="nightbar-seg" style={{ width: at(r.ros - night, max), background: teamTint(r.team_id) }} />
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
    <Group id="classement-chance" title="Chance de la saison">
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
    </Group>
  )
}

export default function Standings({ rows, today }: { rows: Standing[]; today: Today | null }) {
  const [sort, setSort] = useSort('ligue', SORT)
  // Ce soir : les attendus des matchs pas encore finis (en direct si possible) ; rien sans soirée
  const live = useLive(today)
  const tonight = new Map((today?.teams ?? []).map((r) => [r.team_id, teamNight(r, today!, live).left]))
  const anyTonight = [...tonight.values()].some((x) => x > 0.005)
  const max = Math.max(...rows.map((r) => r.points + (r.ros_p90 ?? r.p90 - r.points)))
  const me = rows.find((r) => r.mine)
  const sorted = sortBy(rows, sort, (r, k) =>
    k === 'final' ? r.final : k === 'p_first' ? r.p_first : k === 'points' ? r.points : k === 'ros' ? r.ros : name(r),
  )
  return (
    <>
      <Group id="classement-fin" title="Fin de saison projetée">
        <p className="legend-line">
          <i className="lg-swatch" style={{ background: 'var(--text-dim)' }} /> points acquis +{' '}
          <i className="lg-swatch" style={{ background: 'color-mix(in oklab, var(--text-dim) 35%, var(--surface-1))' }} /> ROS =
          total estimé <i className="lg-range" /> fourchette.
          {anyTonight && (
            <>
              {' '}<i className="lg-swatch is-tonight" style={{ background: 'var(--text-dim)' }} /> points encore possibles ce soir
              (pris dans la ROS).
            </>
          )}
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
                  <SeasonBar r={r} max={max} tonight={tonight.get(r.team_id) ?? 0} />
                </div>
                <div className="row-side">
                  <span className="row-value num">{prob(r.p_first)}</span>
                  <span className="row-sub">P(1er)</span>
                </div>
              </li>
            )
          })}
        </ol>
      </Group>
      <Luck rows={rows} />
    </>
  )
}
