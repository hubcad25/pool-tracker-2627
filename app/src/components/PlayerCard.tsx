import { useState } from 'react'
import { dec, injuryText, int, lastName, minutes, pct, signed } from '../format'
import { luckPhrase, percentileText, pts } from '../luck'
import { arrow, tone, toneFill } from '../tone'
import type { Luck, Player, Verdict } from '../types'
import Band, { LUCK_FULL, rosQuantile, vsPreseason } from './Band'

/** Ce qu'il faut pour montrer la chance d'une saison : mes cartes, les FA, les blessés */
export type SeasonLike = { points: number; verdict?: Verdict | null; luck?: Luck | null }

const CHIP = { malchanceux: 'Malchanceux', chanceux: 'Chanceux' }

const pct0 = (x: number | null) => (x == null ? '—' : `${Math.round(x * 100)} %`)

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value num">{value}</span>
      {sub && <span className="stat-sub num">{sub}</span>}
    </div>
  )
}

/** Jauge 0–100 : 50 au centre = normal, à droite = chanceux */
function Gauge({ q }: { q: number }) {
  return (
    <div className="gauge" role="img" aria-label={`Centile ${Math.round(q * 100)} sur 100`}>
      <div className="gauge-track">
        <span className="gauge-mid" />
        <span className="gauge-dot" style={{ left: `${q * 100}%`, background: toneFill(q - 0.5, 0.45) }} title={`Centile ${Math.round(q * 100)}`} />
      </div>
      <div className="gauge-ends">
        <span>malchanceux</span>
        <span>normal</span>
        <span>chanceux</span>
      </div>
    </div>
  )
}

function LuckLine({ label, text, q, small }: { label: string; text: string; q: number | null; small?: string }) {
  return (
    <div className="luck-line">
      <p>
        <b>{label} :</b> {text}
        {q != null && <> · <span style={tone(q - 0.5, 0.45)}>{percentileText(q)}</span></>}
      </p>
      {small && <p className="luck-sh">{small}</p>}
      {q != null && <Gauge q={q} />}
    </div>
  )
}

/** Net de chance : points réels − points avec une chance normale */
export const netLuck = (p: SeasonLike) => (p.luck ? (p.luck.net_points ?? p.points - p.luck.expected_points) : 0)

/** Une ligne courte et colorée : « ▲ 9 pts, dont ~2 de chance » */
/** « 9 pts · ▲ +2,2 de chance » : les points, puis le net de chance en couleur (vert = la chance lui a rapporté,
 *  rouge = elle lui a coûté, presque neutre près de 0) ; atténué avant 10 matchs. */
export function LuckSummary({ p, className }: { p: SeasonLike; className?: string }) {
  const net = netLuck(p)
  const small = p.verdict === 'petit_echantillon'
  return (
    <span className={className} title={luckPhrase(p.points, net)}>
      {p.points} {pts(p.points)} ·{' '}
      <b className={`luck-net num${small ? ' is-small' : ''}`} style={tone(net, LUCK_FULL)}>
        {Math.abs(net) < 0.05 ? '±0' : `${arrow(net, 0.05)}${signed(net)}`} de {net < 0 ? 'malchance' : 'chance'}
      </b>
    </span>
  )
}

