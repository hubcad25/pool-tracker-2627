"""Scénarios « snapshot d'hier / snapshot d'aujourd'hui » → notif attendue (ou aucune)."""
import copy
from datetime import date, timedelta

import pytest

from pipeline import rules

TODAY = date(2026, 10, 10)
MY_TEAM = 5


def schedule(team: str, n: int = 70, every: int = 2) -> list[dict]:
    """Un match tous les `every` jours à partir d'aujourd'hui."""
    return [{"game_id": i, "date": (TODAY + timedelta(days=i * every)).isoformat(), "team": team} for i in range(n)]


SCHEDULE = schedule("CAR") + schedule("CHI") + schedule("COL") + schedule("VAN")


def player(espn_id, name, pos="RW", team="CAR", slot="F", status="ACTIVE", injury=None, ret=None):
    return {"espn_id": espn_id, "name": name, "pos": pos, "pro_team": team, "slot": slot,
            "injury_status": status, "injury_type": injury, "expected_return": ret, "out_for_season": False}


def league(*roster, team_id=MY_TEAM):
    return {"teams": [{"team_id": team_id, "roster": list(roster)}]}


BASE = [
    player(1, "Seth Jarvis", slot="IR", status="INJURY_RESERVE", injury="Shoulder", ret="2026-10-24"),
    player(2, "Valeri Nichushkin", team="COL"),
    player(3, "Brock Boeser", team="VAN"),
    player(4, "Quinn Hughes", pos="D", team="VAN"),
]
PRIORS = {2: {"sim_mean": 50, "gp": 82}, 3: {"sim_mean": 60, "gp": 82}, 4: {"sim_mean": 80, "gp": 82}}
QUANTILES = {"rates": [0], "games": [0], "q10": [[0.8]], "q90": [[1.2]]}
PARAMS = {pos: {"k": 30, "w": 0.0, "quantiles": QUANTILES} for pos in ("F", "D")}


@pytest.fixture(autouse=True)
def params(monkeypatch):
    monkeypatch.setattr(rules, "ros_params", lambda: PARAMS)


def evaluate(prev, cur, priors=PRIORS):
    return rules.evaluate(league(*prev), league(*cur), MY_TEAM, SCHEDULE, priors, TODAY)


FIELDS = {"status": "injury_status", "injury": "injury_type", "ret": "expected_return"}


def changed(espn_id, **fields):
    cur = copy.deepcopy(BASE)
    next(p for p in cur if p["espn_id"] == espn_id).update({FIELDS.get(k, k): v for k, v in fields.items()})
    return cur


def test_matchs_manques_selon_le_calendrier():
    # 14 jours, un match aux 2 jours à partir d'aujourd'hui → 7 matchs
    p = player(9, "X", ret=(TODAY + timedelta(days=14)).isoformat())
    assert rules.games_missed(p, SCHEDULE, TODAY) == 7


def test_blessure_d_un_joueur_actif():
    cur = changed(2, status="INJURY_RESERVE", injury="Knee", ret="2026-10-30")
    [e] = evaluate(BASE, cur)
    assert e.kind == "status"
    assert e.message == "Nichushkin → IR (genou), retour ~30 oct, manque 10 matchs"


def test_suspension_sans_type_de_blessure():
    [e] = evaluate(BASE, changed(3, status="SUSPENSION", injury="Suspension", ret="2026-10-14"))
    assert e.message == "Boeser → suspendu, retour ~14 oct, manque 2 matchs"


def test_blessure_sans_date_de_retour():
    [e] = evaluate(BASE, changed(2, status="OUT", injury="Lower Body"))
    assert e.message == "Nichushkin → OUT (bas du corps), retour inconnu"


def test_ne_notifie_pas_un_dtd_sans_match_manque():
    assert evaluate(BASE, changed(2, status="DAY_TO_DAY", injury="Illness")) == []
    assert evaluate(BASE, changed(2, status="DAY_TO_DAY", injury="Illness", ret=TODAY.isoformat())) == []


