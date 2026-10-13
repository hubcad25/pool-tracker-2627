// Logo d'une équipe de la LNH, servi par le CDN de la LNH (version claire ou sombre selon le thème du système).
// Les abréviations ESPN diffèrent de celles de la LNH pour quatre équipes (même table que ids.ESPN_TO_NHL_TEAM).
const ESPN_TO_NHL: Record<string, string> = { NJ: 'NJD', LA: 'LAK', SJ: 'SJS', TB: 'TBL' }

const url = (code: string, theme: 'light' | 'dark') => `https://assets.nhle.com/logos/nhl/svg/${code}_${theme}.svg`

export default function TeamLogo({ team }: { team: string }) {
  const code = ESPN_TO_NHL[team] ?? team
  return (
    <picture className="team-logo">
      <source srcSet={url(code, 'dark')} media="(prefers-color-scheme: dark)" />
      <img src={url(code, 'light')} alt={code} title={code} loading="lazy" />
    </picture>
  )
}
