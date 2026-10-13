"""Contexte du match de ce soir : buts attendus selon les cotes, facteurs patineur et gardien, historique."""
from datetime import date

import pytest

from model import soir
from pipeline import contexte

DAY = date(2026, 10, 13)
SCHEDULE = [{"team": "MTL", "date": "2026-10-13"}, {"team": "BUF", "date": "2026-10-13"},
            {"team": "BUF", "date": "2026-10-12"}]


def book(name="DraftKings", home_ml=-155, away_ml=130, total=6.5, over=-105, under=-115):
    return {"book": name, "home_ml": home_ml, "away_ml": away_ml, "total": total, "over": over, "under": under}


def game(state="pre", books=None):
    return {"home": "MTL", "away": "BUF", "state": state, "books": books or [book()]}


def test_le_favori_doit_marquer_plus_et_les_buts_attendus_respectent_le_total():
    goals = contexte.expected_goals([game()])
    mtl, buf = goals["MTL"], goals["BUF"]
    assert mtl[0] > buf[0] and mtl == (buf[1], buf[0])
    assert soir.p_win(*mtl) == pytest.approx(soir.fair(-155, 130)[0], abs=1e-6)


def test_cotes_d_un_match_commence_ignorees():
    assert contexte.expected_goals([game(state="in")]) == {}


def test_livre_live_et_cotes_incoherentes_ignores():
    assert soir.game_odds([book(name="ESPN Bet - Live Odds", home_ml=600, away_ml=-1200)]) is None
    assert soir.game_odds([book(home_ml=100, away_ml=210)]) is None   # marge négative : cote périmée


def test_facteur_patineur_selon_les_buts_attendus_et_le_back_to_back():
    assert soir.skater_factor(3.1, 3.1, b2b=False) == 1.0
    assert soir.skater_factor(3.41, 3.1, b2b=False) == pytest.approx(1.1 ** soir.ODDS_EXPONENT)
    assert soir.skater_factor(None, 3.1, b2b=True) == soir.B2B


def test_facteur_gardien_plus_haut_quand_son_equipe_est_favorite():
    assert soir.goalie_factor(3.5, 2.6, 3.1, 3.1) > 1 > soir.goalie_factor(2.6, 3.5, 3.1, 3.1)
    assert soir.goalie_factor(None, None, 3.1, 3.1) == 1.0


def test_facteurs_relatifs_a_la_moyenne_de_l_equipe_cette_saison():
    goals = {"MTL": (3.5, 2.8), "BUF": (2.8, 3.5)}
    strong = {"2026-10-1" + str(d): {"MTL": [3.5, 2.8]} for d in range(10)}
    last_season = {"2026-04-10": {"MTL": [1.0, 5.0]}}
    f_new = contexte.factors(DAY, goals, last_season, SCHEDULE)
    f_known = contexte.factors(DAY, goals, strong | last_season, SCHEDULE)
    assert f_new["MTL"][0] > f_known["MTL"][0] > 1    # la moyenne de MTL monte : le facteur baisse
    assert f_new["BUF"][0] < soir.B2B                  # BUF a joué hier et est négligé


def test_sans_cotes_seul_le_back_to_back_compte():
    f = contexte.factors(DAY, {}, {}, SCHEDULE)
    assert f == {"MTL": (1.0, 1.0), "BUF": (soir.B2B, 1.0)}


def test_la_soiree_relit_les_buts_attendus_gardes_sans_appeler_espn(tmp_path, monkeypatch):
    monkeypatch.setattr(contexte, "HISTORY", tmp_path / "buts.json")
    contexte.record(DAY, {"MTL": (3.4, 2.9), "BUF": (2.9, 3.4)})
    monkeypatch.setattr(contexte, "tonight", lambda day: pytest.fail("ESPN appelé"))
    assert contexte.load(DAY, SCHEDULE)["MTL"][0] > 1


def test_l_historique_ajoute_les_matchs_sans_effacer_ceux_du_jour(tmp_path, monkeypatch):
    monkeypatch.setattr(contexte, "HISTORY", tmp_path / "buts.json")
    contexte.record(DAY, {"MTL": (3.4, 2.9)})
    contexte.record(DAY, {"BUF": (2.9, 3.4)})
    assert set(contexte.load_history()["2026-10-13"]) == {"MTL", "BUF"}
