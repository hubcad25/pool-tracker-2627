import { useState, type ReactNode } from 'react'

const KEY = 'groupes-replies'

function readClosed(): string[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]')
  } catch {
    return []
  }
}

/** Un module repliable (titre + contenu). Ouvert par défaut ; ce qu'on replie le reste d'une visite à l'autre. */
export default function Group({ id, title, children }: { id: string; title: ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(() => !readClosed().includes(id))
  const onToggle = (e: React.SyntheticEvent<HTMLDetailsElement>) => {
    const now = e.currentTarget.open
    setOpen(now)
    try {
      const closed = readClosed().filter((x) => x !== id)
      localStorage.setItem(KEY, JSON.stringify(now ? closed : [...closed, id]))
    } catch {
      // Stockage indisponible (navigation privée) : le module se rouvrira au prochain chargement
    }
  }
  return (
    <details className="group" open={open} onToggle={onToggle}>
      <summary className="group-title">{title}</summary>
      {open && children}
    </details>
  )
}
