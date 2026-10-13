// Gardien en direct, même loi que model/soir.py : buts de chaque équipe ~ Poisson indépendants, égalité après
// 60 min → prolongation gagnée à 50 %. Points de pool : 2 la victoire, 1 la défaite en prolongation, +1 le
// blanchissage. Pendant le match, les buts qui restent ~ Poisson(buts attendus × fraction du temps qui reste),
// ajoutés au pointage.
const MAX = 20
const LEAGUE_GOALS = 3.1 // buts par équipe et par match, sans cotes (pipeline/contexte.py)

function pmf(lam: number): number[] {
  const p = [Math.exp(-lam)]
  for (let k = 1; k <= MAX; k++) p.push((p[k - 1] * lam) / k)
  return p
}

/** P(victoire), P(défaite en prolongation), P(blanchissage) et points attendus des gardiens d'une équipe, d'après
 *  le pointage (`gf`, `ga`) et les buts attendus encore à venir (`lf`, `la`). */
export function goalieOutlook(gf: number, ga: number, lf: number, la: number) {
  const pf = pmf(lf)
  const pa = pmf(la)
  let lead = 0
  let tie = 0
  for (let i = 0; i <= MAX; i++)
    for (let j = 0; j <= MAX; j++) {
      const d = gf + i - (ga + j)
      if (d > 0) lead += pf[i] * pa[j]
      else if (d === 0) tie += pf[i] * pa[j]
    }
  const win = lead + tie / 2
  const otl = tie / 2
  // Blanchissage : aucun but contre et victoire (0-0 après 60 min : prolongation ou tirs de barrage à 50 %)
  const shutout = ga > 0 ? 0 : pa[0] * (gf > 0 ? 1 : 1 - pf[0] / 2)
  return { win, otl, shutout, points: 2 * win + otl + shutout }
}

export type GoalieNight = {
  /** Devant le filet (true), sur le banc (false), pas encore connu (null) */
  inNet: boolean | null
  score: { for: number; against: number }
  /** P(victoire), P(défaite en prolongation) et P(blanchissage) de son équipe, d'après le pointage */
  win: number
  otl: number
  shutout: number
}

/** La soirée d'un gardien. L'attendu d'avant-match compte la chance qu'il ne joue pas ; une fois le match
 *  commencé, on sait s'il joue : prévu = ses points s'il joue, ou 0 sur le banc. */
export function goalieNight(expected: number, goals: { for: number; against: number } | null,
  score: { for: number; against: number }, left: number, inNet: boolean | null) {
  const pre = goalieOutlook(0, 0, goals?.for ?? LEAGUE_GOALS, goals?.against ?? LEAGUE_GOALS)
  const now = goalieOutlook(score.for, score.against, (goals?.for ?? LEAGUE_GOALS) * left, (goals?.against ?? LEAGUE_GOALS) * left)
  const plays = inNet === false ? 0 : inNet === true ? 1 : Math.min(1, expected / pre.points)
  const prevu = inNet === false ? 0 : inNet === true ? Math.max(expected, pre.points) : expected
  return {
    expected: prevu,
    left: prevu * (now.points / pre.points),
    p1Start: plays * (pre.win + pre.otl),
    p1: plays * (now.win + now.otl),
    goalie: { inNet, score, win: now.win, otl: now.otl, shutout: now.shutout } satisfies GoalieNight,
  }
}
