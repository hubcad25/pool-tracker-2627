"""dashboard.json : cartes de mon équipe, verdicts de chance."""
import pytest

from pipeline import dashboard, rules
from pipeline.events import Event
from tests.test_rules import BASE, MY_TEAM, PARAMS, SCHEDULE, TODAY, league, player

PRIOR = {"sim_mean": 60, "gp": 82, "q10": 45.0, "sim_median": 60.0, "q90": 75.0}
CAREER = {"gp": 1000, "g": 200, "a": 300, "ixg": 200, "sog": 2000, "on_goals": 1000, "on_sog": 10000}


def obs(gp, g, a, ixg=None, sog=None, on_goals=None, on_sog=None):
    """Par défaut, une saison identique à la carrière (aucune chance) ; coéquipiers à 10 % attendus."""
    ixg = g if ixg is None else ixg
    sog = g * 10 if sog is None else sog
    on_sog = sog * 5 if on_sog is None else on_sog
    on_goals = g + (on_sog - sog) * 0.1 if on_goals is None else on_goals
    return {"gp": gp, "g": g, "a": a, "points": g + a, "toi": gp * 1080, "ixg": ixg, "sog": sog,
            "on_goals": on_goals, "on_sog": on_sog, "on_xg": ixg + (on_sog - sog) * 0.1}


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


def test_centile_conforme_quand_la_saison_ressemble_a_la_carriere():
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(20, 10, 10), "career": CAREER}, SCHEDULE, TODAY)
    goals, assists = c["luck"]["goals"], c["luck"]["assists"]
    assert (goals["obs"], goals["shots"], goals["sh_expected"]) == (10, 100, 0.1)
    assert goals["percentile"] == pytest.approx(0.5, abs=0.05)
    assert (assists["obs_goals"], assists["expected_goals"], assists["shots"]) == (40, 40.0, 400)
    assert assists["percentile"] == pytest.approx(0.5, abs=0.05)
    assert c["luck"]["net_points"] == 0.0


def test_centile_chanceux_quand_il_marque_bien_au_dessus_de_son_ixg():
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(20, 20, 5, ixg=10, sog=100), "career": CAREER},
                       SCHEDULE, TODAY)
    assert c["luck"]["goals"]["percentile"] > 0.9
    # Finition de carrière, saison comprise : 220 G / 210 ixG → 10 × 220 / 210 buts attendus
    assert c["luck"]["net_points"] == pytest.approx(25 - 5 - 10 * 220 / 210, abs=0.05)


def test_centile_malchanceux_quand_ses_coequipiers_ne_marquent_pas():
    # 10 buts des coéquipiers pour 40 attendus (xG sur la glace − ixG)
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(20, 10, 2, on_goals=20, on_sog=500), "career": CAREER},
                       SCHEDULE, TODAY)
    assists = c["luck"]["assists"]
    assert (assists["obs_goals"], assists["expected_goals"]) == (10, 40.0)
    assert assists["percentile"] < 0.1
    assert c["luck"]["net_points"] < 0


def test_centile_tient_compte_de_la_taille_de_l_echantillon():
    # Le même sh% de 20 % (attendu 10 %) : peu probable sur 100 tirs, plausible sur 10
    assert dashboard.percentile(20, 100, 0.1) > 0.99
    assert 0.7 < dashboard.percentile(2, 10, 0.1) < 0.9


def test_sans_tirs_pas_de_centile():
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(2, 0, 1, sog=0, on_sog=0, on_goals=0), "career": CAREER},
                       SCHEDULE, TODAY)
    assert (c["luck"]["goals"], c["luck"]["assists"]) == (None, None)


