import type { CSSProperties } from 'react'

/** Couleur d'un chiffre selon son ampleur : du gris neutre (--text-dim) vers --good ou --danger, de façon continue.
 *  `x` : l'écart signé avec le neutre ; `full` : l'écart qui donne la couleur pleine. Le signe ou la flèche
 *  restent toujours écrits à côté : la couleur ne fait que renforcer. Les deux pôles et le gris passent 4,5:1 en
 *  texte, clair comme sombre (theme.css), donc tous les mélanges aussi. */
export function tone(x: number, full: number, positive: 'good' | 'bad' = 'good'): CSSProperties {
  const t = Math.min(1, Math.abs(x) / full)
  if (t < 0.04) return { color: 'var(--text-dim)' }
  const good = (x > 0) === (positive === 'good')
  return { color: `color-mix(in oklab, var(${good ? '--good' : '--danger'}) ${Math.round(100 * t ** 0.75)}%, var(--text-dim))` }
}

/** Fond d'une marque (barre) selon la même règle, du gris clair vers la couleur pleine */
export function toneFill(x: number, full: number, positive: 'good' | 'bad' = 'good'): string {
  const t = Math.min(1, Math.abs(x) / full)
  const good = (x > 0) === (positive === 'good')
  return `color-mix(in oklab, var(${good ? '--good' : '--danger'}) ${Math.round(35 + 65 * t ** 0.75)}%, var(--surface-3))`
}

/** ▲ / ▼ devant un écart (rien près de zéro) */
export const arrow = (x: number, eps = 0.05) => (x > eps ? '▲ ' : x < -eps ? '▼ ' : '')
