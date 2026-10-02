import { useState } from 'react'
import { dec, injuryText, int, lastName, minutes, pct, signed } from '../format'
import type { Player } from '../types'
import Band, { standing } from './Band'

const VERDICT_LABEL = {
  malchanceux: 'Malchanceux',
  chanceux: 'Chanceux',
  conforme: 'Conforme',
  petit_echantillon: 'Échantillon trop petit (< 10 matchs)',
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value num">{value}</span>
      {sub && <span className="stat-sub num">{sub}</span>}
    </div>
  )
}

export default function PlayerCard({ player: p, max, ticks }: { player: Player; max: number; ticks: number[] }) {
  const [open, setOpen] = useState(false)
  const s = standing(p)
  // Couleur réservée aux verdicts qui appellent une décision (garder / acheter, vendre)
  const chip = p.verdict === 'malchanceux' || p.verdict === 'chanceux' ? p.verdict : null
  return (
    <article className={`card${open ? ' is-open' : ''}`} onClick={() => setOpen(!open)}>
      <header className="card-head">
        <div className="card-who">
          <span className="card-name">{lastName(p.name)}</span>
          <span className="card-meta">
            {p.pos} · {p.team}
          </span>
          {chip && <span className={`chip is-${chip}`}>{VERDICT_LABEL[chip]}</span>}
          {p.injury && <span className="chip is-injury">{injuryText(p.injury)}</span>}
        </div>
        <div className="card-total">
          {p.final ? (
            <span className={`card-final num${s ? ` is-${s}` : ''}`}>{int(p.final.mean)}</span>
          ) : (
            <span className="card-final num is-none">—</span>
          )}
          <span className="card-now num">
            {p.points} pts · {p.gp} PJ
          </span>
        </div>
      </header>

      {p.final && <Band player={p} max={max} ticks={ticks} />}

      {open && (
        <div className="card-detail">
          {p.final && p.ros && (
            <Stat
              label="Total projeté"
              value={`${int(p.final.mean)} (${int(p.final.p10)}–${int(p.final.p90)})`}
              sub={`ROS ${int(p.ros.mean)} en ${p.ros.games_left} matchs`}
            />
          )}
          {p.prior && (
            <Stat
              label="Préseason, même nb de matchs"
              value={`${int(p.prior.p10)} · ${int(p.prior.p50)} · ${int(p.prior.p90)}`}
              sub="p10 · p50 · p90"
            />
          )}
          {p.pace != null && <Stat label="Pace sur 84" value={int(p.pace)} sub={`${p.g} B · ${p.a} A`} />}
          {p.luck && (
            <>
              <Stat label="Points sans la chance" value={dec(p.luck.expected_points)} sub={`réels ${p.points}`} />
              <Stat label="B − xB" value={signed(p.luck.g_minus_ixg)} />
              <Stat label="Sh %" value={pct(p.luck.sh)} sub={`carrière ${pct(p.luck.sh_career)}`} />
              <Stat label="Sh % des coéquipiers" value={pct(p.luck.oish)} sub={`carrière ${pct(p.luck.oish_career)}`} />
              {p.luck.toi != null && <Stat label="TG / match" value={minutes(p.luck.toi)} />}
            </>
          )}
          {p.verdict && <p className="card-verdict">{VERDICT_LABEL[p.verdict]}</p>}
        </div>
      )}
    </article>
  )
}
