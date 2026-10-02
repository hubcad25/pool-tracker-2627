# ADR 0001 — Pas de signal de rôle (TOI, PP, DailyFaceoff) dans la ROS

- Statut : accepté
- Date : 2026-10-02

## Contexte

La ROS (`model/ros.py`) mélange un prior et la production de la saison, ajustée pour la chance (candidat 4 du
backtest). Un changement de rôle (promotion au premier trio, entrée au PP1) devrait faire bouger la projection plus
vite que k ne le permet. Deux options :

- **Rôle observé** : le TOI hors PP et le TOI en PP de la saison (MoneyPuck), comparés à l'an passé.
- **Rôle anticipé** : les trios et les unités de PP de DailyFaceoff (une page par équipe, lisible par script),
  convertis en TOI attendu (F1 ≈ 16,5 min hors PP, PP1 ≈ 2,9 min PP, etc.), pour voir un changement avant
  qu'il paraisse dans les stats.

## Ce qu'on a testé

Backtest 2022-23 à 2025-26, hors échantillon (une saison de côté). Prior ajusté :
prior + b_ev × ΔTOI hors PP + b_pp × ΔTOI PP (minutes par match, par rapport à l'an passé), b choisis par le backtest.

| candidat | RMSE P/GP | bon ordre (paires du top 250) |
|---|---|---|
| 4. mélange + chance (retenu) | 0,1527 | 77,1 % |
| 5. + rôle observé, saison | 0,1516 | 77,2 % |
| 5b. + rôle récent, 5 derniers matchs | 0,1515 | 77,3 % |
| 6. + rôle parfait : vrai TOI du reste de la saison | 0,1370 | 79,6 % |

Le 5b sert de substitut historique à DailyFaceoff, dont les trios reflètent surtout le dernier match et les pratiques.
On n'a pas d'historique des trios DailyFaceoff.

## Décision

- On garde le candidat 4. Aucun signal de rôle dans la ROS.
- DailyFaceoff est retiré du pipeline (collecteur, snapshot, alerte de panne). Le code est dans l'historique git
  (session du 2026-10-02, jamais commité dans `main`).
- Les candidats 5, 5b et 6 restent dans `backtest/run.py` et `backtest/report.md` pour la trace.

## Pourquoi

- **Le rôle compte, mais c'est le rôle futur qui compte.** Connaître le vrai TOI du reste de la saison réduirait
  l'erreur de 10 % (b stables : ~0,12 P/GP par minute de PP, ~0,05 par minute hors PP). Le rôle actuel, lui,
  n'apporte que 0,7 % : les points et les ixG le reflètent déjà.
- **Le gain du plafond vient de changements qu'aucune source ne voit d'avance** : la blessure d'un coéquipier, un
  trade, un remaniement. Il est aussi gonflé par la causalité inverse (un joueur chaud reçoit plus de minutes).
- **DailyFaceoff ≈ rôle récent** : il ne voit qu'un jour ou deux d'avance. Le 5b montre que ça ne vaut presque
  rien, pour une source fragile de plus (blocage, changement de page).
- **Biais en prod** : le consensus préseason intègre déjà les changements de rôle de l'été. Un Δ mesuré par
  rapport à l'an passé les compterait deux fois.

## Conséquences

- Un vrai changement de rôle passe par les points et les ixG, au rythme de k (moitié du chemin à ~25 matchs).
- La piste « sh% attendu des coéquipiers selon les trios DailyFaceoff » (`PLAN.md`) demanderait de remettre
  DailyFaceoff. À n'envisager que si un backtest sur les trios historiques de MoneyPuck montre un gain net.
- À revoir si une source permet d'anticiper les changements de rôle *futurs* (et pas seulement le dernier
  alignement), ou si le dashboard veut afficher les trios (affichage seulement, hors ROS).