def test_bande_preseason_ramenee_aux_matchs_restants():
    c = dashboard.card(BASE[1], PRIOR | {"obs": obs(10, 3, 3), "career": CAREER}, SCHEDULE, TODAY)
    # 70 matchs restants : la bande de la ROS, pas celle du total final (10 + 70 matchs)
    assert c["ros_prior"] == {"p10": 38.4, "p50": 51.2, "p90": 64.0}
    assert c["prior"]["p50"] == pytest.approx(60 / 82 * 80, abs=0.1)


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


def two_teams(mine, other, points=(20, 10), acquisitions=2):
    return {"teams": [
        {"team_id": MY_TEAM, "abbrev": "HC25", "name": "hubcad25", "points": points[0], "acquisitions": acquisitions,
         "roster": list(mine)},
        {"team_id": 1, "abbrev": "GSP", "name": "GSP", "points": points[1], "roster": list(other)},
    ]}


OTHER = [player(20, "Martin Necas", team="COL", status="OUT", injury="Knee", ret="2026-10-20"),
         player(21, "Cale Makar", pos="D", team="COL", status="DAY_TO_DAY", injury="Lower Body", ret="2026-10-10")]


def test_blessures_de_la_ligue_les_miennes_d_abord_et_sans_dtd_qui_ne_manque_rien():
    priors = {1: PRIOR, 20: PRIOR | {"sim_mean": 90}}
    out = dashboard.injuries(two_teams(BASE, OTHER), MY_TEAM, SCHEDULE, priors, TODAY)
    assert [(i["name"], i["owner"], i["mine"]) for i in out] == [("Seth Jarvis", "HC25", True),
                                                                 ("Martin Necas", "GSP", False)]
    assert out[1]["games_missed"] == 5


FREE = [player(30, "Bon FA", team="CAR"), player(31, "FA moyen", team="CHI"), player(2, "Valeri Nichushkin")]


def test_fa_classes_par_ros_avec_le_gain_vs_mon_pire_joueur():
    priors = {2: PRIOR | {"sim_mean": 50}, 3: PRIOR, 30: PRIOR | {"sim_mean": 55}, 31: PRIOR | {"sim_mean": 40}}
    fa = dashboard.free_agents(two_teams(BASE, OTHER), MY_TEAM, FREE, SCHEDULE, priors, TODAY)
    assert fa["moves_left"] == 1
    assert fa["worst"]["F"]["name"] == "Valeri Nichushkin"
    # Nichushkin est à moi : il n'est pas un FA
    assert [(f["name"], f["gain"]) for f in fa["players"]["F"]] == [("Bon FA", 4.3), ("FA moyen", -8.6)]


def test_fa_mon_joueur_a_l_ir_n_est_pas_mon_pire():
    priors = {1: PRIOR | {"sim_mean": 1}, 2: PRIOR, 3: PRIOR}
    fa = dashboard.free_agents(two_teams(BASE, OTHER), MY_TEAM, [], SCHEDULE, priors, TODAY)
    assert fa["worst"]["F"]["name"] != "Seth Jarvis"


def test_classement_points_actuels_plus_ros_de_l_alignement():
    priors = {i: PRIOR for i in (1, 2, 3, 4, 20, 21)}
    rows = dashboard.standings(two_teams(BASE, OTHER), MY_TEAM, SCHEDULE, priors, TODAY)
    mine = next(r for r in rows if r["mine"])
    assert mine["ros"] == pytest.approx(60 / 82 * (70 - 7) + 60 / 82 * 70 * 3, abs=0.2)
    assert mine["final"] == pytest.approx(20 + mine["ros"], abs=0.1)
    assert sum(r["p_first"] for r in rows) == pytest.approx(1)
    # L'écart-type du total final (gardé pour la P(1er) en direct de la PWA) : p90 = final + Z90 × sd
    assert mine["p90"] == pytest.approx(mine["final"] + dashboard.Z90 * mine["sd"], abs=0.1)
    # 4 joueurs contre 2 : je suis presque sûr de finir 1er
    assert rows[0]["mine"] and mine["p_first"] > 0.99


