import type { Player, Range } from '../types'

/** ~Centile de la ROS moyenne dans la bande préseason ramenée aux mêmes matchs (interpolation p10 / p50 / p90,
 *  prolongée au-delà) : 0,5 = ce qu'on prévoyait avant la saison. */
export function rosQuantile(mean: number, pr: Range): number {
  const lin = (x: number, x0: number, x1: number, y0: number, y1: number) => (x1 === x0 ? y0 : y0 + ((x - x0) / (x1 - x0)) * (y1 - y0))
  const q =
    mean <= pr.p10 ? lin(mean, pr.p10 - (pr.p50 - pr.p10), pr.p10, 0, 0.1)
    : mean <= pr.p50 ? lin(mean, pr.p10, pr.p50, 0.1, 0.5)
    : mean <= pr.p90 ? lin(mean, pr.p50, pr.p90, 0.5, 0.9)
    : lin(mean, pr.p90, pr.p90 + (pr.p90 - pr.p50), 0.9, 1)
  return Math.max(0.01, Math.min(0.99, q))
}

/** « ↑ vs préseason » / « ↓ vs préseason » / « ≈ préseason » */
export const vsPreseason = (q: number) => (q >= 0.6 ? '↑ vs préseason' : q <= 0.4 ? '↓ vs préseason' : '≈ préseason')

// Couleur pleine à ±6 pts de chance
export const LUCK_FULL = 6

/** Le segment de chance sur la barre : nettement vert (chanceux) ou rouge (malchanceux), même petit ; un peu
 *  moins saturé avant 10 matchs, jamais effacé. */
const luckFill = (net: number, small: boolean) =>
  `color-mix(in oklab, var(${net > 0 ? '--good' : '--danger'}) ${small ? 80 : 100}%, var(--surface-1))`

const at = (x: number, max: number) => `${(Math.max(0, Math.min(x, max)) / max) * 100}%`

/** Graduations très pâles tous les 10 points */
export const gridTicks = (max: number) => Array.from({ length: Math.floor(max / 10) + 1 }, (_, i) => i * 10)

/** La saison d'un joueur en une barre, à l'échelle commune de l'équipe :
 *  1. points faits (plein) puis ROS (clair) jusqu'au total estimé ;
 *  2. la fourchette probable du total, au bout ;
 *  3. l'écart entre ses points et ceux qu'il aurait avec une chance normale : un bloc vert (chanceux) ou rouge
 *     (malchanceux), 8 px au moins pour rester visible à cette échelle ; un simple trait s'il n'y a pas d'écart.
 *  En dessous, une fine rangée : la fourchette préseason du total final (p10–p90, trait à p50), mêmes matchs. */
export default function Band({ player: p, max }: { player: Player; max: number }) {
  const exp = p.group !== 'G' ? p.luck?.expected_points : undefined
  const net = exp != null ? p.points - exp : 0
  const small = p.verdict === 'petit_echantillon'
  const pr = p.prior
  return (
    <>
    <div className="band" aria-hidden="true">
      {gridTicks(max).map((t) => (
        <span key={t} className="band-tick" style={{ left: at(t, max) }} />
      ))}
      <span className="band-real" style={{ width: at(p.points, max) }} />
      {p.ros && <span className="band-ros" style={{ left: at(p.points, max), width: at(p.ros.mean, max) }} />}
      {p.final && <span className="band-range" style={{ left: at(p.final.p10, max), width: at(p.final.p90 - p.final.p10, max) }} />}
      {exp != null && (
        <>
          {Math.abs(net) >= 0.1 && (
            <span
              className="band-luck"
              style={{ left: at(Math.min(exp, p.points), max), width: at(Math.abs(net), max), background: luckFill(net, small) }}
            />
          )}
          {Math.abs(net) < 0.1 && <span className="band-luck-mark" style={{ left: at(exp, max) }} />}
        </>
      )}
    </div>
    {pr && (
      <div className="band-prior-row" aria-hidden="true">
        {gridTicks(max).map((t) => (
          <span key={t} className="band-tick" style={{ left: at(t, max) }} />
        ))}
        <span className="band-prior" style={{ left: at(pr.p10, max), width: at(pr.p90 - pr.p10, max) }} />
        <span className="band-prior-mid" style={{ left: at(pr.p50, max) }} />
      </div>
    )}
    </>
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
