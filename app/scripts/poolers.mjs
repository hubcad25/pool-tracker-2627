// Icônes des poolers (src/poolers.json → icône Phosphor « fill », licence MIT, + teinte --team-<slot>).
// Écrit src/poolerIcons.ts (tracés, pour l'app : la couleur vient du thème) et public/poolers/<team_id>.png
// (couleur du thème clair, pour les notifs ntfy, qui n'affichent pas le SVG). À relancer après un changement
// de poolers.json : npm run poolers
import { Resvg } from '@resvg/resvg-js'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'

const here = (p) => new URL(`../${p}`, import.meta.url)
const poolers = JSON.parse(readFileSync(here('src/poolers.json')))
const theme = readFileSync(here('src/theme.css'), 'utf8').split(':root')[1]  // thème clair
const hex = (slot) => theme.match(new RegExp(`--team-${slot}: (#[0-9a-f]{6})`))[1]
const svg = (icon) => readFileSync(here(`node_modules/@phosphor-icons/core/assets/fill/${icon}-fill.svg`), 'utf8')
const inner = (s) => s.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')

mkdirSync(here('public/poolers'), { recursive: true })
const paths = {}
for (const [id, { icon, slot }] of Object.entries(poolers)) {
  paths[id] = inner(svg(icon))
  const colored = svg(icon).replace('fill="currentColor"', `fill="${hex(slot)}"`)
  const png = new Resvg(colored, { fitTo: { mode: 'width', value: 192 } }).render().asPng()
  writeFileSync(here(`public/poolers/${id}.png`), png)
}
writeFileSync(here('src/poolerIcons.ts'),
  '// Généré par scripts/poolers.mjs (ne pas modifier) : tracés des icônes Phosphor, viewBox 0 0 256 256\n'
  + `export const ICONS: Record<number, string> = ${JSON.stringify(paths, null, 1)}\n`)