export function LuckBlock({ p, luck }: { p: SeasonLike; luck: Luck }) {
  const g = luck.goals
  const a = luck.assists
  const old = g === undefined && a === undefined
  return (
    <div className="luck">
      <p className="luck-head">
        <LuckSummary p={{ ...p, luck }} />
      </p>
      <p className="luck-sub">Avec une chance normale, il aurait {dec(luck.expected_points)} {pts(luck.expected_points)}.</p>
      {g && (
        <LuckLine
          label="Ses tirs"
          text={`${g.obs} G (${dec(g.expected)} attendus)`}
          small={`${pct0(g.sh_obs)} de ses ${g.shots} tirs entrent (${pct0(g.sh_expected)} attendus)`}
          q={g.percentile}
        />
      )}
      {a && (
        <LuckLine
          label="Ses coéquipiers"
          text={`${a.obs_goals} G avec lui sur la glace (${dec(a.expected_goals)} attendus)`}
          small={`${pct0(a.sh_obs)} de leurs ${a.shots} tirs entrent (${pct0(a.sh_expected)} attendus)`}
          q={a.percentile}
        />
      )}
      {old && (
        <>
          <LuckLine label="Ses tirs" text={`${pct(luck.sh)} entrent, ${pct(luck.sh_career)} en carrière`} q={null} />
          <LuckLine label="Ses coéquipiers" text={`${pct(luck.oish)} de leurs tirs entrent, ${pct(luck.oish_career)} en carrière`} q={null} />
        </>
      )}
      {p.verdict === 'petit_echantillon' && <p className="luck-small">Moins de 10 matchs : ça peut encore beaucoup bouger.</p>}
    </div>
  )
}

export default function PlayerCard({ player: p, max }: { player: Player; max: number }) {
  const [open, setOpen] = useState(false)
  const q = p.ros && p.ros_prior ? rosQuantile(p.ros.mean, p.ros_prior) : null
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
          {chip && <span className={`chip is-${chip}`}>{CHIP[chip]}</span>}
          {p.injury && <span className="chip is-injury">{injuryText(p.injury)}</span>}
          {p.luck && p.group !== 'G' ? (
            <LuckSummary p={p} className="card-season" />
          ) : (
            <span className="card-season">{p.points} pts</span>
          )}
        </div>
        <div className="card-total">
          {p.ros ? (
            <>
              <span className={`card-final num${q == null ? ' is-data' : ''}`} style={q == null ? undefined : tone(q - 0.5, 0.45)}>
                <small>ROS</small> {int(p.ros.mean)}
              </span>
              {q != null && (
                <span className="card-vs" style={tone(q - 0.5, 0.45)}>
                  {vsPreseason(q)}
                </span>
              )}
              <span className="card-range num">
                {int(p.ros.p10)}–{int(p.ros.p90)} en {p.ros.games_left} m.
              </span>
            </>
          ) : (
            <span className="card-final num is-none">—</span>
          )}
          <span className="card-now num">
            {p.gp} GP{p.final && <> · total ~{int(p.final.mean)}</>}
          </span>
        </div>
      </header>

      <Band player={p} max={max} />

      {open && (
        <div className="card-detail">
          {p.ros && (
            <Stat
              label="ROS (fin de saison)"
              value={`${int(p.ros.mean)} (${int(p.ros.p10)}–${int(p.ros.p90)})`}
              sub={`en ${p.ros.games_left} matchs restants`}
            />
          )}
          {p.ros_prior && (
            <Stat
              label="Attendu avant la saison"
              value={`${int(p.ros_prior.p50)} (${int(p.ros_prior.p10)}–${int(p.ros_prior.p90)})`}
              sub={q != null ? `pour les mêmes matchs · ROS au ${Math.round(q * 100)}e c.` : 'pour les mêmes matchs'}
            />
          )}
          {p.pace != null && (
            <Stat
              label="Rythme actuel sur 84 m."
              value={int(p.pace)}
              sub={p.group === 'G' ? `${p.w ?? 0} W · ${p.otl ?? 0} OTL · ${p.so ?? 0} SO` : `${p.g} G · ${p.a} A`}
            />
          )}
          {p.final && (
            <Stat label="Total en fin de saison" value={int(p.final.mean)} sub={`${int(p.final.p10)}–${int(p.final.p90)}`} />
          )}
          {p.luck?.toi != null && <Stat label="TOI / match" value={minutes(p.luck.toi)} />}
          {p.luck && p.group !== 'G' && <LuckBlock p={p} luck={p.luck} />}
        </div>
      )}
    </article>
  )
}
