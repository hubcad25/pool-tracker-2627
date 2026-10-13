import { prob } from '../format'
import { nightDist } from '../poisson'
import { teamColor, teamTint } from '../teams'

const pts = (k: number) => `${k} ${k >= 2 ? 'pts' : 'pt'}`

/** Le total de la soirée d'une équipe, valeur par valeur : une barre par total possible (réel + encore possible).
 *  Le plus probable en couleur pleine et chiffré en gros ; l'intervalle 80 % en teinte, le reste pâle. */
export default function DistBars({ actual, left, teamId }: { actual: number; left: number; teamId: number }) {
  if (left <= 0.005) return null
  const d = nightDist(actual, left)
  const top = Math.max(...d.probs)
  const label = `Le plus probable : ${d.modes.map(pts).join(' ou ')} ; intervalle 80 % : ${d.lo} à ${d.hi}`
  return (
    <div className="dist" onClick={(e) => e.stopPropagation()}>
      <p className="dist-head">
        <span className="dist-mode num">{d.modes.join(' ou ')}</span> <small>{d.modes.at(-1)! >= 2 ? 'pts' : 'pt'}</small>{' '}
        <span className="dist-sub num">
          le plus probable ({prob(d.probs[d.values.indexOf(d.modes[0])])}) · intervalle 80 % : {d.lo} à {d.hi}
        </span>
      </p>
      <div className="dist-plot" role="img" aria-label={label}>
        {d.values.map((v, i) => {
          const mode = d.modes.includes(v)
          const inside = v >= d.lo && v <= d.hi
          return (
            <div key={v} className="dist-col" title={`${pts(v)} : ${prob(d.probs[i])}`}>
              <span className="dist-track">
                <span className="dist-bar" style={{
                  height: `${(d.probs[i] / top) * 100}%`,
                  background: mode ? teamColor(teamId) : inside ? teamTint(teamId) : 'var(--border)',
                }} />
              </span>
              <span className={`dist-x num${mode ? ' is-mode' : ''}`}>{v}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
