import { dec } from '../format'
import { teamColor, teamTint } from '../teams'

type Parts = { actual: number; expected: number; left: number; lost: number }

const pct = (x: number, max: number) => `${(Math.max(0, x) / max) * 100}%`

/** La soirée en une barre, à une échelle commune (`max`). Longueur pleine = la projection (réel, plein, puis
 *  encore possible, clair) ; au bout, le perdu hachuré et pâle ; trait = l'attendu d'avant-match. Avant le premier
 *  match, la projection est l'attendu. */
export default function NightBar({ n, max, teamId, thin }: { n: Parts; max: number; teamId: number; thin?: boolean }) {
  const label = `${n.actual} faits, fin ≈ ${dec(n.actual + n.left)}, ${dec(n.lost)} perdus, ${dec(n.expected)} prévus`
  return (
    <div className={`nightbar${thin ? ' is-thin' : ''}`} role="img" aria-label={label} title={label}>
      <div className="nightbar-track">
        {n.actual > 0 && <span className="nightbar-seg" style={{ width: pct(n.actual, max), background: teamColor(teamId) }} />}
        {n.left > 0.005 && <span className="nightbar-seg" style={{ width: pct(n.left, max), background: teamTint(teamId) }} />}
        {n.lost > 0.005 && <span className="nightbar-seg is-lost" style={{ width: pct(n.lost, max) }} />}
      </div>
      <span className="nightbar-expected" style={{ left: pct(n.expected, max) }} />
    </div>
  )
}

/** Légende des barres de la soirée */
export function NightLegend() {
  return (
    <p className="legend-line">
      <i className="lg-swatch" style={{ background: 'var(--text-dim)' }} /> points faits +{' '}
      <i className="lg-swatch" style={{ background: 'color-mix(in oklab, var(--text-dim) 35%, var(--surface-1))' }} /> encore
      possibles ; <i className="lg-swatch is-lost" /> perdus ; <i className="lg-tick" /> prévu.
      <b>Fin ≈</b> : faits + ce qui reste à jouer. <b>Prévu</b> (le trait) : avant les matchs, ne bouge plus.
    </p>
  )
}
