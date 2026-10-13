// P(1er) de chaque équipe, même calcul que pipeline/dashboard.first_place_odds (mêmes constantes) :
// totaux finaux ~ normales indépendantes, P_i = ∫ φ_i(x) ∏_{j≠i} Φ_j(x) dx par une somme de Riemann.
const MIN_SD = 1.0
const GRID_STEP = 0.1
const GRID_SDS = 8

const phi = (z: number) => Math.exp((-z * z) / 2) / Math.sqrt(2 * Math.PI)

/** Φ(z), par l'approximation d'Abramowitz et Stegun 7.1.26 de erf (erreur < 1,5e-7) */
function cdf(z: number) {
  const x = Math.abs(z) / Math.SQRT2
  const t = 1 / (1 + 0.3275911 * x)
  const erf = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x)
  return 0.5 * (1 + (z >= 0 ? erf : -erf))
}

export function firstPlaceOdds(means: number[], sds: number[]): number[] {
  const s = sds.map((sd) => Math.max(sd, MIN_SD))
  const lo = Math.min(...means.map((m, i) => m - GRID_SDS * s[i]))
  const hi = Math.max(...means.map((m, i) => m + GRID_SDS * s[i]))
  const step = GRID_STEP * Math.min(...s)
  const odds = means.map(() => 0)
  for (let k = 0; k <= Math.floor((hi - lo) / step); k++) {
    const x = lo + (k + 0.5) * step
    const zs = means.map((m, i) => (x - m) / s[i])
    const cdfs = zs.map(cdf)
    zs.forEach((z, i) => {
      const density = phi(z) / s[i]
      if (density < 1e-300) return
      let others = 1
      cdfs.forEach((c, j) => {
        if (j !== i) others *= c
      })
      odds[i] += density * others * step
    })
  }
  return odds
}
