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
  // v2 (absents des vieux dashboards)
  net_points?: number | null
  goals?: LuckGoals | null
  assists?: LuckAssists | null
}

/** Finition : ses buts vs attendu sur ses tirs. percentile 0,5 = normal, 0,9 = plus chanceux que 90 % des cas */
export type LuckGoals = {
  obs: number
  expected: number
  shots: number
  sh_obs: number | null
  sh_expected: number | null
  percentile: number | null
}

/** Passes : buts des coéquipiers quand il est sur la glace vs attendu */
export type LuckAssists = {
  obs_goals: number
  expected_goals: number
  shots: number
  sh_obs: number | null
  sh_expected: number | null
  percentile: number | null
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
  // Gardiens : points de pool = 2 W + OTL + SO
  w?: number
  otl?: number
  so?: number
  pace: number | null
  prior: Range | null
  ros: (Interval & { games_left: number }) | null
  // Préseason ramenée aux matchs restants (v2)
  ros_prior?: Range | null
  final: Interval | null
  luck: Luck | null
  verdict: Verdict | null
}

export type Alert = { kind: string; message: string; priority: number }

/** Saison d'un joueur hors de mon équipe (FA, blessés) : absent des vieux dashboards */
export type Season = {
  gp?: number
  points?: number
  luck?: Luck | null
  verdict?: Verdict | null
}

export type LeagueInjury = Injury & Season & {
  espn_id: number
  name: string
  pos: string
  team: string
  owner: string | null
  mine: boolean
  ros: Interval | null
}

export type FreeAgent = Season & {
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
  // P(sa ROS > celle de mon pire joueur à sa position)
  p_better?: number | null
}

export type FreeAgents = {
  moves_left: number | null
  worst: Partial<Record<'F' | 'D' | 'G', { espn_id: number; name: string; ros: Interval }>>
  // G absent des dashboards écrits avant l'ajout des gardiens
  players: Record<'F' | 'D', FreeAgent[]> & { G?: FreeAgent[] }
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
  // Intervalle de la ROS (v2)
  ros_p10?: number | null
  ros_p90?: number | null
  delta_p_first_per_point?: number | null
  // Chance de la saison : somme des net_points des patineurs de l'alignement (positif = chanceuse)
  luck_points?: number | null
}

export type GameState = 'FUT' | 'LIVE' | 'FINAL'

export type TodayTeam = {
  team_id: number
  abbrev: string | null
  name: string | null
  mine: boolean
  points: number
  p_first: number | null
  expected_tonight: number
  actual_tonight: number | null
  playing_tonight: number
  delta_p_first_per_point?: number | null
  // Total final projeté le matin et son écart-type (absents des vieux today.json) : P(1er) en direct
  final?: number | null
  sd?: number | null
  // Joueurs de l'alignement qui jouent ce soir (absent des vieux today.json)
  players?: TonightPlayer[]
}

export type TonightPlayer = {
  espn_id: number
  nhl_id?: number | null
  game_id?: number
  name: string
  pos: string | null
  team: string
  opp: string
  start: string
  expected: number
  actual: number | null
}

export type Today = {
  date: string
  updated: string
  games: { id: number; start: string; home: string; away: string; state: GameState }[]
  p_first: { now: number | null; yesterday: number | null; history: { day: string; p_first: number }[] } | null
  teams: TodayTeam[]
  my_players: (TonightPlayer & { injury: string | null })[]
  watch: (TonightPlayer & {
    owner: { team_id: number; abbrev: string | null; name: string | null }
    delta_p_first_per_point: number | null
    threat: number | null
  })[]
}

export type Dashboard = {
  day: string
  team: { id: number; name: string | null } | null
  alerts: Alert[]
  players: Player[]
  // Les cartes de chaque équipe du pool (clé : team_id en texte), moi compris
  teams_players?: Record<string, Player[]>
  injuries?: LeagueInjury[]
  free_agents?: FreeAgents | null
  standings?: Standing[]
  // Écrit à part dans data/today.json (servi à côté) ; gardé ici au cas où
  today?: Today | null
}
