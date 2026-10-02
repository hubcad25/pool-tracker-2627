"""Envoi ntfy : au plus une notif par exécution, sans renvoyer une clé déjà envoyée."""
import json

import requests

from pipeline import config
from pipeline.events import Event

SENT = config.STATE_DIR / "sent.json"


def load_sent() -> set[str]:
    return set(json.loads(SENT.read_text())) if SENT.exists() else set()


def save_sent(keys: set[str]) -> None:
    SENT.parent.mkdir(parents=True, exist_ok=True)
    SENT.write_text(json.dumps(sorted(keys), indent=1) + "\n")


def forget(prefix: str) -> None:
    """Réarme une alerte de santé une fois le problème réglé (ex. cookies remplacés)."""
    sent = load_sent()
    if any(k.startswith(prefix) for k in sent):
        save_sent({k for k in sent if not k.startswith(prefix)})


def compose(events: list[Event]) -> dict | None:
    if not events:
        return None
    events = sorted(events, key=lambda e: -e.priority)
    title = events[0].message.split(" : ")[0] if len(events) == 1 else f"Pool : {len(events)} événements"
    return {
        "title": title[:80],
        "message": "\n".join(f"• {e.message}" for e in events),
        "priority": events[0].priority,
        "click": config.DASHBOARD_URL,
        "actions": [{"action": "view", "label": "Dashboard", "url": config.DASHBOARD_URL}],
    }


def send(events: list[Event], *, target: str = "test", dry_run: bool = True) -> dict | None:
    """Filtre les événements déjà envoyés, regroupe le reste en une notif et l'envoie (ou l'imprime)."""
    sent = load_sent()
    new = [e for e in events if e.key not in sent]
    payload = compose(new)
    if payload is None:
        return None
    if dry_run:
        print(f"[dry-run → {target}]\n{json.dumps(payload, ensure_ascii=False, indent=2)}")
        return payload
    topic = config.env(f"NTFY_TOPIC_{target.upper()}")
    if not topic:
        raise RuntimeError(f"NTFY_TOPIC_{target.upper()} manquant")
    requests.post("https://ntfy.sh/", json={"topic": topic, **payload}, timeout=30).raise_for_status()
    save_sent(sent | {e.key for e in new})
    return payload
