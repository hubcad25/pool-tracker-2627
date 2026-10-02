import type { Injury } from './types'

const MONTHS = ['janv', 'févr', 'mars', 'avr', 'mai', 'juin', 'juil', 'août', 'sept', 'oct', 'nov', 'déc']

export const int = (x: number) => Math.round(x).toString()

export const dec = (x: number, digits = 1) =>
  x.toLocaleString('fr-CA', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export function signed(x: number, digits = 1) {
  // Arrondir avant le signe : −0,3 affiché sans décimale doit donner « 0 », pas « −0 »
  const r = Number(x.toFixed(digits))
  return (r > 0 ? '+' : r < 0 ? '−' : '') + dec(Math.abs(r), digits)
}

export const pct = (x: number | null) => (x == null ? '—' : `${dec(x * 100)} %`)

export function shortDate(iso: string) {
  const [, m, d] = iso.split('-').map(Number)
  return `${d} ${MONTHS[m - 1]}`
}

/** Minutes décimales → m:ss */
export function minutes(x: number) {
  const m = Math.floor(x)
  return `${m}:${String(Math.round((x - m) * 60)).padStart(2, '0')}`
}

/** Le nom de famille (« Leon Draisaitl » → « Draisaitl ») */
export const lastName = (name: string) => name.split(' ').slice(1).join(' ') || name

const STATUS: Record<string, string> = { DAY_TO_DAY: 'DTD', OUT: 'OUT', INJURY_RESERVE: 'IR', SUSPENSION: 'Suspendu' }

/** « IR · retour ~7 nov · manque 15 m. » */
export function injuryText(i: Pick<Injury, 'expected_return' | 'games_missed'> & { status: string; out_for_season?: boolean }) {
  const status = STATUS[i.status] ?? i.status
  if (i.out_for_season) return `${status} · saison terminée`
  if (!i.expected_return) return `${status} · retour inconnu`
  const missed = i.games_missed ? ` · manque ${i.games_missed} m.` : ''
  return `${status} · retour ~${shortDate(i.expected_return)}${missed}`
}
