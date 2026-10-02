"""dashboard.json : cartes de mon équipe, verdicts de chance."""
import pytest

from pipeline import dashboard, rules
from pipeline.events import Event
from tests.test_rules import BASE, MY_TEAM, PARAMS, SCHEDULE, TODAY, league, player

PRIOR = {"sim_mean": 60, "gp": 82, "q10": 45.0, "sim_median": 60.0, "q90": 75.0}
CAREER = {"gp": 1000, "g": 200, "a": 300, "ixg": 200, "sog": 2000, "on_goals": 1000, "on_sog": 10000}


def obs(gp, g, a, ixg=None, sog=None, on_goals=None, on_sog=None):
    """Par défaut, une saison identique à la carrière (aucune chance)."""
    ixg = g if ixg is None else ixg
    sog = g * 10 if sog is None else sog
    on_sog = sog * 5 if on_sog is None else on_sog
    on_goals = g + (on_sog - sog) * 0.1 if on_goals is None else on_goals
    return {"gp": gp, "g": g, "a": a, "points": g + a, "toi": gp * 1080, "ixg": ixg, "sog": sog,
            "on_goals": on_goals, "on_sog": on_sog}


@pytest.fixture(autouse=True)
def params(monkeypatch):
    monkeypatch.setattr(rules, "ros_params", lambda: PARAMS | {"F": PARAMS["F"] | {"m": 0}})


def build(*roster, priors=None, alerts=()):
    return dashboard.build(league(*roster), MY_TEAM, SCHEDULE, priors or {}, TODAY, list(alerts))


def test_carte_avant_le_premier_match():
    c = dashboard.card(BASE[1], PRIOR, SCHEDULE, TODAY)
    assert (c["gp"], c["points"], c["pace"]) == (0, 0, None)
    assert c["ros"]["games_left"] == 70
    # Bande ramenée de 82 à 70 matchs, comme le total final
    assert c["prior"] == {"p10": 38.4, "p50": 51.2, "p90": 64.0}
    assert c["prior"]["p50"] == c["final"]["mean"]
    assert c["final"]["mean"] == pytest.approx(60 / 82 * 70, abs=0.1)
    assert c["verdict"] == "petit_echantillon"


def test_carte_total_final_egal_points_plus_ros():
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(20, 8, 12), "career": CAREER}, SCHEDULE, TODAY)
    assert c["points"] == 20
    assert c["pace"] == 84.0
    assert c["final"]["mean"] == pytest.approx(20 + c["ros"]["mean"], abs=0.1)
    assert c["final"]["p10"] < c["final"]["mean"] < c["final"]["p90"]


def test_blesse_avec_matchs_manques_et_moins_de_matchs_restants():
    jarvis = BASE[0]
    c = dashboard.card(jarvis, PRIOR, SCHEDULE, TODAY)
    assert c["injury"]["status"] == "INJURY_RESERVE"
    assert c["injury"]["games_missed"] == 7
    assert c["ros"]["games_left"] == 70 - 7
    assert c["prior"]["p50"] == round(60 / 82 * 63, 1)


def test_joueur_actif_sans_bloc_blessure():
    assert dashboard.card(BASE[1], PRIOR, SCHEDULE, TODAY)["injury"] is None


def test_verdict_malchanceux_quand_il_tire_sous_son_ixg():
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(20, 2, 10, ixg=8), "career": CAREER}, SCHEDULE, TODAY)
    assert c["luck"]["g_minus_ixg"] == -6.0
    assert c["verdict"] == "malchanceux"


def test_verdict_chanceux_quand_il_marque_au_dessus_de_son_ixg():
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(20, 12, 8, ixg=6), "career": CAREER}, SCHEDULE, TODAY)
    assert c["verdict"] == "chanceux"


def test_verdict_conforme_quand_l_ecart_est_petit():
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(20, 8, 10, ixg=7), "career": CAREER}, SCHEDULE, TODAY)
    assert c["verdict"] == "conforme"


def test_pas_de_verdict_de_chance_avant_10_matchs():
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(9, 0, 2, ixg=5), "career": CAREER}, SCHEDULE, TODAY)
    assert c["verdict"] == "petit_echantillon"


def test_gardien_sans_ros_ni_verdict():
    c = dashboard.card(player(9, "Jet Greaves", pos="G", slot="G"), {"q10": 58, "sim_median": 68, "q90": 79},
                       SCHEDULE, TODAY)
    assert (c["prior"], c["ros"], c["final"], c["luck"], c["verdict"]) == (None,) * 5


def test_ordre_attaquants_defenseurs_gardien_ir_puis_total_final():
    priors = {2: PRIOR, 3: PRIOR | {"sim_mean": 70}, 4: PRIOR}
    goalie = player(9, "Jet Greaves", pos="G", slot="G")
    names = [c["name"] for c in build(*BASE, goalie, priors=priors)["players"]]
    assert names == ["Brock Boeser", "Valeri Nichushkin", "Quinn Hughes", "Jet Greaves", "Seth Jarvis"]


def test_les_alertes_du_jour_sont_reprises():
    data = build(*BASE, alerts=[Event("activation", "k", "Jarvis activable", 5)])
    assert data["alerts"] == [{"kind": "activation", "message": "Jarvis activable", "priority": 5}]
    assert data["day"] == TODAY.isoformat()


def test_sans_ligue_le_dashboard_est_vide():
    data = dashboard.build(None, MY_TEAM, SCHEDULE, {}, TODAY, [])
    assert (data["team"], data["players"]) == (None, [])
