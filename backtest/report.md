# Backtest du rythme ROS

Saisons 2022-23 à 2025-26, coupures après 10, 20, 30, 41, 60 matchs d'équipe, 13378 lignes (joueur × coupure, ≥ 10 matchs joués ensuite). Prior Marcel 5/4/3 pondéré par les GP, âge : × (1 + 0.015 × (27 − âge)).
Hors échantillon : k, w et m estimés sans la saison évaluée.

Erreur : RMSE du P/GP ROS pondérée par les GP restants. Ordre : % de paires du top 250 (selon le prior) où le meilleur rythme ROS est bien prédit.

## Global

| candidat | RMSE P/GP | ordre |
|---|---|---|
| 1. prior | 0.1699 | 73.6% |
| 2. observé | 0.2163 | 74.2% |
| 3. mélange | 0.1541 | 77.0% |
| 4. mélange + chance | 0.1527 | 77.1% |
| 5. + rôle observé (saison) | 0.1516 | 77.2% |
| 5b. + rôle récent (5 derniers matchs) | 0.1515 | 77.3% |
| 6. + rôle parfait (plafond) | 0.1370 | 79.6% |

## RMSE P/GP par coupure

| candidat | 10 m | 20 m | 30 m | 41 m | 60 m |
|---|---|---|---|---|---|
| 1. prior | 0.1571 | 0.1614 | 0.1692 | 0.1797 | 0.2132 |
| 2. observé | 0.2607 | 0.2102 | 0.1867 | 0.1795 | 0.1980 |
| 3. mélange | 0.1497 | 0.1473 | 0.1505 | 0.1572 | 0.1876 |
| 4. mélange + chance | 0.1483 | 0.1459 | 0.1493 | 0.1554 | 0.1863 |
| 5. + rôle observé (saison) | 0.1475 | 0.1447 | 0.1482 | 0.1539 | 0.1852 |
| 5b. + rôle récent (5 derniers matchs) | 0.1478 | 0.1448 | 0.1476 | 0.1536 | 0.1846 |
| 6. + rôle parfait (plafond) | 0.1281 | 0.1298 | 0.1350 | 0.1426 | 0.1758 |

## Paramètres retenus

| position | k | w | m | couverture 80 % : ≥ 0 P/GP | ≥ 0.3 P/GP | ≥ 0.5 P/GP | ≥ 0.7 P/GP |
|---|---|---|---|---|---|---|---|
| F | 25 | 0.4 | 400 | 80.3% | 80.1% | 80.5% | 80.1% |
| D | 20 | 0.5 | 800 | 80.6% | 80.1% | 79.8% | 81.6% |
