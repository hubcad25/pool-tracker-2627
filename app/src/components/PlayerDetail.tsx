import { useEffect, useState, type ReactNode } from 'react'
import { dec, prob } from '../format'
import { fetchBoxLine, fetchShotZones, hasProxy, type BoxLine, type Live, type Night, type ShotZones } from '../live'
import type { TonightPlayer } from '../types'

const STRENGTH: Record<string, string> = { pp: 'AN', sh: 'DN', en: 'filet désert' }

const pts = (x: number) => `${x} ${x >= 2 ? 'pts' : 'pt'}`

type Zones = { shots: ShotZones; goals: ShotZones }

/** Le match d'un joueur, déplié sous sa ligne : sa soirée de pool, ses points et sa feuille de match */
export default function PlayerDetail({ p, n, live, children }: { p: TonightPlayer; n: Night; live: Live; children?: ReactNode }) {
  const [box, setBox] = useState<BoxLine | null | 'error' | undefined>(undefined)
  const [zones, setZones] = useState<Zones | null>(null)
  const started = n.state !== 'FUT'
  const goalie = p.pos === 'G'
  // Relu à chaque lecture du direct (~60 s) tant que le match est en cours
  useEffect(() => {
    if (!hasProxy || !started || p.game_id == null || p.nhl_id == null) return
    let stopped = false
    fetchBoxLine(p.game_id, p.nhl_id)
      .then((b) => !stopped && setBox(b))
      .catch(() => !stopped && setBox('error'))
    fetchShotZones(p.game_id, p.nhl_id, goalie)
      .then((z) => !stopped && setZones(z))
      .catch(() => !stopped && setZones(null))
    return () => {
      stopped = true
    }
  }, [p.game_id, p.nhl_id, started, goalie, live.at])

  const goals = (p.game_id != null ? live.games.get(p.game_id)?.goals : undefined) ?? []
  const mine = goals.filter((g) => g.scorer.id === p.nhl_id || g.assists.some((a) => a.id === p.nhl_id))
  const b = box && box !== 'error' ? box : null
  const unavailable = started && (!hasProxy || box === 'error')

  if (goalie && n.goalie)
    return (
      <div className="player-detail" onClick={(e) => e.stopPropagation()}>
        <GoalieLive p={p} n={n} />
        {children}
        {unavailable && <p className="detail-line">Détails du match indisponibles (pas de direct LNH).</p>}
        {b && n.goalie.inNet !== false && (
          <dl className="detail-stats num">
            <Stat k="Arrêts" v={b.shotsAgainst != null ? `${b.saves}/${b.shotsAgainst}` : undefined} />
            <Stat k="% arrêts" v={b.savePctg != null ? b.savePctg.toFixed(3).replace(/^0/, '') : undefined} />
            <Stat k="TOI" v={b.toi} />
          </dl>
        )}
        {zones && n.goalie.inNet !== false && <ZoneBar title="Tirs contre" z={zones} />}
      </div>
    )

  return (
    <div className="player-detail" onClick={(e) => e.stopPropagation()}>
      <PoolLine n={n} />
      {children}
      {!started ? null : unavailable ? (
        <p className="detail-line">Détails du match indisponibles (pas de direct LNH).</p>
      ) : (
        <>
          <ul className="detail-goals">
            {mine.length === 0 && <li>Aucun point pour l'instant.</li>}
            {mine.map((g, i) => (
              <li key={i} className="num">
                <b>{g.scorer.id === p.nhl_id ? 'But' : 'Passe'}</b> · {g.period} {g.time}
                {STRENGTH[g.strength] && <> · {STRENGTH[g.strength]}</>}
                {g.scorer.id !== p.nhl_id && <span className="detail-fine"> · but de {g.scorer.name}</span>}
              </li>
            ))}
          </ul>
          {b && (
            <dl className="detail-stats num">
              <Stat k="TOI" v={b.toi} />
              <Stat k="Shifts" v={b.shifts} />
              <Stat k="Tirs" v={b.sog} />
            </dl>
          )}
          {zones && <ZoneBar title="Tirs par zone" z={zones} />}
          {box === undefined && <p className="detail-line">Chargement…</p>}
        </>
      )}
    </div>
  )
}

/** La soirée de pool en une ligne : prévu, réel, fin probable et chance d'au moins un point */
function PoolLine({ n }: { n: Night }) {
  const before = n.p1Start
  if (n.state === 'FUT')
    return (
      <p className="detail-line num">
        Prévu {dec(n.expected)} pt · P(1+ pt) {prob(before)}
      </p>
    )
  return (
    <p className="detail-line num">
      {pts(n.actual)} · prévu {dec(n.expected)}
      {n.state === 'LIVE' && <> · fin ≈ {dec(n.actual + n.left)}</>}
      {' · '}
      {n.actual >= 1 ? (
        <span className="detail-ok">✓ 1+ pt</span>
      ) : n.state === 'LIVE' ? (
        <>
          P(1+ pt) début {prob(before)} → maintenant {prob(n.p1)}
        </>
      ) : (
        <>P(1+ pt) début {prob(before)}</>
      )}
    </p>
  )
}

/** Gardien en direct : le pointage, s'il joue, puis ce qui donne des points (victoire 2, défaite en prol. 1,
 *  jeu blanc +1) avec leurs chances, et ses points au bout */
function GoalieLive({ p, n }: { p: TonightPlayer; n: Night }) {
  const g = n.goalie!
  const opp = p.opp.replace('@', '')
  const done = n.state === 'FINAL'
  const role =
    g.inNet === true ? { text: 'Devant le filet', cls: 'is-in' }
    : g.inNet === false ? { text: 'Sur le banc', cls: 'is-out' }
    : { text: n.state === 'FUT' ? 'Partant pas confirmé' : 'Partant inconnu', cls: '' }
  return (
    <div className="goalie-live">
      <div className="goalie-head">
        {n.state !== 'FUT' && (
          <span className="goalie-score num">
            {p.team} <b>{g.score.for}</b> – <b>{g.score.against}</b> {opp}
            {n.clock && <small> · {n.clock}</small>}
          </span>
        )}
        <span className={`goalie-role ${role.cls}`}>{role.text}</span>
      </div>
      {g.inNet === false ? (
        <p className="detail-line">0 pt ce soir.</p>
      ) : done ? (
        <p className="detail-line num">
          <b>{pts(n.actual)}</b> · prévu {dec(n.expected)}
        </p>
      ) : (
        <>
          <div className="goalie-odds num">
            <Odd k="Victoire" sub="2 pts" v={g.win} />
            <Odd k="Déf. prol." sub="1 pt" v={g.otl} />
            <Odd k="Jeu blanc" sub="+1 pt" v={g.shutout} />
          </div>
          <p className="detail-line num">
            Fin ≈ <b>{dec(n.actual + n.left)}</b> pt · prévu {dec(n.expected)}
            {g.inNet == null && <span className="detail-fine"> · compte la chance qu'il ne joue pas</span>}
          </p>
        </>
      )}
    </div>
  )
}

function Odd({ k, sub, v }: { k: string; sub: string; v: number }) {
  return (
    <div className="goalie-odd">
      <span className="goalie-odd-k">{k} <small>{sub}</small></span>
      <b>{prob(v)}</b>
    </div>
  )
}

const ZONES: { key: keyof ShotZones; label: string }[] = [
  { key: 'hd', label: 'HD' },
  { key: 'md', label: 'MD' },
  { key: 'ld', label: 'LD' },
]

/** Tirs au but par zone en une barre (HD rouge, MD jaune, LD vert), les buts entre parenthèses */
function ZoneBar({ title, z }: { title: string; z: Zones }) {
  const total = z.shots.hd + z.shots.md + z.shots.ld
  return (
    <div className="zones">
      <div className="zones-title">
        {title} <span className="num">· {total}</span>
      </div>
      {total > 0 && (
        <div className="zones-bar" role="img" aria-label={ZONES.map(({ key, label }) => `${label} ${z.shots[key]}`).join(', ')}>
          {ZONES.map(({ key }) => z.shots[key] > 0 && <span key={key} className={`zones-seg is-${key}`} style={{ flexGrow: z.shots[key] }} />)}
        </div>
      )}
      <div className="zones-legend num">
        {ZONES.map(({ key, label }) => (
          <span key={key}>
            <i className={`zones-dot is-${key}`} />
            {label} <b>{z.shots[key]}</b>
            {z.goals[key] > 0 && <small> ({z.goals[key]} but{z.goals[key] > 1 ? 's' : ''})</small>}
          </span>
        ))}
      </div>
    </div>
  )
}

function Stat({ k, v }: { k: string; v: ReactNode }) {
  if (v == null) return null
  return (
    <div>
      <dt>{k}</dt>
      <dd>{v}</dd>
    </div>
  )
}
