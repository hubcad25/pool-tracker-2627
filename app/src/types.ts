// Miroir de pipeline/dashboard.py

export type Range = { p10: number; p50: number; p90: number }
export type Interval = { mean: number; p10: number; p90: number }

export type Verdict = 'malchanceux' | 'chanceux' | 'conforme' | 'petit_echantillon'

export type Injury = {
  status: string
  type: string | null
  expected_return: string | null
  out_for_season: boolean
  games_missed: number | null
}

export type Luck = {
  expected_points: number
  sh: number | null
  sh_career: number | null
  g_minus_ixg: number
  oish: number | null
  oish_career: number | null
  toi: number | null
}

export type Player = {
  espn_id: number
  name: string
  pos: string
  group: 'F' | 'D' | 'G'
  team: string
  slot: 'F' | 'D' | 'G' | 'IR'
  injury: Injury | null
  gp: number
  g: number
  a: number
  points: number
  pace: number | null
  prior: Range | null
  ros: (Interval & { games_left: number }) | null
  final: Interval | null
  luck: Luck | null
  verdict: Verdict | null
}

export type Alert = { kind: string; message: string; priority: number }

export type LeagueInjury = Injury & {
  espn_id: number
  name: string
  pos: string
  team: string
  owner: string | null
  mine: boolean
  ros: Interval | null
}

export type FreeAgent = {
  espn_id: number
  name: string
  pos: string
  team: string
  status: string
  expected_return: string | null
  games_missed: number | null
  pct_owned: number | null
  ros: Interval
  gain: number | null
}

export type FreeAgents = {
  moves_left: number | null
  worst: Partial<Record<'F' | 'D', { espn_id: number; name: string; ros: Interval }>>
  players: Record<'F' | 'D', FreeAgent[]>
}

export type Standing = {
  team_id: number
  abbrev: string | null
  name: string | null
  mine: boolean
  points: number
  ros: number
  final: number
  p10: number
  p90: number
  p_first: number
}

export type Dashboard = {
  day: string
  team: { id: number; name: string | null } | null
  alerts: Alert[]
  players: Player[]
  injuries?: LeagueInjury[]
  free_agents?: FreeAgents | null
  standings?: Standing[]
}
