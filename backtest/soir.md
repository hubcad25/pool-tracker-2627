# Backtest des points d'un soir

Saisons 2022-23 à 2025-26, 158462 joueurs-matchs (patineurs avec un historique), 100% avec des cotes. Hors échantillon : β estimés sans la saison évaluée.

Δ : variation de la déviance de Poisson moyenne vs le modèle actuel (négatif = mieux).

| candidat | déviance | Δ global | Δ 2022-23 | Δ 2023-24 | Δ 2024-25 | Δ 2025-26 |
|---|---|---|---|---|---|---|
| 0. actuel | 0.92737 | +0.00% | +0.00% | +0.00% | +0.00% | +0.00% |
| 1. actuel + calibrage | 0.92746 | +0.01% | +0.01% | +0.01% | +0.01% | +0.01% |
| 2. + domicile, défense adverse | 0.92449 | -0.31% | -0.56% | -0.32% | -0.33% | -0.03% |
| 3. + back-to-back | 0.92701 | -0.04% | -0.05% | -0.01% | -0.08% | -0.01% |
| 4. + main chaude | 0.92736 | -0.00% | +0.01% | -0.01% | -0.01% | +0.01% |
| 5. + cotes | 0.92463 | -0.30% | -0.50% | -0.18% | -0.44% | -0.06% |
| 6. cotes + back-to-back | 0.92452 | -0.31% | -0.51% | -0.18% | -0.47% | -0.07% |
| 7. tout | 0.92382 | -0.38% | -0.64% | -0.32% | -0.48% | -0.09% |

## Effets estimés (toutes les saisons)

× : multiplicateur des points attendus (domicile, b2b : oui vs non ; main chaude : +1 pt/match au-dessus du rythme). ^ : exposant du ratio (défense adverse, cotes).

| candidat | calibrage | domicile | défense adverse | b2b | b2b adverse | main chaude | cotes |
|---|---|---|---|---|---|---|---|
| 1. actuel + calibrage | ×1.000 |  |  |  |  |  |  |
| 2. + domicile, défense adverse | ×0.965 | ×1.075 | ^0.75 |  |  |  |  |
| 3. + back-to-back | ×1.001 |  |  | ×0.924 | ×1.065 |  |  |
| 4. + main chaude | ×0.999 |  |  |  |  | ×1.049 |  |
| 5. + cotes | ×1.002 |  |  |  |  |  | ^0.65 |
| 6. cotes + back-to-back | ×1.006 |  |  | ×0.953 | ×1.020 |  | ^0.62 |
| 7. tout | ×0.985 | ×1.040 | ^0.52 | ×0.947 | ×1.031 | ×1.044 | ^0.31 |

## Gardiens

10524 matchs-équipes avec cotes. Points de pool des gardiens d'une équipe par match : 1.161 en moyenne.

- Erreur quadratique : constante 1.0102, cotes 0.9464 (-6.3%).
- Buts attendus selon les cotes : 3.112 par équipe (réels : 3.111, tirs de barrage compris).
- Prolongation : 15.7% prédite (Poisson), 22.3% réelle.

| prédit | matchs | prédit moyen | réel moyen |
|---|---|---|---|
| 0.4+ | 212 | 0.543 | 0.486 |
| 0.6+ | 939 | 0.720 | 0.763 |
| 0.8+ | 2253 | 0.909 | 0.968 |
| 1.0+ | 2833 | 1.097 | 1.134 |
| 1.2+ | 2698 | 1.295 | 1.319 |
| 1.4+ | 1236 | 1.485 | 1.491 |
| 1.6+ | 353 | 1.677 | 1.720 |