def test_classement_seulement_10_attaquants_et_5_defenseurs():
    many = [player(100 + i, f"F{i}") for i in range(12)]
    priors = {100 + i: PRIOR for i in range(12)}
    rows = dashboard.standings(two_teams(many, []), MY_TEAM, SCHEDULE, priors, TODAY)
    assert next(r for r in rows if r["mine"])["ros"] == pytest.approx(60 / 82 * 70 * 10, abs=0.5)


def test_build_complet_avec_la_ligue():
    data = dashboard.build(two_teams(BASE, OTHER), MY_TEAM, SCHEDULE, {2: PRIOR}, TODAY, [], FREE)
    assert {"injuries", "free_agents", "standings"} <= data.keys()


def test_classement_intervalle_de_la_ros_sans_les_points_acquis():
    priors = {i: PRIOR for i in (1, 2, 3, 4, 20, 21)}
    mine = next(r for r in dashboard.standings(two_teams(BASE, OTHER), MY_TEAM, SCHEDULE, priors, TODAY)
                if r["mine"])
    assert mine["ros_p10"] < mine["ros"] < mine["ros_p90"]
    assert mine["ros_p90"] - mine["ros"] == pytest.approx(mine["p90"] - mine["final"], abs=0.1)


def test_p_premier_analytique():
    assert dashboard.first_place_odds([100, 100], [10, 10]) == pytest.approx([0.5, 0.5], abs=1e-6)
    odds = dashboard.first_place_odds([110, 100, 90], [10, 10, 10])
    assert sum(odds) == pytest.approx(1, abs=1e-6)
    assert odds[0] > odds[1] > odds[2]


def test_delta_de_p_premier_negatif_pour_un_rival_positif_pour_moi():
    deltas = dashboard.p_first_deltas([100, 100, 90], [10, 10, 10], me=0)
    assert deltas[0] > 0 and deltas[1] < 0 and deltas[2] < 0
    # Le rival à égalité menace plus que celui qui est loin derrière
    assert deltas[1] < deltas[2]
    # Deux normales égales : dérivée φ(0) / √(10² + 10²) ≈ 0,028 par point
    assert dashboard.p_first_deltas([100, 100], [10, 10], me=0)[0] == pytest.approx(0.0282, abs=0.001)


def test_classement_delta_par_point_de_chaque_equipe():
    priors = {i: PRIOR for i in (2, 3, 20)}
    rows = dashboard.standings(two_teams(BASE, [player(20, "Martin Necas", team="COL")], points=(10, 10)),
                               MY_TEAM, SCHEDULE, priors, TODAY)
    by = {r["team_id"]: r for r in rows}
    assert by[MY_TEAM]["delta_p_first_per_point"] > 0 > by[1]["delta_p_first_per_point"]


def test_chance_d_equipe_somme_des_patineurs_de_l_alignement():
    # Chanceux : +10 (voir test_centile_chanceux_...) ; malchanceux : 0 réel pour ~3 attendus
    lucky = PRIOR | {"obs": obs(20, 15, 5, ixg=5), "career": CAREER}
    unlucky = PRIOR | {"obs": obs(20, 0, 0, ixg=3, sog=30), "career": CAREER}
    priors = {2: lucky, 3: unlucky, 4: lucky}
    expected = sum(dashboard.luck(priors[i]["obs"], CAREER, "F" if i < 4 else "D")["net_points"] for i in (2, 3, 4))
    roster = [*BASE, player(5, "Gardien", pos="G", slot="G")]
    rows = dashboard.standings(two_teams(roster, []), MY_TEAM, SCHEDULE, priors | {5: lucky}, TODAY)
    mine = next(r for r in rows if r["mine"])
    assert mine["luck_points"] == pytest.approx(expected, abs=0.1)
    assert next(r for r in rows if not r["mine"])["luck_points"] == 0


