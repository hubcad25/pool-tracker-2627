"""Gardiens : ROS en points de pool (2 W + OTL + SO) par match de leur équipe."""
from datetime import date, timedelta

import pytest

from model import ros as model_ros
from pipeline import dashboard, rules

TODAY = date(2026, 10, 20)
# 10 matchs joués par CBJ, 74 à venir
SCHEDULE = [{"game_id": i, "date": (TODAY + timedelta(days=i - 10)).isoformat(), "team": "CBJ"} for i in range(84)]
GREAVES = {"espn_id": 9, "name": "Jet Greaves", "pos": "G", "pro_team": "CBJ", "slot": "G",
           "injury_status": "ACTIVE", "injury_type": None, "expected_return": None, "out_for_season": False}
PRIOR = {"sim_mean": 67.2, "gp": 84, "q10": 50.4, "sim_median": 67.2, "q90": 84.0}


def test_prior_seul_sans_match_joue():
    mean, p10, p90 = model_ros.goalie_ros(0.8, 0, 0, 84)
    assert mean == pytest.approx(67.2)
    assert p10 < mean < p90


def test_le_rythme_observe_tire_la_ros():
    # 10 matchs d'équipe, 7 victoires dont 1 blanchissage : 15 pts, bien au-dessus du prior (8)
    hot = rules.ros(GREAVES, PRIOR | {"obs": {"gp": 8, "points": 15}}, SCHEDULE, TODAY)
    cold = rules.ros(GREAVES, PRIOR | {"obs": {"gp": 8, "points": 2}}, SCHEDULE, TODAY)
    base = 0.8 * 74
    assert cold[0] < base < hot[0]
    assert hot[0] == pytest.approx((30 * 0.8 + 15) / 40 * 74)


def test_carte_d_un_gardien_en_points_de_pool():
    obs = {"gp": 8, "gs": 8, "w": 6, "otl": 1, "so": 1, "points": 14}
    c = dashboard.card(GREAVES, PRIOR | {"obs": obs}, SCHEDULE, TODAY)
    assert (c["points"], c["w"], c["otl"], c["so"]) == (14, 6, 1, 1)
    assert c["pace"] == pytest.approx(14 / 10 * 84)
    assert c["ros"]["games_left"] == 74
    assert c["final"]["mean"] == pytest.approx(14 + c["ros"]["mean"], abs=0.1)


def test_sans_stats_le_prior_seul_mais_sans_match_joue_le_rythme_baisse():
    panne = rules.ros(GREAVES, PRIOR | {"obs": None}, SCHEDULE, TODAY)
    auxiliaire = rules.ros(GREAVES, PRIOR | {"obs": {"gp": 0, "points": 0}}, SCHEDULE, TODAY)
    assert panne[0] == pytest.approx(0.8 * 74)
    assert auxiliaire[0] < panne[0]


def test_le_classement_compte_un_gardien_par_equipe():
    league = {"teams": [{"team_id": 5, "abbrev": "HC25", "name": "x", "points": 0,
                         "roster": [GREAVES, GREAVES | {"espn_id": 10, "slot": "F"}]}]}
    priors = {9: PRIOR, 10: PRIOR}
    row = dashboard.standings(league, 5, SCHEDULE, priors, TODAY)[0]
    assert row["ros"] == pytest.approx(0.8 * 74, abs=0.1)
