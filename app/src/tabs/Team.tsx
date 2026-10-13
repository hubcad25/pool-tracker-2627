import Group from '../components/Group'
import { BandScale } from '../components/Band'
import PlayerCard from '../components/PlayerCard'
import { SortBar, sortBy, useSort, type SortOption } from '../components/Sort'
import { lastName } from '../format'
import { tone } from '../tone'
import { teamColor } from '../teams'
import type { Player, Standing } from '../types'

const GROUPS: { slot: Player['slot']; label: string }[] = [
  { slot: 'F', label: 'Attaquants' },
  { slot: 'D', label: 'Défenseurs' },
  { slot: 'G', label: 'Gardien' },
  { slot: 'IR', label: 'Réserve (IR)' },
]
// Étiquettes tous les 50 points ; graduations pâles tous les 10 (Band)
const TICK = 50

type Key = 'ros' | 'points' | 'luck' | 'name'
const SORT: SortOption<Key>[] = [
  { key: 'ros', label: 'ROS', dir: 'desc' },
  { key: 'points', label: 'Pts', dir: 'desc' },
  { key: 'luck', label: 'Chance', dir: 'desc' },
  { key: 'name', label: 'Nom', dir: 'asc' },
]

const luck = (p: Player) => (p.luck ? (p.luck.net_points ?? p.points - p.luck.expected_points) : null)

/** Choix de l'équipe affichée : change l'URL (#equipe/<team_id>), donc le lien se partage */
function TeamPicker({ teamId, teams, myId }: { teamId: number; teams: Standing[]; myId: number }) {
  if (teams.length < 2) return null
  const sorted = [...teams].sort((a, b) => (a.team_id === myId ? -1 : b.team_id === myId ? 1 : (a.name ?? '').localeCompare(b.name ?? '', 'fr')))
  return (
    <label className="team-picker">
      <i className="swatch" style={{ background: teamColor(teamId) }} />
      <select
        aria-label="Équipe"
        value={teamId}
        onChange={(e) => {
          const id = Number(e.target.value)
          location.hash = id === myId ? '#equipe' : `#equipe/${id}`
        }}
      >
        {sorted.map((t) => (
          <option key={t.team_id} value={t.team_id}>
            {t.name ?? t.abbrev}
            {t.team_id === myId ? ' (moi)' : ''}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function Team({ players, teamId, teams, myId }: { players: Player[]; teamId: number; teams: Standing[]; myId: number }) {
  const [sort, setSort] = useSort('equipe', SORT)
  // Échelle commune à toute l'équipe (0 → total estimé) : les cartes se comparent d'un coup d'œil
  const top = Math.max(TICK, ...players.flatMap((p) => [p.final?.p90 ?? 0, p.prior?.p90 ?? 0, p.points]))
  const max = Math.ceil(top / 10) * 10
  const ticks = Array.from({ length: Math.floor(max / TICK) + 1 }, (_, i) => i * TICK)
  return (
    <>
      <TeamPicker teamId={teamId} teams={teams} myId={myId} />
      <p className="legend-line">
        <i className="lg-real" /> points faits, <i className="lg-ros" /> à venir (ROS) jusqu'au total estimé{' '}
        <i className="lg-range" /> ; <i className="lg-luck-good" />/<i className="lg-luck-bad" /> points gagnés / perdus par la chance ;{' '}
        <i className="lg-prior2" /> en dessous : prévu avant la saison.
      </p>
      <p className="group-note">
        ROS <span style={tone(0.4, 0.45)}>en vert</span> ou <span style={tone(-0.4, 0.45)}>en rouge</span> : au-dessus ou en
        dessous de ce qu'on prévoyait avant la saison.
      </p>
      <SortBar options={SORT} sort={sort} onChange={setSort} />
      {GROUPS.map(({ slot, label }) => {
        const group = sortBy(players.filter((p) => p.slot === slot), sort, (p, k) =>
          k === 'ros' ? (p.ros?.mean ?? null) : k === 'points' ? p.points : k === 'luck' ? luck(p) : lastName(p.name),
        )
        if (!group.length) return null
        return (
          <Group key={slot} id={`equipe-${slot}`} title={label}>
            <BandScale max={max} ticks={ticks} />
            {group.map((p) => (
              <PlayerCard key={p.espn_id} player={p} max={max} />
            ))}
          </Group>
        )
      })}
    </>
  )
}
