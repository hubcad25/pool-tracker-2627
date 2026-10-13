"""data/today.json : la soirée dans la PWA (matchs, attendus, P(1er) et son historique, joueurs à surveiller)."""
from datetime import date, datetime

import pytest

from pipeline import config, today

DAY = date(2026, 10, 10)
NOW = datetime(2026, 10, 10, 12, 5, tzinfo=config.TZ)
# MTL @ TOR à 19 h, EDM @ VAN à 22 h (teams : [visiteur, local])
EAST = {"game_id": 1, "start": "2026-10-10T23:00:00Z", "teams": ["MTL", "TOR"]}
WEST = {"game_id": 2, "start": "2026-10-11T02:00:00Z", "teams": ["EDM", "VAN"]}


def games(east="FUT", west="FUT"):
    return [EAST | {"state": east}, WEST | {"state": west}]


def player(espn_id, name, team, slot="F", status="ACTIVE"):
    return {"espn_id": espn_id, "name": name, "pos": "C", "pro_team": team, "slot": slot, "injury_status": status}


ME = {"team_id": 5, "abbrev": "HC25", "name": "hubcad25", "points": 60, "roster": [
    player(1, "Alexis Lafrenière", "TOR"), player(2, "Leon Draisaitl", "EDM", status="DAY_TO_DAY"),
    player(3, "Connor Bedard", "MTL", slot="IR"), player(4, "Quinn Hughes", "MIN", slot="D"),
]}
GSP = {"team_id": 1, "abbrev": "GSP", "name": "GSP", "points": 58, "roster": [
    player(11, "Mitch Marner", "VAN"), player(12, "Nick Suzuki", "MTL"),
]}
FAR = {"team_id": 2, "abbrev": "LOIN", "name": "Loin", "points": 20, "roster": [player(21, "Cole Caufield", "MTL")]}
LEAGUE = {"teams": [ME, GSP, FAR]}
RATES = {"1": 0.8, "2": 1.4, "3": 1.0, "4": 0.5, "11": 1.0, "12": 0.9, "21": 1.2}
NHL_OF = {1: 101, 2: 102, 11: 111, 12: 112, 21: 121}
ODDS = {5: (0.6, 0.02), 1: (0.39, -0.015), 2: (0.01, -0.001)}


def build(game_list=None, points=None, history=(), odds=ODDS):
    return today.build(DAY, LEAGUE, 5, RATES, games() if game_list is None else game_list, points or {}, NHL_OF,
                       odds, list(history), NOW)


def test_sans_match_today_est_vide():
    t = build([])
    assert (t["games"], t["my_players"], t["watch"]) == ([], [], [])
    assert all(r["playing_tonight"] == 0 and r["expected_tonight"] == 0 for r in t["teams"])
    assert t["p_first"]["now"] == 0.6


def test_mes_joueurs_qui_jouent_ce_soir_par_heure_sans_l_ir():
    t = build()
    assert [(p["name"], p["opp"], p["injury"]) for p in t["my_players"]] == [
        ("Alexis Lafrenière", "MTL", None), ("Leon Draisaitl", "@VAN", "DAY_TO_DAY")]
    assert all(p["actual"] is None for p in t["my_players"])
    mine = next(r for r in t["teams"] if r["mine"])
    assert (mine["expected_tonight"], mine["playing_tonight"], mine["actual_tonight"]) == (2.2, 2, None)


def test_equipes_triees_par_p_premier():
    assert [r["abbrev"] for r in build()["teams"]] == ["HC25", "GSP", "LOIN"]


def test_watch_les_adversaires_les_plus_menacants_d_abord():
    w = build()["watch"]
    # Marner : 1,0 × −0,015 ; Suzuki : 0,9 × −0,015 ; Caufield : 1,2 × −0,001
    assert [(p["name"], p["owner"]["abbrev"]) for p in w] == [("Mitch Marner", "GSP"), ("Nick Suzuki", "GSP"),
                                                              ("Cole Caufield", "LOIN")]
    assert w[0]["threat"] == pytest.approx(-0.015)
    assert w[0]["opp"] == "EDM" and w[1]["opp"] == "@TOR"


def test_watch_limite_a_8_joueurs():
    many = {"team_id": 1, "abbrev": "GSP", "points": 58,
            "roster": [player(100 + i, f"Joueur {i}", "VAN") for i in range(12)]}
    t = today.build(DAY, {"teams": [ME, many]}, 5, RATES, games(), {}, NHL_OF, ODDS, [], NOW)
    assert len(t["watch"]) == today.WATCH


