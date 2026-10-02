"""Correspondance ESPN id ↔ NHL id ↔ id canonique (celui des priors).

data/id_map.csv est complétée automatiquement chaque jour (nom normalisé + alias, départagé par
équipe puis position). data/id_overrides.csv contient les corrections manuelles et a toujours priorité.
Un joueur d'une équipe de la ligue sans nhl_id ou sans canonical_id est signalé pour correction à la main.
"""
import csv
import json
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from pipeline import config

ID_MAP = config.ROOT / "data" / "id_map.csv"
OVERRIDES = config.ROOT / "data" / "id_overrides.csv"
FIELDS = ["espn_id", "nhl_id", "canonical_id", "name", "method"]

SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}
# Abréviations ESPN qui diffèrent de celles de la LNH
ESPN_TO_NHL_TEAM = {"NJ": "NJD", "LA": "LAK", "SJ": "SJS", "TB": "TBL"}


def normalize_name(name: str) -> str:
    """Même normalisation que le projet de draft, pour retrouver ses player_id."""
    if not name:
        return ""
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name.strip()).strip()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c)).lower()
    name = name.replace(".", "").replace("'", "").replace("-", " ")
    return " ".join(t for t in name.split() if t not in SUFFIXES)


def pos_group(pos: str | None) -> str:
    pos = (pos or "").upper()
    return "G" if pos.startswith("G") else "D" if pos.startswith("D") else "F"


# Homonymes réels : le défenseur reçoit le suffixe _(d) dans les priors
COLLISIONS = {"elias pettersson", "sebastian aho"}


def load_aliases(path: Path = config.PRIORS_DIR / "name_aliases.csv") -> dict[str, str]:
    if not path.exists():
        return {}
    with open(path, newline="") as f:
        return {normalize_name(r["alias_name"]): normalize_name(r["canonical_name"]) for r in csv.DictReader(f)}


def name_key(name: str, aliases: dict[str, str]) -> str:
    norm = normalize_name(name)
    return aliases.get(norm, norm)


def canonical_id(name: str, pos: str, aliases: dict[str, str], prior_ids: set[str]) -> str | None:
    key = name_key(name, aliases)
    candidates = [key.replace(" ", "_")]
    if key in COLLISIONS and pos_group(pos) == "D":
        candidates.insert(0, f"{candidates[0]}_(d)")
    if pos_group(pos) == "G":
        candidates.insert(0, f"{candidates[0]}_(g)")
    return next((c for c in candidates if c in prior_ids), None)


def match_nhl(player: dict, nhl_by_key: dict[str, list[dict]], aliases: dict[str, str]) -> tuple[int | None, str]:
    """Retourne (nhl_id, méthode). nhl_id est None si aucun candidat ou si l'ambiguïté persiste."""
    cands = nhl_by_key.get(name_key(player["name"], aliases), [])
    if len(cands) == 1:
        return cands[0]["nhl_id"], "name"
    if not cands:
        return None, "unmatched"
    team = ESPN_TO_NHL_TEAM.get(player["pro_team"], player["pro_team"])
    for method, keep in (("name+team", lambda c: c["team"] == team),
                         ("name+pos", lambda c: pos_group(c["pos"]) == pos_group(player["pos"]))):
        narrowed = [c for c in cands if keep(c)]
        if len(narrowed) == 1:
            return narrowed[0]["nhl_id"], method
        cands = narrowed or cands
    return None, "ambiguous"


def read_map(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    with open(path, newline="") as f:
        return {int(r["espn_id"]): r for r in csv.DictReader(f)}


def write_map(rows: dict[int, dict]) -> None:
    with open(ID_MAP, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for espn_id in sorted(rows):
            w.writerow({k: rows[espn_id].get(k, "") for k in FIELDS})


def load_prior_ids(path: Path = config.PRIORS_DIR / "priors.json") -> set[str]:
    if not path.exists():
        return set()
    return {p["player_id"] for p in json.loads(path.read_text())}


def update_map(espn_players: list[dict], nhl_players: list[dict],
               search: Callable[[str], list[dict]] | None = None,
               worth_search: Callable[[dict], bool] = lambda p: False) -> dict[int, dict]:
    """Ajoute les joueurs ESPN inconnus et réessaie ceux qui n'ont pas encore été associés.

    Les rosters `current` de la LNH omettent les blessés : pour les joueurs qui comptent (`worth_search`),
    on se rabat sur la recherche par nom. Les lignes déjà associées ne sont jamais modifiées.
    """
    aliases = load_aliases()
    prior_ids = load_prior_ids()
    nhl_by_key: dict[str, list[dict]] = {}
    for p in nhl_players:
        nhl_by_key.setdefault(name_key(p["name"], aliases), []).append(p)

    rows = read_map(ID_MAP)
    for p in espn_players:
        row = rows.get(p["espn_id"], {"espn_id": p["espn_id"], "name": p["name"]})
        if not row.get("nhl_id"):
            nhl_id, method = match_nhl(p, nhl_by_key, aliases)
            if nhl_id is None and search and worth_search(p):
                found = {}
                for c in search(p["name"]):
                    found.setdefault(name_key(c["name"], aliases), []).append(c)
                nhl_id, method = match_nhl(p, found, aliases)
                method = f"search:{method}"
            row["nhl_id"], row["method"] = str(nhl_id or ""), method
        if not row.get("canonical_id"):
            row["canonical_id"] = canonical_id(p["name"], p["pos"], aliases, prior_ids) or ""
        rows[p["espn_id"]] = row
    write_map(rows)
    return resolved(rows)


def resolved(rows: dict[int, dict]) -> dict[int, dict]:
    """La table auto avec les corrections manuelles appliquées par-dessus."""
    out = {k: dict(v) for k, v in rows.items()}
    for espn_id, o in read_map(OVERRIDES).items():
        base = out.setdefault(espn_id, {"espn_id": espn_id, "name": o.get("name", "")})
        for field in ("nhl_id", "canonical_id"):
            if o.get(field):
                base[field] = o[field]
        base["method"] = "manual"
    return out


def missing(id_map: dict[int, dict], players: list[dict]) -> list[dict]:
    """Joueurs (de la ligue) dont un id manque. Les gardiens n'ont pas de prior : seul nhl_id compte."""
    out = []
    for p in players:
        row = id_map.get(p["espn_id"], {})
        fields = ["nhl_id"] + ([] if p["pos"] == "G" else ["canonical_id"])
        gaps = [f for f in fields if not row.get(f)]
        if gaps:
            out.append({**p, "missing": gaps})
    return out
