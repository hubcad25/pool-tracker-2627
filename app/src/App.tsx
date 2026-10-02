import { useEffect, useState } from 'react'
import { BandScale } from './components/Band'
import PlayerCard from './components/PlayerCard'
import { shortDate } from './format'
import type { Dashboard, Player } from './types'

const GROUPS: { slot: Player['slot']; label: string }[] = [
  { slot: 'F', label: 'Attaquants' },
  { slot: 'D', label: 'Défenseurs' },
  { slot: 'G', label: 'Gardien' },
  { slot: 'IR', label: 'Réserve (IR)' },
]
const TICK = 25

function daysOld(iso: string) {
  const today = new Date()
  const local = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const [y, m, d] = iso.split('-').map(Number)
  return Math.round((local.getTime() - new Date(y, m - 1, d).getTime()) / 86_400_000)
}

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetch('dashboard.json', { cache: 'no-cache' })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setError(true))
  }, [])

  if (error) return <main className="app"><p className="empty">Impossible de charger les données.</p></main>
  if (!data) return <main className="app" />

  // Échelle commune à toute l'équipe : les cartes se comparent d'un coup d'œil
  const top = Math.max(TICK, ...data.players.flatMap((p) => [p.final?.p90 ?? 0, p.prior?.p90 ?? 0]))
  const max = Math.ceil(top / TICK) * TICK
  const ticks = Array.from({ length: max / TICK + 1 }, (_, i) => i * TICK)
  const age = daysOld(data.day)

  return (
    <main className="app">
      <header className="top">
        <div>
          <p className="top-league">HABS FOR THE CUP</p>
          <h1 className="top-team">{data.team?.name ?? 'Mon équipe'}</h1>
        </div>
        <p className={`top-day${age > 1 ? ' is-stale' : ''}`}>
          {age > 1 ? `Données vieilles de ${age} jours` : `Données du ${shortDate(data.day)}`}
        </p>
      </header>

      {data.alerts.length > 0 && (
        <section className="alerts">
          {data.alerts.map((a, i) => (
            <p key={i} className="alert">{a.message}</p>
          ))}
        </section>
      )}

      <div className="legend">
        <span><i className="lg-prior" /> Préseason p10–p90</span>
        <span><i className="lg-points" /> Points acquis</span>
        <span><i className="lg-final" /> Total projeté p10–p90</span>
      </div>

      {GROUPS.map(({ slot, label }) => {
        const players = data.players.filter((p) => p.slot === slot)
        if (!players.length) return null
        return (
          <section key={slot} className="group">
            <div className="group-head">
              <h2>{label}</h2>
              <BandScale max={max} ticks={ticks} />
            </div>
            {players.map((p) => (
              <PlayerCard key={p.espn_id} player={p} max={max} ticks={ticks} />
            ))}
          </section>
        )
      })}
    </main>
  )
}