def test_chance_d_equipe_sans_l_ir_ni_le_gardien():
    lucky = PRIOR | {"obs": obs(20, 15, 5, ixg=5), "career": CAREER}
    jarvis_ir = BASE[0]
    goalie = player(5, "Gardien", pos="G", slot="G")
    assert dashboard.team_luck({"roster": [jarvis_ir, goalie]}, {1: lucky, 5: lucky}) == 0
    assert dashboard.team_luck({"roster": [BASE[1]]}, {2: lucky}) == pytest.approx(20 - 5 * 215 / 205 - 5, abs=0.05)


def test_p_meilleur_normales_ajustees_aux_p10_p90():
    a = {"mean": 30, "p10": 20, "p90": 40}
    assert dashboard.p_better(a, a) == pytest.approx(0.5)
    # σ = 10 / 1,2816 chacun ; écart 10 → z = 10 / (√2 × 7,80) ≈ 0,906
    assert dashboard.p_better(a | {"mean": 40, "p10": 30, "p90": 50}, a) == pytest.approx(0.8176, abs=0.001)
    assert dashboard.p_better(a, a | {"mean": 40, "p10": 30, "p90": 50}) == pytest.approx(0.1824, abs=0.001)


def test_fa_avec_p_meilleur_et_chance_de_sa_saison():
    lucky = PRIOR | {"sim_mean": 55, "obs": obs(20, 15, 5, ixg=5), "career": CAREER}
    priors = {2: PRIOR | {"sim_mean": 50}, 3: PRIOR, 30: lucky, 31: PRIOR | {"sim_mean": 40}}
    fa = dashboard.free_agents(two_teams(BASE, OTHER), MY_TEAM, FREE, SCHEDULE, priors, TODAY)
    bon, moyen = fa["players"]["F"]
    assert 0.5 < bon["p_better"] < 1 and 0 < moyen["p_better"] < 0.5
    assert (bon["gp"], bon["points"], bon["verdict"]) == (20, 20, "chanceux")
    assert bon["luck"]["net_points"] > 0
    # Sans stats de la saison : pas de chance, échantillon vide
    assert (moyen["gp"], moyen["luck"], moyen["verdict"]) == (0, None, "petit_echantillon")


def test_fa_sans_pire_joueur_a_sa_position_pas_de_p_meilleur():
    goalie = player(40, "Gardien FA", pos="G")
    fa = dashboard.free_agents(two_teams(BASE, OTHER), MY_TEAM, [goalie], SCHEDULE, {40: PRIOR}, TODAY)
    assert fa["players"]["G"][0]["p_better"] is None and fa["players"]["G"][0]["luck"] is None


def test_blesses_avec_la_chance_de_leur_saison():
    priors = {1: PRIOR | {"obs": obs(20, 0, 0, ixg=3, sog=30), "career": CAREER}, 20: PRIOR}
    out = dashboard.injuries(two_teams(BASE, OTHER), MY_TEAM, SCHEDULE, priors, TODAY)
    jarvis, necas = out
    assert jarvis["luck"]["net_points"] < 0 and jarvis["verdict"] == "malchanceux"
    assert (necas["luck"], necas["gp"]) == (None, 0)


def test_cartes_de_toutes_les_equipes():
    priors = {i: PRIOR for i in (1, 2, 3, 4, 20, 21)}
    data = dashboard.build(two_teams(BASE, OTHER), MY_TEAM, SCHEDULE, priors, TODAY, [])
    assert set(data["teams_players"]) == {str(MY_TEAM), "1"}
    assert data["teams_players"][str(MY_TEAM)] == data["players"]
    assert {c["name"] for c in data["teams_players"]["1"]} == {"Martin Necas", "Cale Makar"}
    assert data["teams_players"]["1"][0].keys() == data["players"][0].keys()


def test_sans_ligue_pas_de_cartes_d_equipes():
    assert dashboard.build(None, MY_TEAM, SCHEDULE, {}, TODAY, [])["teams_players"] == {}