def test_ne_notifie_pas_le_retour_au_jeu_d_un_joueur_de_l_alignement():
    prev = changed(2, status="OUT", injury="Knee")
    assert evaluate(prev, BASE) == []


def test_ne_notifie_pas_un_joueur_qui_vient_d_arriver():
    cur = BASE + [player(5, "Nouveau Venu", status="OUT", injury="Knee")]
    assert evaluate(BASE, cur) == []


def test_ne_notifie_pas_sans_snapshot_la_veille():
    assert rules.evaluate(None, league(*changed(2, status="OUT")), MY_TEAM, SCHEDULE, PRIORS, TODAY) == []


def test_ne_notifie_pas_une_autre_equipe():
    prev = {"teams": [{"team_id": MY_TEAM, "roster": BASE}, {"team_id": 7, "roster": [player(8, "Autre Gars")]}]}
    cur = copy.deepcopy(prev)
    cur["teams"][1]["roster"][0].update(injury_status="INJURY_RESERVE", expected_return="2026-11-30")
    assert rules.evaluate(prev, cur, MY_TEAM, SCHEDULE, PRIORS, TODAY) == []


def test_date_de_retour_repoussee():
    [e] = evaluate(BASE, changed(1, ret="2026-11-07"))
    assert e.kind == "return_date"
    assert e.message == "Jarvis : retour repoussé au ~7 nov (était ~24 oct), manque 14 matchs"


def test_ne_notifie_pas_un_petit_decalage_de_date():
    # 4 jours = 2 matchs < seuil de 3
    assert evaluate(BASE, changed(1, ret="2026-10-28")) == []


def test_activation_suggere_le_drop_au_plus_faible_ros_de_la_meme_position():
    [e] = evaluate(BASE, changed(1, status="ACTIVE", injury=None, ret=None))
    assert e.kind == "activation"
    # 70 matchs restants au rythme du prior : Nichushkin 50/82 → 43, Boeser 60/82 → 51 (intervalle ×0,8-1,2).
    # Hughes (D) n'est pas candidat.
    assert e.message == "Jarvis activable → drop Nichushkin (ROS 43, 34-51) plutôt que Boeser (ROS 51, 41-61)"


def test_activation_la_ros_tient_compte_du_debut_de_saison():
    # Nichushkin : 20 points en 20 matchs → (30 × 0,61 + 20) / 50 = 0,77 P/GP, il passe devant Boeser (0,73)
    obs = {"gp": 20, "g": 10, "a": 10, "ixg": 10, "sog": 50, "on_goals": 30, "on_sog": 300}
    priors = PRIORS | {2: PRIORS[2] | {"obs": obs}}
    [e] = evaluate(BASE, changed(1, status="ACTIVE", injury=None, ret=None), priors=priors)
    assert e.message.startswith("Jarvis activable → drop Boeser (ROS 51")


def test_activation_un_candidat_blesse_perd_ses_matchs_manques():
    cur = changed(1, status="ACTIVE", injury=None, ret=None)
    next(p for p in cur if p["espn_id"] == 3).update(injury_status="OUT", expected_return="2026-12-09")
    prev = copy.deepcopy(BASE)
    next(p for p in prev if p["espn_id"] == 3).update(injury_status="OUT", expected_return="2026-12-09")
    [e] = evaluate(prev, cur)
    # Boeser manque 30 matchs : 60/82 × 40 → 29, maintenant sous Nichushkin
    assert e.message.startswith("Jarvis activable → drop Boeser (ROS 29")


def test_activation_un_joueur_sans_prior_passe_en_premier():
    [e] = evaluate(BASE, changed(1, status="ACTIVE"), priors={3: PRIORS[3]})
    assert "drop Nichushkin (ROS ?)" in e.message


def test_dtd_dans_le_slot_ir_est_activable():
    [e] = evaluate(BASE, changed(1, status="DAY_TO_DAY"))
    assert e.kind == "activation"


def test_activation_notifiee_une_seule_fois():
    active = changed(1, status="ACTIVE", injury=None, ret=None)
    assert evaluate(active, active) == []
