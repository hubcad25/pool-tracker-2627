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

// Numéros de chandail par espn_id (dashboard.json, rosters LNH du jour) ; remplis par App au chargement
let numbers: Record<string, number> = {}
export const setNumbers = (n: Record<string, number> | undefined) => (numbers = n ?? {})

/** Le nom affiché partout : « Leon Draisaitl » → « L. Draisaitl #29 » (sans numéro s'il est inconnu) */
export function playerName(name: string, espnId?: number) {
  const [first, ...rest] = name.split(' ')
  const short = rest.length ? `${first.includes('.') ? first : `${first[0]}.`} ${rest.join(' ')}` : name
  const n = espnId != null ? numbers[String(espnId)] : undefined
  return n != null ? `${short} #${n}` : short
}

const STATUS: Record<string, string> = { DAY_TO_DAY: 'DTD', OUT: 'OUT', INJURY_RESERVE: 'IR', SUSPENSION: 'Suspendu' }

/** « IR · retour ~7 nov · manque 15 m. » */
export function injuryText(i: Pick<Injury, 'expected_return' | 'games_missed'> & { status: string; out_for_season?: boolean }) {
  const status = STATUS[i.status] ?? i.status
  if (i.out_for_season) return `${status} · saison terminée`
  if (!i.expected_return) return `${status} · retour inconnu`
  const missed = i.games_missed ? ` · manque ${i.games_missed} m.` : ''
  return `${status} · retour ~${shortDate(i.expected_return)}${missed}`
}

/** Probabilité → « 75 % », « 4,2 % », « <0,1 % » */
export const prob = (x: number) => (x < 0.001 ? '<0,1 %' : `${dec(x * 100, x < 0.1 ? 1 : 0)} %`)

/** Heure de Montréal d'un instant ISO : « 19 h », « 19 h 30 » */
export function clock(iso: string) {
  const [h, m] = new Date(iso)
    .toLocaleTimeString('fr-CA', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'America/Toronto' })
    .split(/\D+/)
    .map(Number)
  return m ? `${h} h ${String(m).padStart(2, '0')}` : `${h} h`
}
