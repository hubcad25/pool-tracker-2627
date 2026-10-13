# pool-tracker-2627

Projet personnel et ludique : suivi en saison de mon équipe (team_id 5, « hubcad25 ») dans le pool ESPN
« HABS FOR THE CUP ». **Lire `PLAN.md` en premier** : contexte de la ligue, décisions, phases, état d'avancement.

Principe : zéro slop dans les notifs, et garder les choses simples (en particulier le modèle ROS).

## Commandes

```sh
uv run pytest -q && uv run ruff check .
uv run python -m pipeline.main                         # dry-run local (lit .env : cookies ESPN + topics ntfy)
uv run python -m pipeline.main --scenario activation   # notif fictive, n'écrit aucun état
gh workflow run daily.yml -R hubcad25/pool-tracker-2627 -f target=test -f send=true -f scenario=aucun
uv run python -m pipeline.soiree                       # dry-run de la notif de soirée due maintenant
uv run python -m pipeline.soiree --moment fin --day 2026-10-10   # force avant|soir|fin (n'écrit aucun état)
```

## Conventions

- Python 3.13 + uv. Code, commentaires, messages de notif et noms de tests en français.
- Chaque règle de notif a ses tests « doit notifier » **et** « ne doit pas notifier » (`tests/test_rules.py`).
- Les sources passent par `pipeline/http.py` (retries, `AuthError` sur 401/403 avec cookies).
- Date du jour : `config.today()` (heure de Montréal ; le runner est en UTC).
- `priors/` est figé. `data/` est écrit par la job quotidienne (snapshots, id_map, state) : faire `git pull --rebase` avant de pousser.

## Pièges connus

- Push : la clé SSH est refusée, le remote est en HTTPS → `git -c credential.helper='!gh auth git-credential' push`.
- Cookies ESPN (`espn_s2`, `SWID`) : c'est l'utilisateur qui les copie lui-même (dans `.env` et dans les secrets GitHub).
  Ne pas tenter de les extraire du navigateur.
- ESPN public : un `limit` exige un tri (`sortPercOwned`). L'API de la ligue n'a pas `injuryDetails` → on fusionne
  avec l'endpoint public (`espn.fetch_league`). Slots du roster : 3=F, 4=D, 5=G, 8=IR.
- NHL : les rosters `current` omettent les blessés (on se rabat sur `search.d3.nhle.com`). Calendriers : `gameType == 2`.
- Cron GitHub peu fiable (saute des heures) : `soiree.yml` est surtout lancé aux 15 min par la Lambda AWS
  `pool-soiree` (`infra/aws/declencheur.py`, EventBridge Scheduler, compte de la startup, ca-central-1, tag
  `projet=pool-tracker-2627`). Jeton GitHub fine-grained (Actions read/write) dans ses variables d'env.
- Abréviations ESPN ≠ NHL (NJ, LA, SJ, TB) : `ids.ESPN_TO_NHL_TEAM`.
