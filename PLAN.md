# Pool Tracker 2026-27 — Plan

Suivi en saison de mon équipe dans le pool ESPN « HABS FOR THE CUP » : notifs de blessures/moves
sur Android + dashboard mobile (performance vs projection, indicateurs de chance, projection ROS).

**Principe directeur : zéro slop.** Si je reçois une notif, c'est qu'une décision est en jeu.

## Contexte de la ligue

- ESPN, ligue privée, `leagueId=1213664531`, 12 équipes, format League Manager, « Total Season Points » (G+A)
- Alignement : 10 F, 5 D, 1 G, plus 2 slots IR
- **Moves de FA : 3 pour la saison, 2 utilisés (Boeser, Nichushkin) → il en reste 1**
- Trades : 10 pour la saison → c'est le levier principal
- Bedard et Jarvis occupent les 2 slots IR. À leur activation, je dois dropper un F (gratuit : seule la signature coûte un move)
- Je fais mes moves moi-même dans ESPN → les rosters ESPN sont la source de vérité. L'app suit les rosters, rien de plus.

## Décisions prises

| sujet | décision |
|---|---|
| Repo | `hubcad25/pool-tracker-2627`, **public**, séparé de `fantasy_projections_2627` (qui contient des données payantes) |
| Runner | GitHub Actions, **1 exécution par jour vers midi** (cron `0 16 * * *` UTC, donc 12 h en heure d'été et 11 h l'hiver) |
| Notifs | ntfy (app Android), topic au nom aléatoire, deux topics : `test` et `prod` |
| Dashboard | PWA React/Vite, déployée sur GitHub Pages |
| Langage | Python pour la pipeline **et** le modèle ROS (le même code sert au backtest et en production). R reste correct pour l'exploration et les graphiques. |
| Ids des joueurs | `data/id_map.csv` complétée automatiquement chaque jour (nom + alias, départagé par équipe puis position ; recherche NHL pour les blessés absents des rosters). Corrections à la main dans `data/id_overrides.csv`. Notif si un joueur de la ligue n'a pas d'association |
| Prior du backtest | Marcel seulement, sans correction de l'écart Marcel / consensus. On garde la ROS simple |
| Lien avec le projet de draft | copie unique et figée des distributions préseason + alias de noms dans `priors/`. Aucune dépendance vivante. |

## Sources (vérifiées le 2026-10-02)

| donnée | source | auth |
|---|---|---|
| Statut de blessure, type, date de retour prévue | ESPN `.../seasons/2027/segments/0/leaguedefaults/1?view=kona_playercard` (`injuryStatus`, `injuryDetails.expectedReturnDate`) | aucune |
| Rosters des 12 équipes, FA, transactions | ESPN league API (`leagueId=1213664531`) | cookies `espn_s2` + `SWID` (secrets GitHub) |
| Calendrier (date de retour → matchs manqués), stats de base | NHL API `api-web.nhle.com` | aucune |
| Stats avancées de la saison (ixG, tirs, TOI par situation, on-ice) | MoneyPuck `playerData/seasonSummary/2026/regular/skaters.csv` (mis à jour chaque nuit) | aucune |
| Historique match par match (ixG, G, A, TOI, buts/tirs on-ice) | MoneyPuck `playerData/careers/gameByGame/regular/skaters/{nhl_id}.csv` (2008 → aujourd'hui) | aucune |
| Prior préseason | `fantasy_projections_2627/analysis/output/players_export.json` (copié dans `priors/`) | — |

Écartée : Natural Stat Trick (bloque les scripts, 403).

**Cookies ESPN** : `SWID` ne change pas. `espn_s2` dure en général environ un an, mais une déconnexion ou un
changement de mot de passe peut l'invalider. Si la ligue répond 401, une seule notif
« cookies expirés, remplacer le secret `ESPN_S2` ». Les blessures continuent de fonctionner, puisqu'elles passent par l'endpoint public.

**Le join** : ESPN id ↔ NHL id ↔ id canonique. La table se complète automatiquement à chaque exécution :
une association trouvée ne change plus jamais, et les trous sur les joueurs de la ligue déclenchent une notif
pour une correction à la main (`data/id_overrides.csv`).

**Notes d'API** (vérifiées) : l'endpoint ESPN public exige un tri dès qu'on passe un `limit`
(`sortPercOwned`), sinon `filterIds`. Les rosters NHL `current` omettent les blessés : on se rabat sur
`search.d3.nhle.com`. Les calendriers NHL incluent la préseason (`gameType` 1), donc on filtre sur `gameType == 2`.

## Pipeline quotidienne

```
fetch (ESPN public + ligue, NHL, MoneyPuck)
  → snapshot du jour : data/season/YYYY-MM-DD/{league,injuries}.json (commité ; garde aussi le cron actif)
    MoneyPuck n'est pas snapshotté : ses stats sont cumulatives et l'historique match par match existe déjà
  → calculs : pace, indicateurs de chance, projection ROS
  → diff vs le snapshot précédent → événements → filtre anti-slop → ntfy
  → dashboard.json → déploiement de la PWA
```

## Notifications

Au plus **une notif par exécution** (les événements sont regroupés). Chaque notif a un bouton qui ouvre le dashboard.

**Déclencheurs :**
1. **Statut d'un joueur de mon équipe** (ACTIVE ↔ DTD/OUT/IR/SUSPENSION), avec le nombre de matchs manqués calculé
   à partir du calendrier. Ex. : « Jarvis → IR (épaule), retour ~24 oct, manque 9 matchs ».
2. **Date de retour modifiée** de ≥ 3 matchs pour un de mes joueurs.
3. **Activation possible d'un joueur IR** → suggestion de drop parmi mes F, avec la ROS et l'intervalle.
   Ex. : « Jarvis activable → drop Nichushkin (ROS 31, 22-40) plutôt que Boeser (ROS 36, 27-45) ».
4. **Alerte FA (priorité max, son distinct).** Elle tient compte de la **valeur d'option du dernier move** :
   elle part seulement si le gain ROS dépasse ce qu'on peut espérer garder en réserve pour une future
   blessure grave sur mon équipe. Le seuil baisse à mesure que la saison avance. Attendu : 0 à 2 alertes dans toute l'année.
   Une seule alerte par joueur.
5. **Digest hebdo (lundi)** : buy/sell et idées de trade, en une seule notif.
6. **Santé** : 2 échecs consécutifs ou cookies expirés → une seule notif.

**Jamais :** lignes de stats, « rien de neuf », DTD qui ne fait manquer aucun match, blessure dans une autre équipe
(sauf comme cible de trade, et seulement dans le digest).

Déduplication : un fichier d'état des alertes déjà envoyées, avec la clé (joueur, type d'événement, valeur).

