import { useState } from 'react'
import { prob, shortDate, signed } from '../format'
import { toneFill } from '../tone'

const W = 320
const H = 92
const PAD = 6
const LEFT = 30          // place des pourcentages de l'axe y
const BOTTOM = 14        // place des dates de l'axe x
const ZOOM_DAYS = 5      // les derniers jours, à pleine largeur
const ZOOM_SHARE = 0.55  // part de la largeur réservée aux ZOOM_DAYS derniers jours
const SQUEEZE = 6        // au-delà, le temps est écrasé en log : plus petit = plus écrasé
const TREND = 2          // tendance = variation sur ce nombre de jours (couleur des segments, survol)
const MARGIN = 0.05      // axe y : 5 points de % au-delà du plus bas et du plus haut
// Premier match de la saison LNH (data/schedule.json) : l'axe part de là, la courbe du début du suivi
const SEASON_START = '2026-09-29'

/** Jours avant aujourd'hui → abscisse « déformée » : linéaire sur les derniers jours, logarithmique avant */
const warp = (age: number) => (age <= ZOOM_DAYS ? age : ZOOM_DAYS + SQUEEZE * Math.log1p((age - ZOOM_DAYS) / SQUEEZE))

const dayNum = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 86_400_000
const isoOf = (n: number) => new Date(n * 86_400_000).toISOString().slice(0, 10)

/** Graduations de l'axe y : 3 à 5 valeurs rondes dans [lo, hi] */
function yTicks(lo: number, hi: number) {
  const step = [0.01, 0.02, 0.05, 0.1, 0.2].find((s) => (hi - lo) / s <= 5) ?? 0.25
  const out = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 100) / 100)
  return out
}

/** Aujourd'hui, heure locale, en AAAA-MM-JJ */
function localToday() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Ma P(1er) sur toute la saison : les 5 derniers jours en gros plan (un repère par jour), le reste écrasé à gauche
 *  jusqu'au début de la saison. Chaque segment est vert ou rouge selon la tendance sur 2 jours.
 *  `provisional` : le dernier point est celui d'après les matchs de la veille (pointillé, point creux). */
