import { BandScale } from '../components/Band'
import PlayerCard from '../components/PlayerCard'
import type { Player } from '../types'

const GROUPS: { slot: Player['slot']; label: string }[] = [
  { slot: 'F', label: 'Attaquants' },
  { slot: 'D', label: 'Défenseurs' },
  { slot: 'G', label: 'Gardien' },
  { slot: 'IR', label: 'Réserve (IR)' },
]
const TICK = 25

export default function Team({ players }: { players: Player[] }) {
  // Échelle commune à toute l'équipe : les cartes se comparent d'un coup d'œil
  const top = Math.max(TICK, ...players.flatMap((p) => [p.final?.p90 ?? 0, p.prior?.p90 ?? 0]))
  const max = Math.ceil(top / TICK) * TICK
  const ticks = Array.from({ length: max / TICK + 1 }, (_, i) => i * TICK)
  return (
    <>
      <div className="legend">
        <span><i className="lg-prior" /> Préseason p10–p90</span>
        <span><i className="lg-points" /> Points acquis</span>
        <span><i className="lg-final" /> Total projeté p10–p90</span>
      </div>
      {GROUPS.map(({ slot, label }) => {
        const group = players.filter((p) => p.slot === slot)
        if (!group.length) return null
        return (
          <section key={slot} className="group">
            <h2 className="group-title">{label}</h2>
            <BandScale max={max} ticks={ticks} />
            {group.map((p) => (
              <PlayerCard key={p.espn_id} player={p} max={max} ticks={ticks} />
            ))}
          </section>
        )
      })}
    </>
  )
}
