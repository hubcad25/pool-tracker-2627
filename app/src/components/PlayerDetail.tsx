import { useEffect, useState, type ReactNode } from 'react'
import { fetchBoxLine, hasProxy, type BoxLine, type Live, type Night } from '../live'
import type { TonightPlayer } from '../types'

const STRENGTH: Record<string, string> = { pp: 'AN', sh: 'DN', en: 'filet désert' }

/** Le match d'un joueur, déplié sous sa ligne : ses points (quand, sur quel but) et sa feuille de match */
export default function PlayerDetail({ p, n, live, children }: { p: TonightPlayer; n: Night; live: Live; children?: ReactNode }) {
  const [box, setBox] = useState<BoxLine | null | 'error' | undefined>(undefined)
  const started = n.state !== 'FUT'
  // Relu à chaque lecture du direct (~60 s) tant que le match est en cours
  useEffect(() => {
    if (!hasProxy || !started || p.game_id == null || p.nhl_id == null) return
    let stopped = false
    fetchBoxLine(p.game_id, p.nhl_id)
      .then((b) => !stopped && setBox(b))
      .catch(() => !stopped && setBox('error'))
    return () => {
      stopped = true
    }
  }, [p.game_id, p.nhl_id, started, live.at])

  const goals = (p.game_id != null ? live.games.get(p.game_id)?.goals : undefined) ?? []
  const mine = goals.filter((g) => g.scorer.id === p.nhl_id || g.assists.some((a) => a.id === p.nhl_id))
  const goalie = p.pos === 'G'
  const b = box && box !== 'error' ? box : null

  return (
    <div className="player-detail" onClick={(e) => e.stopPropagation()}>
      {children}
      {!started ? (
        <p className="detail-line">Le match n'est pas commencé.</p>
      ) : !hasProxy || box === 'error' ? (
        <p className="detail-line">Détails du match indisponibles (pas de direct LNH).</p>
      ) : (
        <>
          {!goalie && (
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
          )}
          {b && (
            <dl className="detail-stats num">
              {goalie ? (
                <>
                  <Stat k="Arrêts" v={b.shotsAgainst != null ? `${b.saves}/${b.shotsAgainst}` : undefined} />
                  <Stat k="% arrêts" v={b.savePctg != null ? b.savePctg.toFixed(3).replace(/^0/, '') : undefined} />
                  <Stat k="Buts contre" v={b.goalsAgainst} />
                  <Stat k="Temps" v={b.toi} />
                  <Stat k="Décision" v={b.decision} />
                </>
              ) : (
                <>
                  <Stat k="Temps" v={b.toi} />
                  <Stat k="Tirs" v={b.sog} />
                  <Stat k="+/-" v={b.plusMinus != null ? (b.plusMinus > 0 ? `+${b.plusMinus}` : `${b.plusMinus}`.replace('-', '−')) : undefined} />
                  <Stat k="Présences" v={b.shifts} />
                  <Stat k="Mises en échec" v={b.hits} />
                  <Stat k="Tirs bloqués" v={b.blockedShots} />
                  {b.faceoffWinningPctg != null && b.faceoffWinningPctg > 0 && <Stat k="Mises au jeu" v={`${Math.round(b.faceoffWinningPctg * 100)} %`} />}
                </>
              )}
            </dl>
          )}
          {box === undefined && <p className="detail-line">Chargement…</p>}
        </>
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