def test_points_reels_des_matchs_termines_seulement():
    t = build(games(east="OFF", west="LIVE"), points={101: (2, "1+1"), 112: (1, "0+1")})
    assert t["games"][0]["state"] == "FINAL" and t["games"][1]["state"] == "LIVE"
    assert [p["actual"] for p in t["my_players"]] == [2, None]
    by = {r["abbrev"]: r for r in t["teams"]}
    assert (by["HC25"]["actual_tonight"], by["GSP"]["actual_tonight"]) == (2, 1)


def test_sans_odds_la_menace_est_inconnue_mais_la_soiree_reste():
    t = build(odds={})
    assert t["p_first"]["now"] is None
    assert len(t["watch"]) == 3 and all(p["threat"] is None for p in t["watch"])


def test_historique_toute_la_saison_jusqu_au_jour_et_veille():
    history = [{"day": f"2026-10-{d:02d}", "p_first": d / 100} for d in range(1, 12)]
    p = build(history=history)["p_first"]
    assert p["yesterday"] == 0.09
    # Pas le lendemain : on regarde la soirée du 10
    assert [h["day"] for h in p["history"]] == [f"2026-10-{d:02d}" for d in range(1, 11)]


def test_historique_une_valeur_par_jour(tmp_path, monkeypatch):
    monkeypatch.setattr(today, "HISTORY", tmp_path / "p_first.json")
    today.record_p_first(date(2026, 10, 11), 0.7)
    today.record_p_first(date(2026, 10, 10), 0.6)
    today.record_p_first(date(2026, 10, 11), 0.75)
    assert today.load_history() == [{"day": "2026-10-10", "p_first": 0.6}, {"day": "2026-10-11", "p_first": 0.75}]


def test_la_soiree_relit_les_odds_du_today_precedent(tmp_path, monkeypatch):
    monkeypatch.setattr(today, "PATH", tmp_path / "today.json")
    assert today.load_odds() == {}
    today.write(build())
    assert today.load_odds() == ODDS


def test_chaque_equipe_liste_ses_joueurs_de_ce_soir_pour_le_direct():
    t = build(games(east="OFF"), points={101: (2, "1+1")})
    by = {r["abbrev"]: r for r in t["teams"]}
    assert [(p["name"], p["nhl_id"], p["game_id"], p["team"], p["expected"], p["actual"])
            for p in by["HC25"]["players"]] == [("Alexis Lafrenière", 101, 1, "TOR", 0.8, 2),
                                                ("Leon Draisaitl", 102, 2, "EDM", 1.4, None)]
    assert [p["name"] for p in by["GSP"]["players"]] == ["Nick Suzuki", "Mitch Marner"]
    assert set(by["GSP"]["players"][0]) == set(today.LIVE_FIELDS)


def test_l_ir_et_les_equipes_qui_ne_jouent_pas_n_ont_aucun_joueur():
    t = build([WEST | {"state": "FUT"}])
    by = {r["abbrev"]: r for r in t["teams"]}
    assert [p["name"] for p in by["HC25"]["players"]] == ["Leon Draisaitl"]
    assert by["LOIN"]["players"] == []


def test_mes_joueurs_et_watch_ont_les_ids_du_match():
    t = build()
    assert (t["my_players"][0]["nhl_id"], t["my_players"][0]["game_id"]) == (101, 1)
    assert (t["watch"][0]["nhl_id"], t["watch"][0]["game_id"]) == (111, 2)


def test_chaque_equipe_garde_son_total_final_du_matin_pour_la_p_premier_en_direct(tmp_path, monkeypatch):
    monkeypatch.setattr(today, "PATH", tmp_path / "today.json")
    finals = {5: (180.5, 9.1), 1: (175.0, 8.7), 2: (120.2, 7.0)}
    t = today.build(DAY, LEAGUE, 5, RATES, games(), {}, NHL_OF, ODDS, [], NOW, team_finals=finals)
    assert {r["team_id"]: (r["final"], r["sd"]) for r in t["teams"]} == finals
    today.write(t)
    assert today.load_finals() == finals


def test_sans_totaux_du_matin_final_et_sd_sont_vides():
    assert all((r["final"], r["sd"]) == (None, None) for r in build()["teams"])
