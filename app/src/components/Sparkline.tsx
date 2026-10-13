import { prob, shortDate } from '../format'
import { toneFill } from '../tone'

const W = 320
const H = 72
const PAD = 6
const ZOOM_DAYS = 5      // les derniers jours, à pleine largeur
const ZOOM_SHARE = 0.55  // part de la largeur réservée aux ZOOM_DAYS derniers jours
const SQUEEZE = 6        // au-delà, le temps est écrasé en log : plus petit = plus écrasé
const TREND = 2          // la couleur d'un segment = variation sur ce nombre de jours

/** Jours avant aujourd'hui → abscisse « déformée » : linéaire sur les derniers jours, logarithmique avant */
const warp = (age: number) => (age <= ZOOM_DAYS ? age : ZOOM_DAYS + SQUEEZE * Math.log1p((age - ZOOM_DAYS) / SQUEEZE))

const dayNum = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 86_400_000

/** Ma P(1er) sur toute la saison : les 5 derniers jours en gros plan, le reste écrasé à gauche.
 *  Chaque segment est vert ou rouge selon la tendance sur 2 jours, plus vif quand ça bouge beaucoup. */
export default function Sparkline({ points }: { points: { day: string; p_first: number }[] }) {
  if (points.length < 2) return null
  const today = dayNum(points[points.length - 1].day)
  const ages = points.map((p) => today - dayNum(p.day))
  const oldest = warp(Math.max(...ages))
  const zoomEnd = Math.min(ZOOM_DAYS, oldest)
  const inner = W - 2 * PAD
  // Le gros plan prend ZOOM_SHARE de la largeur dès qu'il y a de l'historique avant lui
  const x = (age: number) => {
    const u = warp(age)
    if (oldest <= ZOOM_DAYS) return W - PAD - (u / oldest) * inner
    if (u <= ZOOM_DAYS) return W - PAD - (u / ZOOM_DAYS) * ZOOM_SHARE * inner
    return W - PAD - ZOOM_SHARE * inner - ((u - ZOOM_DAYS) / (oldest - ZOOM_DAYS)) * (1 - ZOOM_SHARE) * inner
  }
  const ys = points.map((p) => p.p_first)
  const lo = Math.max(0, Math.min(...ys) - 0.03)
  const hi = Math.min(1, Math.max(...ys) + 0.03)
  const y = (v: number) => PAD + (1 - (v - lo) / (hi - lo || 0.01)) * (H - 2 * PAD)
  const last = points.length - 1
  const split = x(zoomEnd)
  return (
    <figure className="spark is-wide">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
        aria-label={`P(1er) depuis le ${shortDate(points[0].day)}`}>
        {oldest > ZOOM_DAYS && <line x1={split} x2={split} y1={0} y2={H} className="spark-split" />}
        {points.slice(1).map((p, i) => {
          const back = points[Math.max(0, i + 1 - TREND)]
          return (
            <line key={p.day} x1={x(ages[i])} y1={y(points[i].p_first)} x2={x(ages[i + 1])} y2={y(p.p_first)}
              className="spark-seg" style={{ stroke: toneFill(p.p_first - back.p_first, 0.08) }} />
          )
        })}
        {points.map((p, i) => (
          // Cible de survol plus large que la marque
          <g key={p.day}>
            <title>{`${shortDate(p.day)} : ${prob(p.p_first)}`}</title>
            <circle cx={x(ages[i])} cy={y(p.p_first)} r={7} className="spark-hit" />
            {i === last && <circle cx={x(ages[i])} cy={y(p.p_first)} r={3.5} className="spark-dot" />}
          </g>
        ))}
      </svg>
      <figcaption className="spark-cap num">
        <span>{shortDate(points[0].day)}</span>
        {oldest > ZOOM_DAYS && (
          <span style={{ position: 'absolute', left: `${(split / W) * 100}%` }}>{ZOOM_DAYS} derniers jours →</span>
        )}
        <span>aujourd'hui</span>
      </figcaption>
    </figure>
  )
}
