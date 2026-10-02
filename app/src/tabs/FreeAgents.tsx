import { injuryText, int, lastName, signed } from '../format'
import type { FreeAgents as FA } from '../types'

const LABELS = { F: 'Attaquants', D: 'Défenseurs' } as const

export default function FreeAgents({ fa }: { fa: FA }) {
  return (
    <>
      <p className="fa-moves">
        {fa.moves_left == null ? 'Moves restants inconnus'
          : <><b className="num">{fa.moves_left}</b> move{fa.moves_left > 1 ? 's' : ''} de FA restant{fa.moves_left > 1 ? 's' : ''}</>}
      </p>
      <p className="group-note">
        Gain = ROS du FA − ROS de mon pire joueur à la même position. Seuls les points à venir comptent.
      </p>
      {(['F', 'D'] as const).map((pos) => {
        const worst = fa.worst[pos]
        return (
          <section key={pos} className="group">
            <h2 className="group-title">{LABELS[pos]}</h2>
            {worst && (
              <p className="group-note">
                Mon pire : {lastName(worst.name)}, ROS <span className="num">{int(worst.ros.mean)}</span>
              </p>
            )}
            <ul className="rows">
              {fa.players[pos].map((f) => (
                <li key={f.espn_id} className="row">
                  <div className="row-main">
                    <span className="row-name">{f.name}</span>
                    <span className="row-meta">
                      {f.pos} · {f.team}
                      {f.pct_owned != null && <> · {Math.round(f.pct_owned)} % ESPN</>}
                    </span>
                    {f.status !== 'ACTIVE' && <span className="row-injury">{injuryText(f)}</span>}
                  </div>
                  <div className="row-side">
                    <span className="row-value num">
                      {int(f.ros.mean)}
                      <small> {int(f.ros.p10)}–{int(f.ros.p90)}</small>
                    </span>
                    {f.gain != null && (
                      <span className={`row-gain num${f.gain > 0 ? ' is-good' : ''}`}>{signed(f.gain, 0)}</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </>
  )
}
