import Group from '../components/Group'
import TeamLogo from '../components/TeamLogo'
import { useState } from 'react'
import { LuckBlock, LuckSummary } from '../components/PlayerCard'
import RosBar from '../components/RosBar'
import { SortBar, sortBy, useSort, type SortOption } from '../components/Sort'
import { injuryText, int, lastName, signed } from '../format'
import { arrow, tone } from '../tone'
import type { FreeAgent, FreeAgents as FA, Interval } from '../types'

const LABELS = { F: 'Attaquants', D: 'Défenseurs', G: 'Gardiens' } as const

type Key = 'ros' | 'gain' | 'better' | 'luck' | 'owned' | 'name'
const SORT: SortOption<Key>[] = [
  { key: 'ros', label: 'ROS', dir: 'desc' },
  { key: 'gain', label: 'Gain', dir: 'desc' },
  { key: 'better', label: 'P(meilleur)', dir: 'desc' },
  { key: 'luck', label: 'Chance', dir: 'desc' },
  { key: 'owned', label: '% ESPN', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

const luckOf = (f: FreeAgent) => (f.luck ? (f.luck.net_points ?? (f.points ?? 0) - f.luck.expected_points) : null)

function Row({ f, max, worst }: { f: FreeAgent; max: number; worst?: { name: string; ros: Interval } }) {
  const [open, setOpen] = useState(false)
  const chip = f.verdict === 'chanceux' || f.verdict === 'malchanceux' ? f.verdict : null
  return (
    <li className={`row is-stacked${open ? ' is-open' : ''}`} onClick={() => setOpen(!open)}>
      <div className="row-top">
        <div className="row-main">
          <span className="row-name">
            {f.name} {chip && <span className={`chip is-${chip}`}>{chip === 'chanceux' ? 'Chanceux' : 'Malchanceux'}</span>}
          </span>
          <span className="row-meta">
            {f.pos} · <TeamLogo team={f.team} />
            {f.pct_owned != null && <> · {Math.round(f.pct_owned)} % ESPN</>}
            {f.gp != null && <> · {f.gp} GP</>}
          </span>
          {f.status !== 'ACTIVE' && <span className="row-injury">{injuryText(f)}</span>}
        </div>
        <div className="row-side">
          <span className="row-value num is-data">
            {int(f.ros.mean)}
            <small> {int(f.ros.p10)}–{int(f.ros.p90)}</small>
          </span>
          {f.gain != null && (
            <span className="row-gain num" style={tone(f.gain, 15)}>
              {arrow(f.gain, 0.5)}
              {signed(f.gain, 0)}
            </span>
          )}
        </div>
      </div>
      <RosBar ros={f.ros} max={max} mark={worst?.ros.mean} markLabel={worst ? lastName(worst.name) : undefined} />
      {f.p_better != null && worst && (
        <span className="row-meta">
          P(meilleur que {lastName(worst.name)}){' '}
          <b className="num" style={tone(f.p_better - 0.5, 0.4)}>
            {Math.round(f.p_better * 100)} %
          </b>
        </span>
      )}
      {f.points != null && (
        <span className="row-meta">
          Cette saison :{' '}
          {f.luck ? <LuckSummary p={{ points: f.points, luck: f.luck, verdict: f.verdict }} /> : <>{f.points} pts</>}
        </span>
      )}
      {open && f.luck && f.points != null && (
        <div className="card-detail" onClick={(e) => e.stopPropagation()}>
          <LuckBlock p={{ points: f.points, luck: f.luck, verdict: f.verdict }} luck={f.luck} />
        </div>
      )}
    </li>
  )
}

export default function FreeAgents({ fa }: { fa: FA }) {
  const [sort, setSort] = useSort('fa', SORT)
  return (
    <>
      <p className="fa-moves">
        {fa.moves_left == null ? 'Moves restants inconnus'
          : <><b className="num">{fa.moves_left}</b> move{fa.moves_left > 1 ? 's' : ''} de FA restant{fa.moves_left > 1 ? 's' : ''}</>}
      </p>
      <p className="group-note">
        ROS ◆ et fourchette probable, le trait vertical = mon pire joueur à la position. À droite : les points gagnés (▲) ou
        perdus (▼) en le remplaçant. Touche un joueur pour le détail de sa chance.
      </p>
      <SortBar options={SORT} sort={sort} onChange={setSort} />
      {(['F', 'D', 'G'] as const).map((pos) => {
        const worst = fa.worst[pos]
        const players = fa.players[pos] ?? []
        if (!players.length) return null
        const max = Math.max(1, ...players.map((f) => f.ros.p90), worst?.ros.p90 ?? 0)
        return (
          <Group key={pos} id={`agents-${pos}`} title={LABELS[pos]}>
            {worst && (
              <p className="group-note">
                Mon pire : {lastName(worst.name)}, ROS <span className="num is-data">{int(worst.ros.mean)}</span>{' '}
                <span className="num">({int(worst.ros.p10)}–{int(worst.ros.p90)})</span>
              </p>
            )}
            <ul className="rows">
              {sortBy(players, sort, (f, k) =>
                k === 'ros' ? f.ros.mean
                : k === 'gain' ? f.gain
                : k === 'better' ? (f.p_better ?? null)
                : k === 'luck' ? luckOf(f)
                : k === 'owned' ? f.pct_owned
                : lastName(f.name),
              ).map((f) => (
                <Row key={f.espn_id} f={f} max={max} worst={worst} />
              ))}
            </ul>
          </Group>
        )
      })}
    </>
  )
}
