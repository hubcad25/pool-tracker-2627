"""Notifs de soirée : le bon moment (doit / ne doit pas notifier), les points attendus et réels, les rivaux."""
from datetime import date, datetime

import pytest

from pipeline import config, soiree

DAY = date(2026, 10, 10)
# Premier match à 19 h (23 h UTC), dernier à 22 h (2 h UTC le lendemain)
EAST = {"game_id": 1, "start": "2026-10-10T23:00:00Z", "teams": ["MTL", "TOR"]}
WEST = {"game_id": 2, "start": "2026-10-11T02:00:00Z", "teams": ["EDM", "VAN"]}


def at(hour, minute=0, day=DAY):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=config.TZ)


def games(east="FUT", west="FUT"):
    return [EAST | {"state": east}, WEST | {"state": west}]


NEXT = date(2026, 10, 11)


# --- avant le premier match ---

def test_avant_doit_notifier_dans_l_heure_avant_le_premier_match():
    assert soiree.moment(at(18, 7), games(), [], set()) == ("avant", DAY)


def test_avant_doit_notifier_si_le_premier_match_est_commence_mais_aucun_termine():
    assert soiree.moment(at(19, 40), games(east="LIVE"), [], set()) == ("avant", DAY)


def test_avant_ne_doit_pas_notifier_trop_tot():
    assert soiree.moment(at(17, 37), games(), [], set()) is None


def test_avant_ne_doit_pas_notifier_deux_fois():
    assert soiree.moment(at(18, 37), games(), [], {"2026-10-10:avant"}) is None


def test_avant_ne_doit_pas_notifier_un_soir_sans_match():
    assert soiree.moment(at(18, 37), [], [], set()) is None


def test_avant_ne_doit_pas_notifier_une_fois_un_match_termine():
    assert soiree.moment(at(21, 37), games(east="OFF", west="LIVE"), [], set()) is None


# --- 23 h ---

def test_soir_doit_notifier_un_bilan_partiel_a_23_h():
    assert soiree.moment(at(23, 7), games(east="OFF", west="LIVE"), [], set()) == ("soir", DAY)


def test_soir_est_le_bilan_final_si_tout_est_termine():
    assert soiree.moment(at(23, 7), games(east="OFF", west="OFF"), [], set()) == ("fin", DAY)


def test_soir_ne_doit_pas_notifier_deux_fois_meme_si_les_matchs_finissent_entre_temps():
    assert soiree.moment(at(23, 37), games(east="OFF", west="OFF"), [], {"2026-10-10:soir"}) is None


def test_soir_ne_doit_pas_notifier_avant_23_h():
    assert soiree.moment(at(22, 37), games(east="OFF", west="LIVE"), [], set()) is None


# --- le matin ---

def test_matin_doit_notifier_le_bilan_de_la_veille():
    assert soiree.moment(at(6, 7, NEXT), [], games("OFF", "OFF"), {"2026-10-10:soir"}) == ("fin", DAY)


def test_matin_ne_doit_pas_notifier_si_le_bilan_final_est_parti_a_23_h():
    assert soiree.moment(at(6, 7, NEXT), [], games("OFF", "OFF"), {"2026-10-10:fin"}) is None


def test_matin_ne_doit_pas_notifier_avant_6_h():
    assert soiree.moment(at(5, 37, NEXT), [], games("OFF", "OFF"), set()) is None


def test_matin_ne_doit_pas_notifier_si_un_match_n_est_pas_fini():
    assert soiree.moment(at(6, 7, NEXT), [], games("OFF", "LIVE"), set()) is None


def test_matin_ne_doit_pas_notifier_si_tous_les_matchs_ont_ete_reportes():
    assert soiree.moment(at(6, 7, NEXT), [], games("FUT", "FUT"), set()) is None


# --- calculs ---

def player(espn_id, name, team, slot="F"):
    return {"espn_id": espn_id, "name": name, "pro_team": team, "slot": slot}


ME = {"team_id": 5, "abbrev": "HC25", "points": 60, "roster": [
    player(1, "Alexis Lafrenière", "TOR"), player(2, "Leon Draisaitl", "EDM"),
    player(3, "Connor Bedard", "MTL", slot="IR"), player(4, "Jet Greaves", "MTL", slot="G"),
    player(5, "Quinn Hughes", "MIN", slot="D"),
]}
RATES = {"1": 0.8, "2": 1.4, "3": 1.0, "5": 1.2}
NHL_OF = {1: 101, 2: 102, 3: 103, 4: 104}


def test_soiree_compte_les_matchs_termines_seulement_et_ignore_l_ir():
    points = {101: (2, "1+1"), 104: (2, "victoire")}
    n = soiree.night(ME, RATES, games(east="OFF", west="LIVE"), points, NHL_OF)
    assert n["actual"] == 4
    assert n["expected_done"] == pytest.approx(0.8 + soiree.GOALIE_RATE)
    assert n["expected_left"] == pytest.approx(1.4)
    assert [s[2] for s in n["scorers"]] == ["1+1", "victoire"]


def test_probabilite_de_depassement():
    assert soiree.swap_probability(0, 10, 10) == 1.0
    assert soiree.swap_probability(30, 10, 10) < 0.01
    assert soiree.swap_probability(2, 10, 10) > 0.3
    # Je suis derrière, mais j'ai beaucoup plus de matchs cette semaine
    assert soiree.swap_probability(-3, 20, 8) > 0.9


def test_bilan_final_avec_l_ecart_avant_et_apres():
    rival = {"team_id": 1, "abbrev": "GSP", "points": 59, "roster": [player(11, "Mitch Marner", "VAN")]}
    league = {"teams": [ME, rival]}
    schedule = [{"game_id": 1, "date": "2026-10-10", "team": t} for t in ("MTL", "TOR", "EDM", "VAN")]
    points = {101: (2, "1+1"), 111: (1, "0+1")}
    e = soiree.build("fin", DAY, league, 5, RATES | {"11": 1.0}, schedule, games("OFF", "OFF"), points,
                     NHL_OF | {11: 111})
    assert e.title == "Soirée : 2 pts (attendu 2,9)"
    # Avant la soirée : 58 contre 58 (ESPN compte déjà les points de la soirée)
    assert "GSP : 1 (1,0) · écart 0 → +1" in e.message
