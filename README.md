# pool-tracker-2627

Suivi en saison de mon équipe dans le pool ESPN « HABS FOR THE CUP » : notifs ntfy et dashboard mobile.
Le plan complet est dans [PLAN.md](PLAN.md).

## Local

```sh
uv sync
cp .env.example .env              # ESPN_S2, SWID, topics ntfy
uv run pytest
uv run python -m pipeline.main    # dry-run : imprime la notif sans l'envoyer
uv run python -m pipeline.main --send --target test
```

## Ids des joueurs

`data/id_map.csv` (ESPN ↔ NHL ↔ id des priors) se complète tout seul chaque jour. Quand un joueur d'une équipe
de la ligue n'a pas d'association, une notif le signale. Il faut alors ajouter une ligne dans `data/id_overrides.csv`
(seules les colonnes remplies écrasent la table auto), puis commiter.

## Priors

`priors/` est une copie figée des distributions préseason de `fantasy_projections_2627`
(`uv run python scripts/copy_priors.py`). On ne recopie pas en cours de saison.
