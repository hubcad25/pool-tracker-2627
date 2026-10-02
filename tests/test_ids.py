import pytest

from pipeline import ids


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(ids, "ID_MAP", tmp_path / "id_map.csv")
    monkeypatch.setattr(ids, "OVERRIDES", tmp_path / "id_overrides.csv")
    monkeypatch.setattr(ids, "load_prior_ids", lambda: {"seth_jarvis", "elias_pettersson",
                                                        "elias_pettersson_(d)", "zack_bolduc"})
    monkeypatch.setattr(ids, "load_aliases", lambda: {"zachary bolduc": "zack bolduc"})
    return tmp_path


def espn(espn_id, name, pos="C", team="CAR"):
    return {"espn_id": espn_id, "name": name, "pos": pos, "pro_team": team}


def nhl(nhl_id, name, pos="C", team="CAR"):
    return {"nhl_id": nhl_id, "name": name, "pos": pos, "team": team}


def test_normalize_name():
    assert ids.normalize_name("Jean-Gabriel Pageau") == "jean gabriel pageau"
    assert ids.normalize_name("Tim Stützle") == "tim stutzle"
    assert ids.normalize_name("Martin St. Louis Jr.") == "martin st louis"


def test_homonymes_departages_par_position(paths):
    roster = [nhl(1, "Elias Pettersson", "C", "VAN"), nhl(2, "Elias Pettersson", "D", "VAN")]
    out = ids.update_map([espn(10, "Elias Pettersson", "D", "VAN")], roster)
    assert out[10]["nhl_id"] == "2"
    assert out[10]["method"] == "name+pos"
    assert out[10]["canonical_id"] == "elias_pettersson_(d)"


def test_abreviation_espn_convertie_pour_departager(paths):
    roster = [nhl(1, "Jack Hughes", team="NJD"), nhl(2, "Jack Hughes", team="BOS")]
    assert ids.update_map([espn(10, "Jack Hughes", team="NJ")], roster)[10]["nhl_id"] == "1"


def test_alias(paths):
    out = ids.update_map([espn(10, "Zachary Bolduc", "LW", "MTL")], [nhl(5, "Zack Bolduc", "L", "MTL")])
    assert (out[10]["nhl_id"], out[10]["canonical_id"]) == ("5", "zack_bolduc")


def test_recherche_seulement_pour_les_joueurs_qui_comptent(paths):
    calls = []

    def search(name):
        calls.append(name)
        return [nhl(8482093, "Seth Jarvis", "R")]

    players = [espn(10, "Seth Jarvis", "RW"), espn(11, "Obscure Prospect")]
    out = ids.update_map(players, [], search=search, worth_search=lambda p: p["espn_id"] == 10)
    assert calls == ["Seth Jarvis"]
    assert out[10]["nhl_id"] == "8482093"
    assert out[11]["nhl_id"] == ""


def test_association_existante_jamais_modifiee(paths):
    ids.update_map([espn(10, "Seth Jarvis", "RW")], [nhl(1, "Seth Jarvis", "R")])
    out = ids.update_map([espn(10, "Seth Jarvis", "RW")], [nhl(2, "Seth Jarvis", "R")])
    assert out[10]["nhl_id"] == "1"


def test_override_manuel_a_priorite(paths):
    (paths / "id_overrides.csv").write_text("espn_id,nhl_id,canonical_id,name,method\n10,999,,X,\n")
    out = ids.update_map([espn(10, "Seth Jarvis", "RW")], [nhl(1, "Seth Jarvis", "R")])
    assert (out[10]["nhl_id"], out[10]["canonical_id"], out[10]["method"]) == ("999", "seth_jarvis", "manual")


def test_missing_signale_les_trous_et_ignore_le_prior_des_gardiens(paths):
    players = [espn(10, "Seth Jarvis", "RW"), espn(11, "Inconnu"), espn(12, "Un Gardien", "G")]
    out = ids.update_map(players, [nhl(1, "Seth Jarvis", "R"), nhl(3, "Un Gardien", "G")])
    assert [(p["espn_id"], p["missing"]) for p in ids.missing(out, players)] == [
        (11, ["nhl_id", "canonical_id"])]
