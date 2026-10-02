import type { Player } from '../types'

/** Position relative au total projeté et à la bande préseason (au même nombre de matchs). */
export function standing(p: Player): 'above' | 'below' | null {
  if (!p.final || !p.prior) return null
  if (p.final.mean > p.prior.p90) return 'above'
  if (p.final.mean < p.prior.p10) return 'below'
  return null
}

const at = (x: number, max: number) => `${(Math.max(0, Math.min(x, max)) / max) * 100}%`

/** Une ligne à l'échelle des points de fin de saison, commune à toute l'équipe :
 *  bande préseason p10–p90 (gris), points acquis (barre pleine), total final projeté ◆ et son p10–p90. */
export default function Band({ player: p, max, ticks }: { player: Player; max: number; ticks: number[] }) {
  const s = standing(p)
  return (
    <div className="band" aria-hidden="true">
      {ticks.map((t) => (
        <span key={t} className="band-tick" style={{ left: at(t, max) }} />
      ))}
      {p.prior && (
        <span className="band-prior" style={{ left: at(p.prior.p10, max), right: `calc(100% - ${at(p.prior.p90, max)})` }}>
          <span className="band-prior-mid" style={{ left: at(p.prior.p50 - p.prior.p10, p.prior.p90 - p.prior.p10) }} />
        </span>
      )}
      {p.points > 0 && <span className="band-points" style={{ width: at(p.points, max) }} />}
      {p.final && (
        <>
          <span className="band-interval" style={{ left: at(p.final.p10, max), right: `calc(100% - ${at(p.final.p90, max)})` }} />
          <span className={`band-final${s ? ` is-${s}` : ''}`} style={{ left: at(p.final.mean, max) }} />
        </>
      )}
    </div>
  )
}

export function BandScale({ max, ticks }: { max: number; ticks: number[] }) {
  return (
    <div className="band-scale" aria-hidden="true">
      {ticks.map((t) => (
        <span key={t} className="num" style={{ left: at(t, max) }}>
          {t}
        </span>
      ))}
    </div>
  )
}
