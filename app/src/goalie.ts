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
  /** Partant (true), pas partant (false) ou pas encore connu (null) : figé dès le début du match */
  started: boolean | null
  /** Devant le filet maintenant (true), sur le banc (false), pas encore connu (null) */
  inNet: boolean | null
  /** Sa chance de commencer selon MoneyPuck, avant le match (null sans info) */
  pStart: number | null
  score: { for: number; against: number }
  /** P(victoire), P(défaite en prolongation) et P(blanchissage) de son équipe, d'après le pointage */
  win: number
  otl: number
  shutout: number
}

/** La soirée d'un gardien. L'attendu d'avant-match compte la chance qu'il ne commence pas (MoneyPuck, sinon sa
 *  part des départs). Le prévu se fige sur le partant : ses points s'il commence, 0 sinon (même s'il entre en
 *  relève). Ce qui reste possible suit celui qui est devant le filet. */
export function goalieNight(expected: number, pStart: number | null, goals: { for: number; against: number } | null,
  score: { for: number; against: number }, left: number, role: { started: boolean | null; inNet: boolean | null }) {
  const { started, inNet } = role
  const pre = goalieOutlook(0, 0, goals?.for ?? LEAGUE_GOALS, goals?.against ?? LEAGUE_GOALS)
  const raw = goalieOutlook(score.for, score.against, (goals?.for ?? LEAGUE_GOALS) * left, (goals?.against ?? LEAGUE_GOALS) * left)
  // Changement de gardien : plus de blanchissage possible (il faut être seul devant le filet)
  const now = started === false || (started === true && inNet === false) ? { ...raw, points: raw.points - raw.shutout, shutout: 0 } : raw
  const plays = started === null ? (pStart ?? Math.min(1, expected / pre.points)) : started ? 1 : 0
  const prevu = started === null ? expected : started ? pre.points : 0
  const here = inNet === null ? plays : inNet ? 1 : 0
  return {
    expected: prevu,
    left: inNet === null ? prevu * (now.points / pre.points) : here * now.points,
    p1Start: plays * (pre.win + pre.otl),
    p1: here * (now.win + now.otl),
    goalie: { started, inNet, pStart, score, win: now.win, otl: now.otl, shutout: now.shutout } satisfies GoalieNight,
  }
}
