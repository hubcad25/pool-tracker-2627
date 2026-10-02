const MONTHS = ['janv', 'févr', 'mars', 'avr', 'mai', 'juin', 'juil', 'août', 'sept', 'oct', 'nov', 'déc']

export const int = (x: number) => Math.round(x).toString()

export const dec = (x: number, digits = 1) =>
  x.toLocaleString('fr-CA', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const signed = (x: number, digits = 1) => (x > 0 ? '+' : x < 0 ? '−' : '') + dec(Math.abs(x), digits)

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