## Modèle ROS — le cœur du projet

**Question** : au jour J, combien de points le joueur fera-t-il d'ici la fin de la saison, avec quelle distribution ?

**Décomposition** : ROS = rythme (P/GP) × GP restants.

**Rythme : candidats à comparer** (on garde le plus simple qui gagne au backtest) :
1. Prior seulement
2. Observé seulement
3. Mélange prior + observé, avec un poids k optimisé selon les matchs joués
4. Le même mélange, avec un observé **ajusté pour la chance** : G remplacés par un mélange ixG / sh% de carrière,
   A pondérées par oiSH% carrière / oiSH% actuel
5. Le modèle 4 plus des signaux de rôle (variation du TOI et du PP TOI vs le prior) : un vrai changement de rôle
   doit faire bouger la projection plus vite que la chance

**GP restants** = matchs restants de l'équipe − matchs manqués pour blessure connue − taux de blessures futures
(calibré sur l'historique).

**Backtest :**
- Saisons 2021-22 à 2025-26. Coupures après 10, 20, 30, 41 et 60 matchs d'équipe. Cible : les points réels du reste de la saison.
- Métriques :
  - erreur sur le P/GP ROS ;
  - **précision de l'ordre** : sur des paires de joueurs du top 250, est-ce qu'on prédit le bon gagnant ? (c'est la décision trade/drop) ;
  - **calibration** : est-ce que l'intervalle 80 % contient la valeur réelle 80 % du temps ?
- Les résidus du backtest donnent la largeur de la distribution ROS. Ça corrige, pour la partie en saison, la sous-estimation
  de l'incertitude par le spread entre sources (limite connue du projet de draft).
- Limite : pas de projections préseason historiques. Dans le backtest, le prior est donc un « Marcel » (3 saisons précédentes
  pondérées + ajustement pour l'âge). En production, le prior est le consensus 2026-27. Le k optimal en production sera peut-être un peu différent.
- À consulter le moment venu (pas avant) : les anciens projets `~/code/hockey/predict_points_season` et `predict_points_dynamic`.

## Dashboard (PWA mobile-first)

- **Mon équipe** : une carte par joueur.
  - Points et GP, pace sur 82 matchs, situé dans sa bande préseason p10-p50-p90, et sa projection ROS avec l'intervalle.
  - Indicateurs : sh% vs moyenne sur 3 ans, G − ixG, oiSH% vs carrière, PDO, TOI et PP TOI vs l'an passé.
  - Verdict : *Chanceux / Malchanceux / Rôle ↑ / Rôle ↓ / Conforme*, avec « échantillon trop petit » avant ~10 matchs.
- **Blessures** : mes joueurs blessés (date de retour, matchs manqués), plus les blessures notables dans la ligue.
- **FA** : meilleurs agents libres selon la ROS, comparés à mon pire joueur, avec le seuil de valeur d'option.
- **Ligue** : points actuels + ROS par équipe, simulation du classement final (probabilité de finir 1er).
- **Trades** : voir la phase 4.

**Logique des trades** : dans une ligue « total points », un échange n'aide les deux équipes que si les poolers évaluent
les joueurs différemment. On achète les joueurs dont les points actuels sous-estiment la ROS (malchanceux, rôle stable)
et on vend l'inverse. La perception des autres poolers est approximée par les points actuels et le rang ESPN.

## Tests

1. **Tests unitaires du moteur de règles** (pytest) : des scénarios « snapshot d'hier / snapshot d'aujourd'hui » avec le message attendu.
   Chaque règle anti-slop a son test « ne doit **pas** notifier ».
2. **Dry-run** : la pipeline imprime les notifs qu'elle aurait envoyées, sans rien envoyer
   (testable avec `espn_injuries_2026-10-01.csv` du projet de draft comme « hier »).
3. **`workflow_dispatch`** (lançable depuis l'app GitHub sur le cell) : choix de la cible `test`/`prod` et injection
   d'un scénario fictif (« Bedard activable », « FA à fort gain ») pour voir la vraie notif sur Android.
4. **Mode shadow les 2 premières semaines** : la job tourne en vrai, envoie sur `test` et note chaque notif dans un journal
   sur le dashboard. Je note chacune « utile / slop », on ajuste les seuils, puis on passe sur `prod`.
5. **Monitoring** : courriel GitHub quand la job échoue, plus une notif ntfy après 2 échecs consécutifs.

## Structure

```
priors/          distributions préseason + alias (copiés, figés)
pipeline/        collecteurs ESPN / NHL / MoneyPuck, moteur de règles, ntfy
model/           modèle ROS (le même code pour le backtest et la production)
backtest/        cache MoneyPuck historique + rapports de validation
data/season/     snapshots quotidiens (commités par la job)
app/             PWA React/Vite
tests/           scénarios de notifs
.github/workflows/daily.yml
```

## Phases

0. **Setup** : repo GitHub public, secrets (`ESPN_S2`, `SWID`, `NTFY_TOPIC_TEST`, `NTFY_TOPIC_PROD`), test de l'API de la ligue,
   table de correspondance des ids, copie des priors. Installer ntfy sur Android.
1. **Blessures et rosters en mode shadow** : notifs de statut et d'activation (suggestion de drop basée sur le prior en attendant la ROS).
2. **Modèle ROS + backtest.** La phase la plus importante, peut se faire en parallèle de la phase 1 (elle ne dépend que de MoneyPuck).
3. **Dashboard** : mon équipe, blessures, FA, ligue.
4. **Alertes FA avec valeur d'option, et digest hebdo buy/sell / trades.**

## État

2026-10-02 : plan rédigé. Phase 0 en place : structure du repo, collecteurs ESPN / NHL / MoneyPuck,
priors copiés, table d'ids (les 192 joueurs repêchés sont tous associés), ntfy avec déduplication et dry-run,
compteur d'échecs, workflow quotidien, tests (pytest + ruff).
Repo, secrets et ntfy en place. `fetch_league` validé sur la vraie ligue : slots 3=F, 4=D, 5=G, 8=IR ;
l'API de la ligue n'a pas la date de retour, on la prend de l'endpoint public. Phase 1 codée : `pipeline/rules.py` (statut, date de retour, activation IR avec drop selon la ROS du prior),
29 tests. Scénarios fictifs : `--scenario activation|status` ou `workflow_dispatch`. Mode shadow sur `test`
(notif fictive reçue sur le cell le 2026-10-02). Passer `PIPELINE_TARGET=prod` vers le 16 octobre si le shadow est concluant.

**Prochaine étape : phase 2 (modèle ROS + backtest).** Points de départ :
- Le code va dans `model/` (le même en backtest et en prod) et `backtest/`. Le cache MoneyPuck historique va dans
  `backtest/cache/` (gitignoré).
- Le prior du backtest est Marcel seulement, sans correction vers le consensus. On garde le plus simple qui gagne.
- En production, la ROS remplacera `rules.ros()` (aujourd'hui le prior seul), utilisée par la suggestion de drop.
- Les ids MoneyPuck sont des ids NHL : passer par `data/id_map.csv` (`ids.resolved`).
- Les anciens projets `~/code/hockey/predict_points_season` et `predict_points_dynamic` sont à consulter au début de la phase.
