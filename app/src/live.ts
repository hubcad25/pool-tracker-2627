// La soirée en direct : pointage LNH via le proxy CORS (infra/aws/proxy_lnh.py, VITE_LNH_PROXY).
// Sans proxy (ou s'il ne répond pas), tout se rabat sur today.json : points des matchs FINAL seulement.
import { useEffect, useRef, useState } from 'react'
import { goalieNight, type GoalieNight } from './goalie'
import { atLeastOne } from './poisson'
import type { GameState, Today, TodayTeam, TonightPlayer } from './types'

const PROXY = (import.meta.env.VITE_LNH_PROXY as string | undefined)?.replace(/\/$/, '')
const POLL_MS = 60_000
const SOON_MS = 30 * 60_000
const REGULATION = 3 * 20 * 60
const STATES: Record<string, GameState> = { FUT: 'FUT', PRE: 'FUT', LIVE: 'LIVE', CRIT: 'LIVE', OFF: 'FINAL', FINAL: 'FINAL' }

export type LiveGame = {
  state: GameState
  /** Fraction du match réglementaire qui reste (1 avant le match, 0 à la fin et en prolongation) */
  left: number
  /** « 2e · 14:02 », « 2e entr. », « Prol. », « Final » */
  clock: string | null
  /** Points de pool de chaque joueur du match, par nhl_id (gardiens : seulement une fois le match terminé) */
  points: Map<number, number>
  /** Les buts du match, dans l'ordre (fusillade exclue) */
  goals: Goal[]
  /** Pointage, par abréviation LNH */
  score: Record<string, number>
  /** Gardiens qui ont joué (nhl_id), d'après le boxscore ; null tant qu'on ne le sait pas */
  goalies: Set<number> | null
}

export type Goal = {
  period: string
  time: string
  strength: string
  team: string
  scorer: { id: number; name: string }
  assists: { id: number; name: string }[]
}

export type Live = { games: Map<number, LiveGame>; at: Date | null; status: 'off' | 'ok' | 'error' }

type ScoreGame = {
  id: number
  gameState: string
  period?: number
  periodDescriptor?: { number: number; periodType: string }
  clock?: { secondsRemaining: number; inIntermission: boolean; timeRemaining: string }
  homeTeam?: { abbrev: string; score?: number }
  awayTeam?: { abbrev: string; score?: number }
  goals?: {
    playerId: number
    name?: { default: string }
    teamAbbrev?: string
    strength?: string
    timeInPeriod?: string
    periodDescriptor?: { number: number; periodType: string }
    assists?: { playerId: number; name?: { default: string } }[]
  }[]
}

type BoxPlayer = { playerId: number; goals?: number; assists?: number; toi?: string; decision?: string; goalsAgainst?: number }
type BoxSide = { forwards?: BoxPlayer[]; defense?: BoxPlayer[]; goalies?: BoxPlayer[] }

/** Fraction du temps réglementaire restante. Pendant l'entracte, `period` est la période qui vient de finir. */
export function regulationLeft(g: ScoreGame): number {
  const state = STATES[g.gameState] ?? 'FUT'
  if (state === 'FUT') return 1
  if (state === 'FINAL') return 0
  const period = g.periodDescriptor?.number ?? g.period ?? 1
  if (period > 3 || g.periodDescriptor?.periodType === 'OT' || g.periodDescriptor?.periodType === 'SO') return 0
  const inPeriod = g.clock?.inIntermission ? 0 : (g.clock?.secondsRemaining ?? 1200)
  return Math.max(0, Math.min(1, ((3 - period) * 1200 + inPeriod) / REGULATION))
}

function clockLabel(g: ScoreGame): string | null {
  const state = STATES[g.gameState] ?? 'FUT'
  if (state === 'FINAL') return 'Final'
  if (state === 'FUT') return null
  const n = g.periodDescriptor?.number ?? g.period ?? 1
  const type = g.periodDescriptor?.periodType
  if (type === 'SO') return 'Fusillade'
  const name = type === 'OT' || n > 3 ? 'Prol.' : n === 1 ? '1re' : `${n}e`
  if (g.clock?.inIntermission) return `${name} entr.`
  return g.clock ? `${name} · ${g.clock.timeRemaining}` : name
}

