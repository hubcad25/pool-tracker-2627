import { useEffect, useState, type ReactNode } from 'react'
import { dec, prob } from '../format'
import { fetchBoxLine, fetchShotZones, hasProxy, type BoxLine, type Live, type Night, type OnIce, type ShotZones } from '../live'
import type { TonightPlayer } from '../types'

const STRENGTH: Record<string, string> = { pp: 'AN', sh: 'DN', en: 'filet désert' }

const pts = (x: number) => `${x} ${x >= 2 ? 'pts' : 'pt'}`

type Zones = { shots: ShotZones; goals: ShotZones }

/** Le match d'un joueur, déplié sous sa ligne : sa soirée de pool, ses points et sa feuille de match */
export default function PlayerDetail({ p, n, live, children }: { p: TonightPlayer; n: Night; live: Live; children?: ReactNode }) {
  const [box, setBox] = useState<BoxLine | null | 'error' | undefined>(undefined)
  const [zones, setZones] = useState<(Zones & { onIce: OnIce | null }) | null>(null)
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

  if (goalie && n.goalie) {
    // A joué : partant, ou entré en relève
    const played = n.goalie.started !== false || n.goalie.inNet !== false
    return (
      <div className="player-detail" onClick={(e) => e.stopPropagation()}>
        <GoalieLive p={p} n={n} />
        {children}
        {unavailable && <p className="detail-line">Détails du match indisponibles (pas de direct LNH).</p>}
        {b && played && (
          <dl className="detail-stats num">
            <Stat k="Arrêts" v={b.shotsAgainst != null ? `${b.saves}/${b.shotsAgainst}` : undefined} />
            <Stat k="% arrêts" v={b.savePctg != null ? b.savePctg.toFixed(3).replace(/^0/, '') : undefined} />
            <Stat k="TOI" v={b.toi} />
          </dl>
        )}
        {zones && played && (
          <div className="detail-zones">
            <ZoneBar title="Tirs contre" z={zones} max={40} />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="player-detail" onClick={(e) => e.stopPropagation()}>
      <PoolLine n={n} />
      {children}
      {!started ? null : unavailable ? (
        <p className="detail-line">Détails du match indisponibles (pas de direct LNH).</p>
      ) : (
        <>
          <div className="detail-points">
            <div className="zones-title">Ses points ce soir</div>
            {mine.length === 0 ? (
              <p className="detail-line">Aucun point pour l'instant.</p>
            ) : (
              <ol className="detail-goals">
                {mine.map((g, i) => {
                  const goal = g.scorer.id === p.nhl_id
                  return (
                    <li key={i} className="num">
                      <span className={`point-chip${goal ? ' is-goal' : ''}`}>{goal ? 'But' : 'Passe'}</span>
                      <span>
                        {g.period} {g.time}
                        {STRENGTH[g.strength] && <> · {STRENGTH[g.strength]}</>}
                        {!goal && <span className="detail-fine"> · but de {g.scorer.name}</span>}
                      </span>
                    </li>
                  )
                })}
              </ol>
            )}
          </div>
          {b && (
            <dl className="detail-stats num">
              <Stat k="TOI" v={b.toi} />
              <Stat k="Shifts" v={b.shifts} />
              <Stat k="Tirs" v={b.sog} />
            </dl>
          )}
          {zones && (
            <div className="detail-zones">
              <ZoneBar title="Tirs par zone" z={zones} />
              {zones.onIce && (
                <ZoneBar title="Coéquipiers (lui sur la glace)" z={zones.onIce.for} note={n.state === 'LIVE' ? `jusqu'à ${zones.onIce.upTo}` : undefined} />
              )}
            </div>
          )}
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
    n.state === 'FUT' ? { text: g.pStart != null ? `Commence à ${prob(g.pStart)} (MoneyPuck)` : 'Partant pas annoncé', cls: '' }
    : g.started === true && g.inNet !== false ? { text: done ? 'Partant' : 'Partant · devant le filet', cls: 'is-in' }
    : g.started === true ? { text: 'Partant · retiré', cls: 'is-out' }
    : g.started === false && g.inNet === true ? { text: done ? 'Entré en relève' : 'En relève · devant le filet', cls: 'is-in' }
    : g.started === false ? { text: 'Sur le banc', cls: 'is-out' }
    : { text: 'Partant pas encore connu', cls: '' }
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
      {g.inNet === false && !done ? (
        <p className="detail-line num">{g.started ? `Plus devant le filet · prévu ${dec(n.expected)}` : '0 pt ce soir.'}</p>
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
            {g.started == null && <span className="detail-fine"> · compte la chance qu'il ne commence pas</span>}
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

/** Tirs au but par zone en barre empilée, à la même échelle pour tous (`max` tirs ; au-delà, la barre pleine
 *  vaut son total) : HD rouge, MD jaune, LD vert, le nombre dans chaque segment ; les buts dans la légende */
function ZoneBar({ title, z, note, max = 15 }: { title: string; z: Zones; note?: string; max?: number }) {
  const total = z.shots.hd + z.shots.md + z.shots.ld
  const scale = Math.max(max, total)
  const goals = ZONES.filter(({ key }) => z.goals[key] > 0)
  return (
    <div className="zones">
      <div className="zones-title">
        {title}
        {note && <span className="detail-fine num"> · {note}</span>}
      </div>
      <div className="zones-line num">
        <div className="zones-bar" role="img" aria-label={ZONES.map(({ key, label }) => `${label} ${z.shots[key]}`).join(', ')}>
          {total === 0 && <span className="zones-empty">aucun tir</span>}
          {ZONES.map(({ key }) => z.shots[key] > 0 && (
            <span key={key} className={`zones-seg is-${key}`} style={{ width: `${(z.shots[key] / scale) * 100}%` }}>{z.shots[key]}</span>
          ))}
        </div>
        <b className="zones-total">{total}</b>
      </div>
      {goals.length > 0 && (
        <div className="zones-legend num">
          {goals.map(({ key, label }) => (
            <span key={key}>
              <i className={`zones-dot is-${key}`} />
              {z.goals[key]} but{z.goals[key] > 1 ? 's' : ''} {label}
            </span>
          ))}
        </div>
      )}
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
