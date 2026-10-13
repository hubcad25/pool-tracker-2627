import { useEffect, useState } from 'react'
import { shortDate } from './format'
import FreeAgents from './tabs/FreeAgents'
import Injuries from './tabs/Injuries'
import Standings from './tabs/Standings'
import Team from './tabs/Team'
import Today from './tabs/Today'
import type { Dashboard, Today as TodayData } from './types'

// L'onglet vit dans l'URL (#fa) : une notif peut ouvrir directement le bon
const TABS = [
  { id: 'aujourdhui', label: "Aujourd'hui" },
  { id: 'equipe', label: 'Équipe' },
  { id: 'blessures', label: 'Blessures' },
  { id: 'fa', label: 'FA' },
  { id: 'ligue', label: 'Ligue' },
] as const
type Tab = (typeof TABS)[number]['id']

const fromHash = (): Tab => TABS.find((t) => `#${t.id}` === location.hash.split('/')[0])?.id ?? 'aujourdhui'
// #equipe/12 : la page Équipe d'une autre équipe du pool
const teamFromHash = (): number | null => {
  const [tab, id] = location.hash.split('/')
  return tab === '#equipe' && id && /^\d+$/.test(id) ? Number(id) : null
}

function daysOld(iso: string) {
  const today = new Date()
  const local = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const [y, m, d] = iso.split('-').map(Number)
  return Math.round((local.getTime() - new Date(y, m - 1, d).getTime()) / 86_400_000)
}

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState(false)
  // data/today.json : réécrit pendant la soirée, à part de dashboard.json ; absent = pas de soirée
  const [today, setToday] = useState<TodayData | null>(null)
  const [tab, setTab] = useState<Tab>(fromHash)
  const [teamId, setTeamId] = useState<number | null>(teamFromHash)

  // Relu à chaque retour au premier plan : une PWA reste ouverte en arrière-plan des heures
  useEffect(() => {
    const load = () => {
      fetch('dashboard.json', { cache: 'no-cache' })
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((d) => {
          setData(d)
          setError(false)
        })
        .catch(() => setError(true))
      fetch('today.json', { cache: 'no-cache' })
        .then((r) => (r.ok ? r.json() : null))
        .then(setToday)
        .catch(() => {})
    }
    const onVisible = () => document.visibilityState === 'visible' && load()
    load()
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [])

  useEffect(() => {
    const onHash = () => {
      setTab(fromHash())
      setTeamId(teamFromHash())
    }
    addEventListener('hashchange', onHash)
    return () => removeEventListener('hashchange', onHash)
  }, [])

  // Accolades obligatoires : scrollTo retourne une Promise dans les Chrome récents, que React prendrait
  // pour une fonction de nettoyage (écran vide au changement d'onglet)
  useEffect(() => {
    scrollTo(0, 0)
  }, [tab, teamId])

  if (error && !data) return <main className="app"><p className="empty">Impossible de charger les données.</p></main>
  if (!data) return <main className="app" />

  const age = daysOld(data.day)
  const missing = <p className="empty">Pas encore de données : reviens après la mise à jour de midi.</p>

  return (
    <>
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

        {tab === 'aujourdhui' && ((today ?? data.today) ? <Today today={(today ?? data.today)!} /> : missing)}
        {tab === 'equipe' && (
          <Team
            players={(teamId != null && data.teams_players?.[String(teamId)]) || data.players}
            teamId={teamId != null && data.teams_players?.[String(teamId)] ? teamId : (data.team?.id ?? 5)}
            teams={data.standings ?? []}
            myId={data.team?.id ?? 5}
          />
        )}
        {tab === 'blessures' && (data.injuries ? <Injuries injuries={data.injuries} teamIds={Object.fromEntries((data.standings ?? []).map((r) => [r.abbrev ?? '', r.team_id]))} /> : missing)}
        {tab === 'fa' && (data.free_agents ? <FreeAgents fa={data.free_agents} /> : missing)}
        {tab === 'ligue' && (data.standings?.length ? <Standings rows={data.standings} /> : missing)}
      </main>

      <nav className="tabs">
        {TABS.map((t) => (
          <a key={t.id} href={`#${t.id}`} className={t.id === tab ? 'is-active' : undefined}>
            {t.label}
          </a>
        ))}
      </nav>
    </>
  )
}