/** G + A pendant le match, d'après la liste des buts (la fusillade ne compte pas) */
export function pointsFromGoals(g: ScoreGame): Map<number, number> {
  const out = new Map<number, number>()
  const add = (id: number) => out.set(id, (out.get(id) ?? 0) + 1)
  for (const goal of g.goals ?? []) {
    if (goal.periodDescriptor?.periodType === 'SO') continue
    add(goal.playerId)
    for (const a of goal.assists ?? []) add(a.playerId)
  }
  return out
}

/** Points de pool d'un match terminé, même règle que pipeline/sources/nhl.fetch_points : patineurs G + A ;
 *  gardiens 2 la victoire, 1 la défaite en prolongation, +1 le blanchissage (gagnant seul devant le filet). */
export function pointsFromBoxscore(box: { playerByGameStats?: Record<string, BoxSide> }): Map<number, number> {
  const out = new Map<number, number>()
  for (const side of Object.values(box.playerByGameStats ?? {})) {
    for (const p of [...(side.forwards ?? []), ...(side.defense ?? [])]) out.set(p.playerId, (p.goals ?? 0) + (p.assists ?? 0))
    const used = (side.goalies ?? []).filter((p) => (p.toi ?? '00:00') !== '00:00')
    for (const p of used) {
      if (p.decision === 'W' && p.goalsAgainst === 0 && used.length === 1) out.set(p.playerId, 3)
      else if (p.decision === 'W') out.set(p.playerId, 2)
      else if (p.decision === 'O') out.set(p.playerId, 1)
    }
  }
  return out
}

/** Les gardiens qui ont joué dans un match (temps de jeu > 0) ; null si aucun encore */
function goaliesIn(box: { playerByGameStats?: Record<string, BoxSide> }): Set<number> | null {
  const ids = Object.values(box.playerByGameStats ?? {}).flatMap((side) =>
    (side.goalies ?? []).filter((p) => (p.toi ?? '00:00') !== '00:00').map((p) => p.playerId))
  return ids.length ? new Set(ids) : null
}

const periodName = (d?: { number: number; periodType: string }) =>
  d?.periodType === 'OT' || (d?.number ?? 1) > 3 ? 'Prol.' : d?.number === 1 ? '1re' : `${d?.number ?? 1}e`

function goalsOf(g: ScoreGame): Goal[] {
  return (g.goals ?? [])
    .filter((x) => x.periodDescriptor?.periodType !== 'SO')
    .map((x) => ({
      period: periodName(x.periodDescriptor),
      time: x.timeInPeriod ?? '',
      strength: x.strength ?? 'ev',
      team: x.teamAbbrev ?? '',
      scorer: { id: x.playerId, name: x.name?.default ?? '' },
      assists: (x.assists ?? []).map((a) => ({ id: a.playerId, name: a.name?.default ?? '' })),
    }))
}

const getJson = (path: string) =>
  fetch(`${PROXY}/${path}`, { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : Promise.reject(r.status)))

/** Faut-il interroger la LNH ? Un match en cours, ou un match qui commence d'ici 30 min. */
function active(t: Today, live: Map<number, LiveGame>, now: number) {
  return t.games.some((g) => {
    const state = live.get(g.id)?.state ?? g.state
    return state === 'LIVE' || (state === 'FUT' && new Date(g.start).getTime() - now < SOON_MS)
  })
}

