"""Partants MoneyPuck : lecture de la page du jour et points attendus des gardiens."""
from datetime import date

import pytest

from model import soir as model
from pipeline import partants, soiree
from pipeline.contexte import LEAGUE_GOALS
from pipeline.sources import moneypuck

DAY = date(2026, 10, 13)


def _side(pct: str, starter: str | None) -> str:
    who = f"<h3><b><div style='color:#00008B'>Likely Starter:<BR>{starter}</div></b></h3>" if starter else ""
    return f'<td align="center"><h2>{pct}</h2>{who}</td>'


def _row(away: str, home: str, s_away: str | None, s_home: str | None) -> str:
    return (f"<tr>{_side('40%', s_away)}<td><img src=\"http://x/moneypuck/logos/{away}.png\"></td>"
            f"<td>07:00 PM ET</td><td><img src=\"http://x/moneypuck/logos/{home}.png\"></td>"
            f"{_side('60%', s_home)}</tr>")


PAGE = (_row("FLA", "CBJ", "Bobrovsky: 54.2%", "Greaves: 88%")
        + _row("VGK", "NSH", None, None))  # match commencé : plus de partant


def test_page_moneypuck_visiteur_a_gauche_receveur_a_droite():
    assert moneypuck.parse_starters(PAGE) == {"FLA": ("Bobrovsky", pytest.approx(0.542)),
                                              "CBJ": ("Greaves", pytest.approx(0.88))}


def _g(espn_id: int, name: str, team: str) -> dict:
    return {"espn_id": espn_id, "name": name, "pos": "G", "slot": "G", "pro_team": team}


LEAGUE = {"teams": [{"team_id": 5, "roster": [_g(1, "Jet Greaves", "CBJ"), _g(3, "Juuse Saros", "NSH")]},
                    {"team_id": 6, "roster": [_g(2, "Elvis Merzļikins", "CBJ")]}]}


def test_partant_nomme_et_l_autre_gardien_de_son_equipe():
    p = partants.p_start(LEAGUE, {"CBJ": ("Greaves", 0.88)})
    assert p == {1: 0.88, 2: pytest.approx(0.12)}


def test_accents_ignores():
    assert partants.p_start(LEAGUE, {"CBJ": ("Merzlikins", 0.7)}) == {2: 0.7, 1: pytest.approx(0.3)}


def test_points_attendus_selon_la_chance_de_commencer(monkeypatch):
    monkeypatch.setattr(moneypuck, "fetch_starters", lambda day: {"CBJ": ("Greaves", 0.88)})
    out = partants.load(DAY, LEAGUE, {"CBJ": (3.4, 2.8)})
    assert out[1] == (0.88, pytest.approx(0.88 * model.goalie_points(3.4, 2.8)))
    assert soiree.tonight_rate(LEAGUE["teams"][0]["roster"][0], {}, None, out) == out[1][1]


def test_match_commence_garde_la_chance_d_avant_match(monkeypatch):
    monkeypatch.setattr(moneypuck, "fetch_starters", lambda day: {})
    current = {"date": DAY.isoformat(), "teams": [{"players": [{"espn_id": 3, "p_start": 0.9}]}]}
    out = partants.load(DAY, LEAGUE, {}, current)
    assert out == {3: (0.9, pytest.approx(0.9 * model.goalie_points(LEAGUE_GOALS, LEAGUE_GOALS)))}


def test_sans_moneypuck_le_rythme_reste(monkeypatch):
    def down(day):
        raise RuntimeError("panne")
    monkeypatch.setattr(moneypuck, "fetch_starters", down)
    assert partants.load(DAY, LEAGUE, {}) == {}
    hier = {"date": "2026-10-12", "teams": [{"players": [{"espn_id": 3, "p_start": 1}]}]}
    assert partants.load(DAY, LEAGUE, {}, hier) == {}
