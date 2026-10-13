// La soirée en valeurs entières : total = réel + Poisson(encore possible). Même loi que l'attendu du pipeline
// (soiree.py), seulement vue point par point. Les points arrivent en grappes (but + passes) : la vraie loi est un peu
// plus étalée, l'intervalle est donc un peu trop étroit.
const TAIL = 0.995 // on coupe les queues : 0,5 % de chaque côté
const LEVEL = 0.8 // intervalle 80 %

export type NightDist = {
  /** probs[i] = P(total = values[i]) */
  values: number[]
  probs: number[]
  /** Le ou les totaux les plus probables (deux quand l'encore possible est entier) */
  modes: number[]
  /** Intervalle central d'au moins 80 % */
  lo: number
  hi: number
}

export function nightDist(actual: number, left: number): NightDist {
  const values: number[] = []
  const probs: number[] = []
  let p = Math.exp(-left)
  let cum = 0
  for (let k = 0; k < 200 && (cum < TAIL || k <= left); k++) {
    if (k > 0) p *= left / k
    values.push(actual + k)
    probs.push(p)
    cum += p
  }
  const quantile = (q: number) => {
    let c = 0
    for (let i = 0; i < probs.length; i++) if ((c += probs[i]) >= q) return values[i]
    return values[values.length - 1]
  }
  const lo = quantile((1 - LEVEL) / 2)
  const hi = quantile((1 + LEVEL) / 2)
  // Même coupe à gauche (après les quantiles) : avec 13,8 attendus, 0 à 5 pts ne pèsent presque rien
  const start = values.indexOf(quantile(1 - TAIL))
  values.splice(0, start)
  probs.splice(0, start)
  const top = Math.max(...probs)
  const modes = values.filter((_, i) => probs[i] >= top * (1 - 1e-9))
  return { values, probs, modes, lo, hi }
}

export const atLeastOne = (actual: number, left: number) => (actual >= 1 ? 1 : 1 - Math.exp(-left))