/** Interroge le proxy toutes les ~60 s tant qu'un match est en cours ou imminent, onglet visible seulement. */
export function useLive(t: Today | null): Live {
  const [live, setLive] = useState<Live>({ games: new Map(), at: null, status: 'off' })
  const finals = useRef(new Map<number, { points: Map<number, number>; goalies: Set<number> | null }>())
  const gamesRef = useRef(live.games)

  useEffect(() => {
    if (!PROXY || !t || !t.games.length) return
    let timer: number | undefined
    let stopped = false
    let first = true
    // Les matchs où joue au moins un joueur d'une équipe du pool : les autres boxscores sont inutiles
    const ours = new Set(t.teams.flatMap((r) => (r.players ?? []).map((p) => p.game_id)))

    // Le minuteur tourne tant qu'un match n'est pas terminé ; la LNH n'est interrogée que s'il est en cours ou imminent
    const pending = () => t.games.some((g) => (gamesRef.current.get(g.id)?.state ?? g.state) !== 'FINAL')
    const tick = async () => {
      timer = undefined
      if (stopped || document.hidden) return
      // Une première lecture à l'ouverture (pour les matchs déjà terminés), ensuite seulement pendant les matchs
      if (first || active(t, gamesRef.current, Date.now())) {
        first = false
        try {
          const score: { games: ScoreGame[] } = await getJson(`v1/score/${t.date}`)
          const games = new Map<number, LiveGame>()
          for (const g of score.games) {
            if (!t.games.some((x) => x.id === g.id)) continue
            const state = STATES[g.gameState] ?? 'FUT'
            let points = pointsFromGoals(g)
            let goalies: Set<number> | null = null
            // En cours : le boxscore dit quel gardien est devant le filet
            if (state === 'LIVE' && ours.has(g.id)) {
              try {
                goalies = goaliesIn(await getJson(`v1/gamecenter/${g.id}/boxscore`))
              } catch {
                goalies = null
              }
            }
            if (state === 'FINAL' && ours.has(g.id)) {
              if (!finals.current.has(g.id)) {
                const box = await getJson(`v1/gamecenter/${g.id}/boxscore`)
                finals.current.set(g.id, { points: pointsFromBoxscore(box), goalies: goaliesIn(box) })
              }
              ;({ points, goalies } = finals.current.get(g.id)!)
            }
            const score: Record<string, number> = {}
            for (const side of [g.homeTeam, g.awayTeam]) if (side) score[side.abbrev] = side.score ?? 0
            games.set(g.id, { state, left: regulationLeft(g), clock: clockLabel(g), points, goals: goalsOf(g), score, goalies })
          }
          gamesRef.current = games
          if (!stopped) setLive({ games, at: new Date(), status: 'ok' })
        } catch {
          if (!stopped) setLive((l) => ({ ...l, status: 'error' }))
        }
      }
      if (!stopped && pending()) timer = window.setTimeout(tick, POLL_MS)
    }

    const onVisible = () => {
      if (!document.hidden && timer === undefined) tick()
    }
    tick()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      stopped = true
      clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [t])

  return live
}

export const hasProxy = Boolean(PROXY)

/** Feuille de match d'un joueur, d'après le boxscore LNH (patineur ou gardien) */
export type BoxLine = {
  toi?: string
  sog?: number
  plusMinus?: number
  hits?: number
  blockedShots?: number
  shifts?: number
  powerPlayGoals?: number
  faceoffWinningPctg?: number
  saves?: number
  shotsAgainst?: number
  goalsAgainst?: number
  savePctg?: number
  decision?: string
}

export async function fetchBoxLine(gameId: number, nhlId: number): Promise<BoxLine | null> {
  const box: { playerByGameStats?: Record<string, Record<string, ({ playerId: number } & BoxLine)[]>> } =
    await getJson(`v1/gamecenter/${gameId}/boxscore`)
  for (const side of Object.values(box.playerByGameStats ?? {}))
    for (const list of Object.values(side)) for (const p of list) if (p.playerId === nhlId) return p
  return null
}

/** La soirée d'un joueur : réel, attendu, ce qui reste possible et ce qui est perdu */
/** `p1Start` / `p1` : P(1+ pt) avant le match / maintenant (0 à 1, 1 une fois le point acquis) */
export type Night = {
  actual: number; expected: number; left: number; lost: number; state: GameState; clock: string | null
  p1Start: number; p1: number
  /** Gardiens seulement : devant le filet ou pas, pointage, P(victoire), P(blanchissage) */
  goalie?: GoalieNight
}

export function playerNight(p: Pick<TonightPlayer, 'expected' | 'actual' | 'game_id' | 'nhl_id' | 'pos' | 'team'>, t: Today, live: Live): Night {
  const g = p.game_id != null ? live.games.get(p.game_id) : undefined
  const base = t.games.find((x) => x.id === p.game_id)
  // Vieux today.json sans game_id : un `actual` connu veut dire que le match est terminé
  const state: GameState = g?.state ?? base?.state ?? (p.actual != null ? 'FINAL' : 'FUT')
  // Sans direct, un match en cours garde tout son attendu « possible » (on ne sait pas où il en est)
  const leftFrac = g ? g.left : state === 'FINAL' ? 0 : 1
  const actual = g && p.nhl_id != null ? (g.points.get(p.nhl_id) ?? 0) : (p.actual ?? 0)
  const clock = g?.clock ?? null
  // Gardien : ses points viennent du résultat, pas du temps qui passe ; le pointage décide (goalie.ts)
  if (p.pos === 'G' && base) {
    const home = p.team === base.home
    const odds = base.goals ? { for: base.goals[home ? 'home' : 'away'], against: base.goals[home ? 'away' : 'home'] } : null
    const score = { for: g?.score[p.team] ?? 0, against: g?.score[home ? base.away : base.home] ?? 0 }
    // Devant le filet ou pas, une fois le match commencé : on le sait par le boxscore
    const inNet = g?.goalies && p.nhl_id != null ? g.goalies.has(p.nhl_id) : null
    const gn = goalieNight(p.expected, odds, score, state === 'FINAL' ? 0 : leftFrac, inNet)
    const done = state === 'FINAL'
    return {
      actual, expected: gn.expected, left: done ? 0 : gn.left, lost: Math.max(0, gn.expected - actual - (done ? 0 : gn.left)),
      state, clock, p1Start: gn.p1Start, p1: done ? (actual >= 1 ? 1 : 0) : gn.p1, goalie: gn.goalie,
    }
  }
  const left = p.expected * leftFrac
  const p1Start = atLeastOne(0, p.expected)
  return { actual, expected: p.expected, left, lost: Math.max(0, p.expected - actual - left), state, clock, p1Start, p1: atLeastOne(actual, left) }
}

export function sumNights(nights: Night[]) {
  return nights.reduce(
    (s, n) => ({ actual: s.actual + n.actual, expected: s.expected + n.expected, left: s.left + n.left, lost: s.lost + n.lost }),
    { actual: 0, expected: 0, left: 0, lost: 0 },
  )
}

/** La soirée d'une équipe du pool, en direct si possible */
export function teamNight(r: TodayTeam, t: Today, live: Live) {
  // Vieux today.json sans la liste des joueurs : les totaux tels quels
  if (!r.players) {
    const actual = r.actual_tonight ?? 0
    return { actual, expected: r.expected_tonight, left: Math.max(0, r.expected_tonight - actual), lost: 0, started: r.actual_tonight != null }
  }
  const nights = r.players.map((p) => playerNight(p, t, live))
  return { ...sumNights(nights), started: nights.some((n) => n.state !== 'FUT') }
}

/** Projection de la soirée : réel + encore possible (l'attendu avant le premier match) */
export const projection = (n: { actual: number; left: number }) => n.actual + n.left

/** Tirs au but (buts compris, fusillade exclue) d'un joueur par zone, d'après le play-by-play LNH */
export type ShotZones = { hd: number; md: number; ld: number }

type PbpPlay = {
  typeDescKey: string
  timeInPeriod?: string
  periodDescriptor?: { number: number; periodType: string }
  details?: {
    xCoord?: number; yCoord?: number; zoneCode?: string; eventOwnerTeamId?: number
    shootingPlayerId?: number; scoringPlayerId?: number; goalieInNetId?: number
  }
}

/** Présence d'un joueur (shiftcharts LNH) : typeCode 517 ; les 505 sont des buts, ignorés */
type Shift = { playerId: number; teamId: number; period: number; startTime: string; endTime: string; typeCode: number }

/** Tirs au but par zone pendant qu'un joueur est sur la glace : ceux de ses coéquipiers (pas les siens) et contre.
 *  `upTo` : fin de la dernière présence connue du match (« 2e 13:49 ») ; la LNH publie les présences en retard. */
export type OnIce = { for: { shots: ShotZones; goals: ShotZones }; against: { shots: ShotZones; goals: ShotZones }; upTo: string }

/** HD : enclave basse, ≤ 25 pi de la ligne des buts et |y| ≤ 9 ; MD : entre les points de mise au jeu (|y| ≤ 22)
 *  jusqu'au haut des cercles (35 pi) ; LD : tout le reste (points, bandes, derrière le filet, hors zone). */
export function shotZone(d: NonNullable<PbpPlay['details']>): keyof ShotZones {
  if (d.xCoord == null || d.yCoord == null || (d.zoneCode != null && d.zoneCode !== 'O')) return 'ld'
  // Filets à x = ±89 : en zone offensive, le filet attaqué est du côté du signe de x
  const dx = 89 - Math.abs(d.xCoord)
  const dy = Math.abs(d.yCoord)
  if (dx < 0) return 'ld'
  if (dx <= 25 && dy <= 9) return 'hd'
  if (dx <= 35 && dy <= 22) return 'md'
  return 'ld'
}

const seconds = (mmss: string) => Number(mmss.slice(0, 2)) * 60 + Number(mmss.slice(3, 5))
const zeros = (): ShotZones => ({ hd: 0, md: 0, ld: 0 })
const isShot = (e: PbpPlay) =>
  (e.typeDescKey === 'shot-on-goal' || e.typeDescKey === 'goal') && e.periodDescriptor?.periodType !== 'SO' && e.details != null

/** Tirs pour et contre pendant les présences d'un joueur ; null s'il n'a encore aucune présence publiée.
 *  Une présence couvre un tir si début < t ≤ fin : un tir à l'instant même d'un changement compte pour ceux qui
 *  sortent (après un but, la présence se termine à la seconde du but, et la suivante commence à la mise au jeu). */
export function onIceZones(plays: PbpPlay[], shifts: Shift[], nhlId: number): OnIce | null {
  const all = shifts.filter((s) => s.typeCode === 517)
  const mine = all.filter((s) => s.playerId === nhlId)
  if (!mine.length) return null
  const team = mine[0].teamId
  const out: OnIce = { for: { shots: zeros(), goals: zeros() }, against: { shots: zeros(), goals: zeros() }, upTo: '' }
  for (const e of plays) {
    if (!isShot(e) || !e.timeInPeriod || !e.periodDescriptor) continue
    const t = seconds(e.timeInPeriod)
    const n = e.periodDescriptor.number
    if (!mine.some((s) => s.period === n && seconds(s.startTime) < t && t <= seconds(s.endTime))) continue
    // La zone se lit du point de vue du tireur (zoneCode et |x|), donc vaut aussi pour les tirs contre
    const own = e.details!.eventOwnerTeamId === team
    // « Pour » = ses coéquipiers : ses propres tirs sont déjà comptés à part
    if (own && (e.details!.shootingPlayerId ?? e.details!.scoringPlayerId) === nhlId) continue
    const side = own ? out.for : out.against
    const z = shotZone(e.details!)
    side.shots[z]++
    if (e.typeDescKey === 'goal') side.goals[z]++
  }
  const last = all.reduce((a, s) => (s.period > a.period || (s.period === a.period && s.endTime > a.endTime) ? s : a))
  out.upTo = `${periodName({ number: last.period, periodType: last.period > 3 ? 'OT' : 'REGULAR' })} ${last.endTime}`
  return out
}

/** Tirs au but par zone et buts parmi eux : ceux du joueur, ou (gardien) ceux reçus pendant qu'il était devant le filet.
 *  Patineur : aussi les tirs pendant qu'il est sur la glace (`onIce`, null sans présences publiées). */
export async function fetchShotZones(
  gameId: number, nhlId: number, goalie = false,
): Promise<{ shots: ShotZones; goals: ShotZones; onIce: OnIce | null }> {
  const [pbp, shifts] = await Promise.all([
    getJson(`v1/gamecenter/${gameId}/play-by-play`) as Promise<{ plays?: PbpPlay[] }>,
    goalie ? null : (getJson(`stats/rest/en/shiftcharts?cayenneExp=gameId=${gameId}`) as Promise<{ data?: Shift[] }>).catch(() => null),
  ])
  const shots = zeros()
  const goals = zeros()
  for (const e of pbp.plays ?? []) {
    if (!isShot(e)) continue
    const who = goalie ? e.details!.goalieInNetId : (e.details!.shootingPlayerId ?? e.details!.scoringPlayerId)
    if (who !== nhlId) continue
    const z = shotZone(e.details!)
    shots[z]++
    if (e.typeDescKey === 'goal') goals[z]++
  }
  return { shots, goals, onIce: shifts?.data ? onIceZones(pbp.plays ?? [], shifts.data, nhlId) : null }
}
