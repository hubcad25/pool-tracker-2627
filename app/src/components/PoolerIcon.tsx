import { ICONS } from '../poolerIcons'
import { teamColor } from '../teams'

/** Icône d'une équipe du pool, dans sa couleur (remplace la pastille de couleur) */
export default function PoolerIcon({ teamId }: { teamId: number }) {
  return (
    <svg className="pooler-icon" viewBox="0 0 256 256" fill={teamColor(teamId)} aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: ICONS[teamId] ?? '<circle cx="128" cy="128" r="72"/>' }} />
  )
}
