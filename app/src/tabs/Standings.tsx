import { dec, int } from '../format'
import type { Standing } from '../types'

export default function Standings({ rows }: { rows: Standing[] }) {
  const lo = Math.min(...rows.map((r) => r.p10))
  const hi = Math.max(...rows.map((r) => r.p90))
  const at = (x: number) => `${((x - lo) / (hi - lo)) * 100}%`
  return (
    <section className="group">
      <p className="group-note">
        Total final = points actuels + ROS du meilleur alignement (10 F, 5 D, IR compris, sans gardien).
        P(1er) : simulation, joueurs indépendants (donc un peu trop sûre d'elle).
      </p>
      <ol className="rows standings">
        {rows.map((r, i) => (
          <li key={r.team_id} className={`row standing${r.mine ? ' is-mine' : ''}`}>
            <span className="standing-rank num">{i + 1}</span>
            <div className="row-main">
              <span className="row-name">{r.name}</span>
              <span className="row-meta num">
                {int(r.points)} pts · final {int(r.final)} ({int(r.p10)}–{int(r.p90)})
              </span>
              <div className="standing-range" aria-hidden="true">
                <span className="standing-interval" style={{ left: at(r.p10), right: `calc(100% - ${at(r.p90)})` }} />
                <span className="standing-mean" style={{ left: at(r.final) }} />
              </div>
            </div>
            <div className="row-side">
              <span className="row-value num">{r.p_first < 0.001 ? '<0,1' : dec(r.p_first * 100, r.p_first < 0.1 ? 1 : 0)} %</span>
              <span className="row-sub">P(1er)</span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
