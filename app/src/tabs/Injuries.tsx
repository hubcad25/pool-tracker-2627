import Group from '../components/Group'
import TeamLogo from '../components/TeamLogo'
import { useState } from 'react'
import { LuckBlock, LuckSummary } from '../components/PlayerCard'
import RosBar from '../components/RosBar'
import { SortBar, sortBy, useSort, type SortOption } from '../components/Sort'
import { injuryText, int, lastName } from '../format'
import type { LeagueInjury } from '../types'
import PoolerIcon from '../components/PoolerIcon'

type Key = 'ros' | 'missed' | 'return' | 'name'
const SORT: SortOption<Key>[] = [
  { key: 'ros', label: 'ROS', dir: 'desc' },
  { key: 'missed', label: 'Matchs manqués', dir: 'desc' },
  { key: 'return', label: 'Retour', dir: 'asc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

function Row({ i, teamId, max }: { i: LeagueInjury; teamId?: number; max: number }) {
  const [open, setOpen] = useState(false)
  const luck = i.luck && i.points != null ? i.luck : null
  return (
    <li className={`row is-stacked${luck ? ' is-clickable' : ''}`} onClick={() => luck && setOpen(!open)}>
      <div className="row-top">
        <div className="row-main">
          <span className="row-name">{i.name}</span>
          <span className="row-meta">
            {i.pos} · <TeamLogo team={i.team} />
            {!i.mine && i.owner && (
              <>
                {' · '}
                {teamId != null && <PoolerIcon teamId={teamId} />}
                <b>{i.owner}</b>
              </>
            )}
            {i.gp != null && <> · {i.gp} GP</>}
          </span>
          {i.points != null && (
            <span className="row-meta">
              {luck ? <LuckSummary p={{ points: i.points, luck, verdict: i.verdict }} /> : <>{i.points} pts</>}
            </span>
          )}
          <span className="row-injury">{injuryText(i)}</span>
        </div>
        <div className="row-side">
          {i.ros ? (
            <span className="row-value num is-data">
              {int(i.ros.mean)}
              <small> {int(i.ros.p10)}–{int(i.ros.p90)}</small>
            </span>
          ) : (
            <span className="row-value num">—</span>
          )}
          <span className="row-sub">ROS</span>
        </div>
      </div>
      {i.ros && <RosBar ros={i.ros} max={max} />}
      {open && luck && (
        <div className="card-detail" onClick={(e) => e.stopPropagation()}>
          <LuckBlock p={{ points: i.points!, luck, verdict: i.verdict }} luck={luck} />
        </div>
      )}
    </li>
  )
}

/** `teamIds` : abréviation ESPN → team_id (pour la couleur de l'équipe) */
export default function Injuries({ injuries, teamIds = {} }: { injuries: LeagueInjury[]; teamIds?: Record<string, number> }) {
  const [sort, setSort] = useSort('blessures', SORT)
  const sorted = sortBy(injuries, sort, (i, k) =>
    k === 'ros' ? (i.ros?.mean ?? null)
    : k === 'missed' ? (i.out_for_season ? 999 : i.games_missed)
    : k === 'return' ? (i.out_for_season ? '9999' : i.expected_return)
    : lastName(i.name),
  )
  // Échelle commune à toute la page
  const max = Math.max(1, ...injuries.map((i) => i.ros?.p90 ?? 0))
  const mine = sorted.filter((i) => i.mine)
  const others = sorted.filter((i) => !i.mine)
  const row = (i: LeagueInjury) => <Row key={i.espn_id} i={i} teamId={i.owner ? teamIds[i.owner] : undefined} max={max} />
  return (
    <>
      <p className="group-note">ROS ◆ et fourchette probable, à la même échelle pour tous. Touche un joueur pour sa chance.</p>
      <SortBar options={SORT} sort={sort} onChange={setSort} />
      <Group id="blesses-moi" title="Mon équipe">
        {mine.length ? <ul className="rows">{mine.map(row)}</ul> : <p className="empty">Aucun blessé.</p>}
      </Group>
      <Group id="blesses-ligue" title="Dans la ligue">
        <p className="group-note">Les blessés des autres équipes qui vont manquer des matchs.</p>
        {others.length ? <ul className="rows">{others.map(row)}</ul> : <p className="empty">Aucun blessé.</p>}
      </Group>
    </>
  )
}
