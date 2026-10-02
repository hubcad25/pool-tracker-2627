# Backtest du rythme ROS

Saisons 2022-23 à 2025-26, coupures après 10, 20, 30, 41, 60 matchs d'équipe, 13378 lignes (joueur × coupure, ≥ 10 matchs joués ensuite). Prior Marcel 5/4/3 pondéré par les GP, âge : × (1 + 0.015 × (27 − âge)).
Hors échantillon : k et w estimés sans la saison évaluée.

Erreur : RMSE du P/GP ROS pondérée par les GP restants. Ordre : % de paires du top 250 (selon le prior) où le meilleur rythme ROS est bien prédit.

## Global

| candidat | RMSE P/GP | ordre |
|---|---|---|
| 1. prior | 0.1699 | 73.6% |
| 2. observé | 0.2163 | 74.2% |
| 3. mélange | 0.1541 | 77.0% |
| 4. mélange + chance | 0.1532 | 77.1% |

## RMSE P/GP par coupure

| candidat | 10 m | 20 m | 30 m | 41 m | 60 m |
|---|---|---|---|---|---|
| 1. prior | 0.1571 | 0.1614 | 0.1692 | 0.1797 | 0.2132 |
| 2. observé | 0.2607 | 0.2102 | 0.1867 | 0.1795 | 0.1980 |
| 3. mélange | 0.1497 | 0.1473 | 0.1505 | 0.1572 | 0.1876 |
| 4. mélange + chance | 0.1487 | 0.1464 | 0.1498 | 0.1562 | 0.1869 |

## Paramètres retenus

| position | k | w | couverture 80 % : ≥ 0 P/GP | ≥ 0.3 P/GP | ≥ 0.5 P/GP | ≥ 0.7 P/GP |
|---|---|---|---|---|---|---|
| F | 25 | 0.3 | 80.3% | 80.1% | 80.3% | 80.1% |
| D | 25 | 0.4 | 80.5% | 80.1% | 80.5% | 81.5% |
