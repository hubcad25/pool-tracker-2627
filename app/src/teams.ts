// Identité fixe de chaque équipe du pool (src/poolers.json) : une icône unicolore (PoolerIcon) et une couleur
// (--team-N de theme.css), les mêmes dans tous les onglets et dans les notifs. L'icône suit l'équipe, pas son rang
// du jour. Les 12 couleurs ont chacune un nom de teinte différent (theme.css) ; les rivaux principaux ont les plus
// contrastées entre elles et les icônes les plus visibles. Changer poolers.json → npm run poolers (icônes de l'app et des notifs).
import poolers from './poolers.json'

const SLOT: Record<string, { slot: number }> = poolers

export const teamColor = (teamId: number) => `var(--team-${SLOT[teamId]?.slot ?? 1})`

/** Teinte claire de la couleur d'une équipe (« encore possible », ROS) */
export const teamTint = (teamId: number) => `color-mix(in oklab, ${teamColor(teamId)} 35%, var(--surface-1))`