export default function Sparkline({ points, provisional = false }: { points: { day: string; p_first: number }[]; provisional?: boolean }) {
  const [hover, setHover] = useState<number | null>(null)
  if (points.length < 2) return null
  const today = dayNum(points[points.length - 1].day)
  const ages = points.map((p) => today - dayNum(p.day))
  const oldest = warp(Math.max(today - dayNum(SEASON_START), ...ages))
  const zoomEnd = Math.min(ZOOM_DAYS, oldest)
  const inner = W - LEFT - PAD
  // Le gros plan prend ZOOM_SHARE de la largeur dès qu'il y a de l'historique avant lui
  const x = (age: number) => {
    const u = warp(age)
    if (oldest <= ZOOM_DAYS) return W - PAD - (u / oldest) * inner
    if (u <= ZOOM_DAYS) return W - PAD - (u / ZOOM_DAYS) * ZOOM_SHARE * inner
    return W - PAD - ZOOM_SHARE * inner - ((u - ZOOM_DAYS) / (oldest - ZOOM_DAYS)) * (1 - ZOOM_SHARE) * inner
  }
  const ys = points.map((p) => p.p_first)
  // 5 points de % de marge, arrondie au 5 % : la courbe de 57 à 75 % donne un axe de 50 à 80 %
  const lo = Math.max(0, Math.floor(Math.round((Math.min(...ys) - MARGIN) * 1000) / 50) / 20)
  const hi = Math.min(1, Math.ceil(Math.round((Math.max(...ys) + MARGIN) * 1000) / 50) / 20)
  const bottom = H - BOTTOM
  const y = (v: number) => PAD + (1 - (v - lo) / (hi - lo || 0.01)) * (bottom - PAD)
  const last = points.length - 1
  const split = x(zoomEnd)
  // Axe x : chaque jour du gros plan, puis le début de la saison et le début du suivi (s'ils ne se chevauchent pas)
  const zoomDays = Array.from({ length: Math.floor(zoomEnd) + 1 }, (_, age) => age)
  const firstAge = ages[0]
  const startAge = today - dayNum(SEASON_START)
  const oldTicks = [startAge, firstAge].filter((a, i, all) => a > ZOOM_DAYS && all.indexOf(a) === i)
    .filter((a, i, all) => i === 0 || Math.abs(x(a) - x(all[0])) > 34)
  return (
    <figure className="spark is-wide">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
        aria-label={`P(1er) depuis le ${shortDate(points[0].day)}`}>
        {yTicks(lo, hi).map((v) => (
          <g key={v}>
            <line x1={LEFT} x2={W - PAD} y1={y(v)} y2={y(v)} className="spark-grid" />
            <text x={LEFT - 4} y={y(v)} className="spark-axis" textAnchor="end" dominantBaseline="middle">{prob(v)}</text>
          </g>
        ))}
        {oldest > ZOOM_DAYS && <line x1={split} x2={split} y1={PAD} y2={bottom} className="spark-split" />}
        {zoomDays.map((age) => (
          <text key={age} x={x(age)} y={H - 2} className="spark-axis" textAnchor={age === 0 ? 'end' : 'middle'}>
            {isoOf(today - age) === localToday() ? 'auj.' : +isoOf(today - age).slice(8, 10)}
          </text>
        ))}
        {oldTicks.map((age) => (
          <text key={age} x={x(age)} y={H - 2} className="spark-axis" textAnchor={age === startAge ? 'start' : 'middle'}>
            {shortDate(isoOf(today - age))}
          </text>
        ))}
        {points.slice(1).map((p, i) => {
          const back = points[Math.max(0, i + 1 - TREND)]
          return (
            <line key={p.day} x1={x(ages[i])} y1={y(points[i].p_first)} x2={x(ages[i + 1])} y2={y(p.p_first)}
              className={`spark-seg${provisional && i + 1 === last ? ' is-provisional' : ''}`} style={{ stroke: toneFill(p.p_first - back.p_first, 0.08) }} />
          )
        })}
        {points.map((p, i) => (
          // Cible de survol plus large que la marque ; un toucher fait la même chose sur mobile
          <g key={p.day} onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} onClick={() => setHover(i)}>
            <circle cx={x(ages[i])} cy={y(p.p_first)} r={7} className="spark-hit" />
            {(i === last || i === hover) && <circle cx={x(ages[i])} cy={y(p.p_first)} r={3.5}
              className={`spark-dot${provisional && i === last ? ' is-provisional' : ''}`} />}
          </g>
        ))}
      </svg>
      {hover != null && <Tip points={points} i={hover} provisional={provisional && hover === last} left={(x(ages[hover]) / W) * 100} top={(y(points[hover].p_first) / H) * 100} />}
    </figure>
  )
}

/** Au survol d'un point : la date, la P(1er), l'écart avec la veille et la tendance sur TREND jours (la couleur du segment) */
function Tip({ points, i, provisional, left, top }: { points: { day: string; p_first: number }[]; i: number; provisional: boolean; left: number; top: number }) {
  const p = points[i]
  const back = i >= TREND ? points[i - TREND] : null
  const move = back ? (p.p_first - back.p_first) * 100 : null
  const prev = i > 0 ? points[i - 1] : null
  // Écart avec la veille, seulement si le point d'avant est bien la veille (un jour manquant fausserait le sens)
  const day = prev && dayNum(p.day) - dayNum(prev.day) === 1 ? (p.p_first - prev.p_first) * 100 : null
  return (
    <div className="spark-tip num" style={{ left: `${Math.min(Math.max(left, 18), 82)}%`, top: `${top}%` }}>
      <b>{shortDate(p.day)} · {prob(p.p_first)}</b>
      {provisional && <span>provisoire : après les matchs, avant la mise à jour de midi</span>}
      <span style={{ color: day == null ? undefined : toneFill(day / 100, 0.08) }}>
        {day == null ? 'vs la veille : —' : `${signed(day)} pt vs la veille`}
      </span>
      <span style={{ color: move == null ? undefined : toneFill(move / 100, 0.08) }}>
        {move == null ? 'tendance : pas assez de jours' : `${signed(move)} pt sur ${TREND} jours`}
      </span>
    </div>
  )
}
