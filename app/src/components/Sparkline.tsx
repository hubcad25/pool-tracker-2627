import { shortDate, prob } from '../format'

const W = 120
const H = 36
const PAD = 4

/** Trace de ma P(1er) sur les derniers jours. Une seule série : pas de légende, dernier point marqué. */
export default function Sparkline({ points }: { points: { day: string; p_first: number }[] }) {
  if (points.length < 2) return null
  const ys = points.map((p) => p.p_first)
  const lo = Math.min(...ys)
  const hi = Math.max(...ys)
  const span = hi - lo || 0.01
  const x = (i: number) => PAD + (i / (points.length - 1)) * (W - 2 * PAD)
  const y = (v: number) => PAD + (1 - (v - lo) / span) * (H - 2 * PAD)
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.p_first).toFixed(1)}`).join(' ')
  const last = points.length - 1
  return (
    <figure className="spark">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={`P(1er) depuis le ${shortDate(points[0].day)}`}>
        <path d={d} className="spark-line" />
        {points.map((p, i) => (
          // Cible de survol plus large que la marque
          <g key={p.day}>
            <title>{`${shortDate(p.day)} : ${prob(p.p_first)}`}</title>
            <circle cx={x(i)} cy={y(p.p_first)} r={6} className="spark-hit" />
            {i === last && <circle cx={x(i)} cy={y(p.p_first)} r={3} className="spark-dot" />}
          </g>
        ))}
      </svg>
      <figcaption className="spark-cap num">
        <span>{shortDate(points[0].day)}</span>
        <span>aujourd'hui</span>
      </figcaption>
    </figure>
  )
}
