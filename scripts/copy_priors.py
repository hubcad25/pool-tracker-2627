"""Copie unique et figée des distributions préseason depuis fantasy_projections_2627.

On garde seulement la distribution agrégée (quantiles, moyenne, histogramme). Les champs propres à une
source (athletic_edge, eh_edge, ...) ne sont pas copiés.

Usage : uv run python scripts/copy_priors.py [chemin/vers/fantasy_projections_2627]
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEEP = ["player_id", "player_name", "position", "team", "n_sources",
        "q5", "q10", "q25", "sim_median", "q75", "q90", "q95", "sim_mean", "sim_sd",
        "bin_min", "bin_max", "bins"]

src = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "fantasy_projections_2627")
players = json.loads((src / "analysis/output/players_export.json").read_text())
priors = [{k: p[k] for k in KEEP if k in p} for p in players]

out = ROOT / "priors"
out.mkdir(exist_ok=True)
lines = ",\n".join(json.dumps(p, ensure_ascii=False) for p in priors)
(out / "priors.json").write_text(f"[\n{lines}\n]\n")
shutil.copy(src / "data/name_aliases.csv", out / "name_aliases.csv")
print(f"{len(priors)} joueurs copiés dans {out}")
