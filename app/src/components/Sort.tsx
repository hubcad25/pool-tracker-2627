import { useState } from 'react'

export type Dir = 'asc' | 'desc'
export type SortState<K extends string> = { key: K; dir: Dir }
export type SortOption<K extends string> = { key: K; label: string; dir: Dir }

/** Tri d'une liste, mémorisé par liste dans localStorage (absent, bloqué ou corrompu : tri par défaut). */
export function useSort<K extends string>(id: string, options: SortOption<K>[]) {
  const storageKey = `tri:${id}`
  const [sort, setSort] = useState<SortState<K>>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) ?? 'null')
      if (saved && options.some((o) => o.key === saved.key) && (saved.dir === 'asc' || saved.dir === 'desc')) return saved
    } catch {
      // stockage indisponible
    }
    return { key: options[0].key, dir: options[0].dir }
  })
  const choose = (key: K) => {
    const next: SortState<K> =
      key === sort.key ? { key, dir: sort.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: options.find((o) => o.key === key)!.dir }
    setSort(next)
    try {
      localStorage.setItem(storageKey, JSON.stringify(next))
    } catch {
      // stockage indisponible : le tri vaut pour cette visite
    }
  }
  return [sort, choose] as const
}

/** Trie une copie. `value` : la clé de tri d'un élément ; null va toujours à la fin. */
export function sortBy<T, K extends string>(items: T[], sort: SortState<K>, value: (item: T, key: K) => number | string | null) {
  const sign = sort.dir === 'asc' ? 1 : -1
  return [...items].sort((a, b) => {
    const x = value(a, sort.key)
    const y = value(b, sort.key)
    if (x == null || y == null) return x == null ? (y == null ? 0 : 1) : -1
    if (typeof x === 'string' || typeof y === 'string') return sign * String(x).localeCompare(String(y), 'fr')
    return sign * (x - y)
  })
}

/** « Trier : [ROS ↓] [Pts] [Nom] » : toucher l'option active inverse le sens. */
export function SortBar<K extends string>({
  options,
  sort,
  onChange,
}: {
  options: SortOption<K>[]
  sort: SortState<K>
  onChange: (key: K) => void
}) {
  return (
    <div className="sortbar" role="group" aria-label="Trier">
      <span className="sortbar-label">Trier</span>
      {options.map((o) => {
        const active = o.key === sort.key
        return (
          <button
            key={o.key}
            type="button"
            className={`sortbar-opt${active ? ' is-active' : ''}`}
            aria-pressed={active}
            onClick={() => onChange(o.key)}
          >
            {o.label}
            {active && <span aria-label={sort.dir === 'asc' ? 'croissant' : 'décroissant'}>{sort.dir === 'asc' ? ' ↑' : ' ↓'}</span>}
          </button>
        )
      })}
    </div>
  )
}
