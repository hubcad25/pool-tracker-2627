"""Modèle ROS : prior Marcel, mélange prior / observé, ajustement pour la chance, intervalle."""
import pytest

from model import ros

# Coéquipiers : 20 buts pour 20 attendus (xG sur la glace − ixG) → passes neutres
OBS = {"gp": 20, "g": 10, "a": 10, "ixg": 5, "sog": 50, "on_goals": 30, "on_sog": 300, "on_xg": 25}
# Carrière (avant la saison) : finition neutre (G = ixG)
CAREER = {"gp": 240, "g": 60, "a": 90, "ixg": 60, "sog": 600, "on_goals": 260, "on_sog": 3100}


def test_marcel_pondere_par_les_gp():
    # 25 matchs à 1 P/GP il y a 3 ans ne pèsent presque rien face à 2 saisons pleines à 0,5
    seasons = [{"points": 41, "gp": 82}, {"points": 41, "gp": 82}, {"points": 25, "gp": 25}]
    rate = ros.marcel_rate(seasons, age=None, age_slope=0, age_peak=27)
    assert rate == pytest.approx((5 * 41 + 4 * 41 + 3 * 25) / (5 * 82 + 4 * 82 + 3 * 25))
    assert rate < 0.55


def test_marcel_ajuste_pour_l_age():
    seasons = [{"points": 41, "gp": 82}]
    young = ros.marcel_rate(seasons, age=22, age_slope=0.01, age_peak=27)
    old = ros.marcel_rate(seasons, age=32, age_slope=0.01, age_peak=27)
    assert young == pytest.approx(0.5 * 1.05)
    assert old == pytest.approx(0.5 * 0.95)


def test_marcel_sans_historique():
    assert ros.marcel_rate([{"points": 0, "gp": 0}], age=20, age_slope=0, age_peak=27) is None


def test_rate_sans_match_joue_donne_le_prior():
    assert ros.rate(0.6, None, None, k=30, w=0.5) == 0.6
    assert ros.rate(0.6, OBS | {"gp": 0}, 0.0, k=30, w=0.5) == 0.6


def test_rate_melange_prior_et_observe_selon_k():
    # 20 points en 20 matchs, prior 0,5, k = 20 → moitié-moitié
    assert ros.rate(0.5, OBS, None, k=20, w=0) == pytest.approx(0.75)
    assert ros.rate(0.5, OBS, None, k=0, w=0) == pytest.approx(1.0)


def test_rate_melange_points_reels_et_sans_chance_selon_w():
    # 20 points réels, 10 « sans chance », w = 0,3 → 17 points retenus
    assert ros.rate(0.5, OBS, 10.0, k=0, w=0.3) == pytest.approx(17 / 20)


def test_chance_un_finisseur_chanceux_est_ramene_vers_son_ixg():
    # 10 buts sur 5 ixG, carrière neutre : finition (60 + 10) / (60 + 5), saison comprise
    adjusted = ros.luck_adjusted_points(OBS, CAREER, m=0)
    assert adjusted == pytest.approx(5 * 70 / 65 + 10)
    assert adjusted < 16


def test_chance_passes_gonflees_quand_les_coequipiers_marquent_plus_que_leurs_xg():
    hot = OBS | {"on_goals": 40}   # coéquipiers : 30 buts pour 20 attendus
    assert ros.expected_assists(hot) == pytest.approx(10 * 20 / 30)


def test_chance_passes_intactes_quand_les_coequipiers_marquent_leurs_xg():
    assert ros.expected_assists(OBS) == 10


def test_chance_passes_sans_but_des_coequipiers():
    assert ros.expected_assists(OBS | {"a": 0, "on_goals": 10}) == 0


def test_chance_la_finition_de_carriere_est_regressee_selon_les_gp():
    sniper = CAREER | {"g": 90}            # 90 buts sur 60 ixG
    obs = OBS | {"g": 5, "a": 0, "on_goals": 25, "on_xg": 25}   # saison neutre : 5 buts sur 5 ixG
    assert ros.luck_adjusted_points(obs, sniper, m=0) == pytest.approx(5 * 95 / 65)
    # 240 + 20 GP, m = 260 → moitié carrière, moitié moyenne
    assert ros.luck_adjusted_points(obs, sniper, m=260) == pytest.approx(5 * (0.5 * 95 / 65 + 0.5))
    assert ros.luck_adjusted_points(obs, sniper | {"gp": 24}, m=260) < 5 * 1.2


def test_chance_la_finition_apprise_en_saison_compte():
    # Recrue à 10 buts sur 5 ixG en 20 matchs, m = 20 → finition 0,5 × 2 + 0,5 = 1,5
    assert ros.finishing(None, OBS, m=20) == pytest.approx(1.5)
    assert ros.finishing(None, OBS, m=20) > ros.finishing(None, OBS, m=200) > 1


def test_chance_une_recrue_sans_ecart_est_un_finisseur_moyen():
    assert ros.finishing(None, None, m=100) == 1.0
    assert ros.finishing(None, OBS | {"g": 5}, m=100) == pytest.approx(1.0)


def test_moneypuck_lit_le_xg_sur_la_glace():
    row = {"games_played": "5", "I_F_goals": "3", "I_F_primaryAssists": "4", "I_F_secondaryAssists": "2",
           "icetime": "6409", "I_F_xGoals": "3.37", "I_F_shotsOnGoal": "21", "OnIce_F_goals": "15",
           "OnIce_F_shotsOnGoal": "74", "OnIce_F_xGoals": "10.76"}
    assert ros.from_moneypuck(row)["on_xg"] == 10.76
    assert ros.teammate_goals(ros.from_moneypuck(row)) == (12, pytest.approx(10.76 - 3.37))


def test_intervalle_selon_le_rythme_et_les_matchs_restants():
    q = {"rates": [0, 0.5], "games": [0, 20, 40],
         "q10": [[0.2, 0.3, 0.4], [0.5, 0.7, 0.8]], "q90": [[2.0, 1.8, 1.6], [1.6, 1.4, 1.2]]}
    assert ros.interval(1.0, 10, q) == (10, 5, 16)
    assert ros.interval(0.5, 50, q) == (25, 20, 30)
    assert ros.interval(0.25, 40, q) == (10, 4, 16)
