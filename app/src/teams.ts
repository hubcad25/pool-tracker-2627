// Une couleur fixe par équipe du pool (ESPN team_id → --team-N de theme.css), la même dans tous les onglets.
// Ordre fixe, jamais recalculé : la couleur suit l'équipe, pas son rang du jour. Teintes 1 à 8 = palette
// catégorielle du skill dataviz (validée clair et sombre, paires voisines) ; 9 à 12 = teintes 2 à 5 un pas plus
// foncé. Douze couleurs ne se distinguent pas toutes deux à deux : le nom de l'équipe est toujours écrit à
// côté de sa couleur, la couleur ne sert qu'à la retrouver d'un coup d'œil.
const SLOT: Record<number, number> = { 5: 1, 1: 2, 12: 3, 4: 4, 7: 5, 9: 6, 3: 7, 11: 8, 2: 9, 10: 10, 6: 11, 8: 12 }

export const teamColor = (teamId: number) => `var(--team-${SLOT[teamId] ?? 1})`

/** Teinte claire de la couleur d'une équipe (« encore possible », ROS) */
export const teamTint = (teamId: number) => `color-mix(in oklab, ${teamColor(teamId)} 35%, var(--surface-1))`
