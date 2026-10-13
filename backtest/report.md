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
| 4. mélange + chance | 0.1521 | 77.3% |
| 5. + rôle observé (saison) | 0.1509 | 77.5% |
| 5b. + rôle récent (5 derniers matchs) | 0.1505 | 77.5% |
| 6. + rôle parfait (plafond) | 0.1360 | 79.8% |

## RMSE P/GP par coupure

| candidat | 10 m | 20 m | 30 m | 41 m | 60 m |
|---|---|---|---|---|---|
| 1. prior | 0.1571 | 0.1614 | 0.1692 | 0.1797 | 0.2132 |
| 2. observé | 0.2607 | 0.2102 | 0.1867 | 0.1795 | 0.1980 |
| 3. mélange | 0.1497 | 0.1473 | 0.1505 | 0.1572 | 0.1876 |
| 4. mélange + chance | 0.1475 | 0.1452 | 0.1489 | 0.1549 | 0.1856 |
| 5. + rôle observé (saison) | 0.1467 | 0.1438 | 0.1477 | 0.1533 | 0.1844 |
| 5b. + rôle récent (5 derniers matchs) | 0.1466 | 0.1439 | 0.1470 | 0.1527 | 0.1837 |
| 6. + rôle parfait (plafond) | 0.1271 | 0.1284 | 0.1342 | 0.1418 | 0.1747 |

## Paramètres retenus

| position | k | w | m | couverture 80 % : ≥ 0 P/GP | ≥ 0.3 P/GP | ≥ 0.5 P/GP | ≥ 0.7 P/GP |
|---|---|---|---|---|---|---|---|
| F | 25 | 0.5 | 400 | 80.3% | 80.1% | 80.3% | 80.1% |
| D | 20 | 0.7 | 1600 | 80.5% | 80.3% | 80.5% | 81.1% |

## Ajustement pour la chance : finition et passes

Finition (G / ixG régressée avec GP / (GP + m)) : A = 3 saisons, B = carrière depuis 2008-09, C = carrière + saison en cours jusqu'à la coupure. Passes : X = × sh% des coéquipiers de carrière / de la saison, Y = × buts attendus des coéquipiers sur la glace (OnIce_F_xGoals − ixG) / leurs buts.
Δ : écart de RMSE avec la variante retenue, IC 90 % par bootstrap des joueurs (300 tirages).

| variante | RMSE P/GP | Δ vs retenue (IC 90 %) | ordre | couverture 80 % | k, w, m (F) | k, w, m (D) |
|---|---|---|---|---|---|---|
| A·X (3 saisons, sh% des coéquipiers) | 0.15272 | +0.00066 [+0.00019, +0.00108] | 77.10% | 80.3% | 25, 0.4, 400 | 20, 0.5, 800 |
| B·X (carrière, sh% des coéquipiers) | 0.15247 | +0.00040 [-0.00007, +0.00084] | 77.17% | 80.3% | 20, 0.5, 200 | 20, 0.5, 400 |
| C·X (carrière + saison, sh% des coéquipiers) | 0.15238 | +0.00031 [-0.00016, +0.00077] | 77.15% | 80.3% | 20, 0.5, 200 | 20, 0.5, 400 |
| A·Y (3 saisons, xG des coéquipiers) | 0.15205 | -0.00002 [-0.00013, +0.00009] | 77.28% | 80.3% | 25, 0.5, 800 | 20, 0.7, 1000000 |
| B·Y (carrière, xG des coéquipiers) | 0.15212 | +0.00005 [+0.00001, +0.00009] | 77.29% | 80.2% | 25, 0.5, 800 | 20, 0.7, 1000000 |
| C·Y (carrière + saison, xG des coéquipiers) | 0.15207 | — | 77.29% | 80.3% | 25, 0.5, 400 | 20, 0.7, 1600 |
