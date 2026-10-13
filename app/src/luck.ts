// Les textes de chance, partout les mêmes (cartes, FA, blessés, Ligue). Point de vue du propriétaire :
// chanceux = la chance lui a rapporté des points (vert), malchanceux = elle lui en a coûté (rouge).
import { dec } from './format'

export const pts = (x: number) => (Math.abs(x) >= 2 ? 'pts' : 'pt')

/** « ~2 », « ~0,7 » */
export const about = (x: number) => `~${Math.abs(x) >= 0.95 ? Math.round(Math.abs(x)) : dec(Math.abs(x))}`

/** « 9 pts, dont ~2 de chance » / « 4 pts, ~2 de moins que mérité » / « 4 pts, ni chance ni malchance » */
export function luckPhrase(points: number, net: number) {
  const head = `${points} ${pts(points)}`
  if (Math.abs(net) < 0.5) return `${head}, ni chance ni malchance`
  return net > 0 ? `${head}, dont ${about(net)} de chance` : `${head}, ${about(net)} de moins que mérité`
}

/** Chance d'une équipe : « +12 pts grâce à la chance » / « 6 pts perdus à la malchance » */
export function teamLuckPhrase(net: number) {
  if (Math.abs(net) < 0.5) return 'ni chance ni malchance'
  return net > 0 ? `${about(net)} pts grâce à la chance` : `${about(net)} pts perdus à la malchance`
}

/** Centile (0,5 = normal) → « plus chanceux que 86 % des joueurs dans sa situation » */
export function percentileText(q: number) {
  if (q >= 0.6) return `plus chanceux que ${Math.round(q * 100)} % des joueurs dans sa situation`
  if (q <= 0.4) return `plus malchanceux que ${Math.round((1 - q) * 100)} % des joueurs dans sa situation`
  return 'chance normale'
}
