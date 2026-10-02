import { injuryText, int } from '../format'
import type { LeagueInjury } from '../types'

function Row({ i }: { i: LeagueInjury }) {
  return (
    <li className="row">
      <div className="row-main">
        <span className="row-name">{i.name}</span>
        <span className="row-meta">
          {i.pos} · {i.team}
          {!i.mine && i.owner && <> · <b>{i.owner}</b></>}
        </span>
        <span className="row-injury">{injuryText(i)}</span>
      </div>
      <div className="row-side">
        <span className="row-value num">{i.ros ? int(i.ros.mean) : '—'}</span>
        <span className="row-sub">ROS</span>
      </div>
    </li>
  )
}

export default function Injuries({ injuries }: { injuries: LeagueInjury[] }) {
  const mine = injuries.filter((i) => i.mine)
  const others = injuries.filter((i) => !i.mine)
  return (
    <>
      <section className="group">
        <h2 className="group-title">Mon équipe</h2>
        {mine.length ? <ul className="rows">{mine.map((i) => <Row key={i.espn_id} i={i} />)}</ul>
          : <p className="empty">Aucun blessé.</p>}
      </section>
      <section className="group">
        <h2 className="group-title">Dans la ligue</h2>
        <p className="group-note">Les DTD qui ne manquent aucun match sont omis. Triés par ROS.</p>
        {others.length ? <ul className="rows">{others.map((i) => <Row key={i.espn_id} i={i} />)}</ul>
          : <p className="empty">Aucun blessé.</p>}
      </section>
    </>
  )
}
