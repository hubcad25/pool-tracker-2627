"""Modèle ROS : prior Marcel, mélange prior / observé, ajustement pour la chance, intervalle."""
import pytest

from model import ros

OBS = {"gp": 20, "g": 10, "a": 10, "ixg": 5, "sog": 50, "on_goals": 30, "on_sog": 300}
# Carrière : finition neutre (G = ixG) et sh% des coéquipiers de 8 %
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


def test_chance_un_finisseur_chanceux_est_ramene_a_son_ixg():
    # 10 buts sur 5 ixG, finition de carrière neutre → ~5 buts
    obs = OBS | {"on_goals": 10 + 10 + 2, "on_sog": 50 + 140}   # sh% des coéquipiers 12/140 ≈ 8,6 %
    adjusted = ros.luck_adjusted_points(obs, CAREER, m=0, league_sh=0.09)
    assert adjusted < 16
    assert adjusted == pytest.approx(5 + 10 * (200 / 2500) / (12 / 140))


def test_chance_des_passes_gonflees_par_le_sh_des_coequipiers():
    hot = OBS | {"on_goals": 40, "on_sog": 300, "ixg": 10}   # coéquipiers à 30/250 = 12 % vs 8 % en carrière
    assert ros.luck_adjusted_points(hot, CAREER, m=0, league_sh=0.09) == pytest.approx(10 + 10 * 0.08 / 0.12)


def test_chance_la_finition_de_carriere_est_regressee_selon_les_gp():
    sniper = CAREER | {"g": 90}   # 90 buts sur 60 ixG : finition 1,5
    obs = OBS | {"a": 0}
    assert ros.luck_adjusted_points(obs, sniper, m=0, league_sh=0.09) == pytest.approx(5 * 1.5)
    # 240 GP de carrière, m = 240 → moitié carrière, moitié moyenne : 1,25
    assert ros.luck_adjusted_points(obs, sniper, m=240, league_sh=0.09) == pytest.approx(5 * 1.25)
    assert ros.luck_adjusted_points(obs, sniper | {"gp": 24}, m=240, league_sh=0.09) < 5 * 1.1


def test_chance_une_recrue_est_un_finisseur_moyen():
    # 10 buts sur 5 ixG → 5 buts ; passes ramenées au sh% des coéquipiers de la ligue (9 % vs 20/250 = 8 %)
    adjusted = ros.luck_adjusted_points(OBS, None, m=100, league_sh=0.09)
    assert adjusted == pytest.approx(5 + 10 * 0.09 / 0.08)


def test_intervalle_selon_le_rythme_et_les_matchs_restants():
    q = {"rates": [0, 0.5], "games": [0, 20, 40],
         "q10": [[0.2, 0.3, 0.4], [0.5, 0.7, 0.8]], "q90": [[2.0, 1.8, 1.6], [1.6, 1.4, 1.2]]}
    assert ros.interval(1.0, 10, q) == (10, 5, 16)
    assert ros.interval(0.5, 50, q) == (25, 20, 30)
    assert ros.interval(0.25, 40, q) == (10, 4, 16)
