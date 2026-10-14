from pipeline import menaces

DAY = "2026-10-13"


def player(espn_id, nhl_id, name, expected, team="COL", opp="@DAL", game_id=1):
    return {"espn_id": espn_id, "nhl_id": nhl_id, "name": name, "team": team, "opp": opp, "game_id": game_id,
            "expected": expected}


def data():
    """Moi (78 pts) ; RICo, rival (P(1er) bouge) ; Nl, loin derrière (aucun impact) ; LLT à 5 pts, sans impact."""
    return {"date": DAY, "teams": [
        {"team_id": 5, "abbrev": "HC25", "mine": True, "points": 78, "delta_p_first_per_point": 0.004,
         "players": [player(1, 101, "Cole Caufield", 1.0)]},
        {"team_id": 12, "abbrev": "RICo", "mine": False, "points": 60, "delta_p_first_per_point": -0.002,
         "players": [player(2, 102, "Nathan MacKinnon", 1.5)]},
        {"team_id": 8, "abbrev": "Nl", "mine": False, "points": 52, "delta_p_first_per_point": 0.0,
         "players": [player(3, 103, "Brady Tkachuk", 1.0, "OTT", "TOR")]},
        {"team_id": 9, "abbrev": "LLT", "mine": False, "points": 73, "delta_p_first_per_point": None,
         "players": [player(4, 104, "Leon Draisaitl", 1.4, "EDM", "VAN")]},
    ]}


def test_liste_a_surveiller_comme_la_pwa_sans_mes_joueurs():
    watch = menaces.watch_list(data())
    assert [c["name"] for c in watch] == ["Nathan MacKinnon", "Brady Tkachuk", "Leon Draisaitl"]


def test_doit_notifier_un_point_d_une_menace_avec_l_icone_du_pooler():
    evts, keys = menaces.events(menaces.watch_list(data()), {102: (2, "1+1")}, set(), DAY)
    assert len(evts) == 1
    e = evts[0]
    assert e.title == "RICo : MacKinnon 1+1"
    assert e.message == "Nathan MacKinnon (COL @DAL) : 1 but, 1 passe ce soir ≈ −1,0 de tes pts"
    assert e.icon.endswith("poolers/12.png")
    assert keys == {f"{DAY}:102:2"}


def test_doit_notifier_un_point_de_plus_que_le_dernier_notifie():
    evts, _ = menaces.events(menaces.watch_list(data()), {102: (2, "2+0")}, {f"{DAY}:102:1"}, DAY)
    assert len(evts) == 1


def test_doit_faire_une_notif_par_pooler():
    evts, _ = menaces.events(menaces.watch_list(data()), {102: (1, "1+0"), 103: (1, "0+1")}, set(), DAY)
    assert [e.title for e in evts] == ["RICo : MacKinnon 1+0", "Nl : Tkachuk 0+1"]
    assert evts[1].message == "Brady Tkachuk (OTT TOR) : 1 passe ce soir"


def test_ne_doit_pas_notifier_un_point_deja_notifie():
    evts, _ = menaces.events(menaces.watch_list(data()), {102: (1, "1+0")}, {f"{DAY}:102:1"}, DAY)
    assert evts == []


def test_ne_doit_pas_notifier_un_point_retire():
    evts, _ = menaces.events(menaces.watch_list(data()), {102: (1, "1+0")}, {f"{DAY}:102:2"}, DAY)
    assert evts == []


def test_ne_doit_pas_notifier_mes_joueurs_ni_un_joueur_hors_liste():
    evts, _ = menaces.events(menaces.watch_list(data()), {101: (2, "2+0"), 999: (1, "1+0")}, set(), DAY)
    assert evts == []
