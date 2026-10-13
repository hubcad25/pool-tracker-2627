// La soirée en direct : pointage LNH via le proxy CORS (infra/aws/proxy_lnh.py, VITE_LNH_PROXY).
// Sans proxy (ou s'il ne répond pas), tout se rabat sur today.json : points des matchs FINAL seulement.
import { useEffect, useRef, useState } from 'react'
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
  const finals = useRef(new Map<number, Map<number, number>>())
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
            if (state === 'FINAL' && ours.has(g.id)) {
              if (!finals.current.has(g.id)) finals.current.set(g.id, pointsFromBoxscore(await getJson(`v1/gamecenter/${g.id}/boxscore`)))
              points = finals.current.get(g.id)!
            }
            games.set(g.id, { state, left: regulationLeft(g), clock: clockLabel(g), points, goals: goalsOf(g) })
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
export type Night = { actual: number; expected: number; left: number; lost: number; state: GameState; clock: string | null }

export function playerNight(p: Pick<TonightPlayer, 'expected' | 'actual' | 'game_id' | 'nhl_id'>, t: Today, live: Live): Night {
  const g = p.game_id != null ? live.games.get(p.game_id) : undefined
  const base = t.games.find((x) => x.id === p.game_id)
  // Vieux today.json sans game_id : un `actual` connu veut dire que le match est terminé
  const state: GameState = g?.state ?? base?.state ?? (p.actual != null ? 'FINAL' : 'FUT')
  // Sans direct, un match en cours garde tout son attendu « possible » (on ne sait pas où il en est)
  const leftFrac = g ? g.left : state === 'FINAL' ? 0 : 1
  const actual = g && p.nhl_id != null ? (g.points.get(p.nhl_id) ?? 0) : (p.actual ?? 0)
  const left = p.expected * leftFrac
  return { actual, expected: p.expected, left, lost: Math.max(0, p.expected - actual - left), state, clock: g?.clock ?? null }
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
