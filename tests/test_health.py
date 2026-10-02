"""Alertes de santé du pipeline."""
import pytest

from pipeline import main, notify


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "MONEYPUCK_HEALTH", tmp_path / "moneypuck.json")
    monkeypatch.setattr(notify, "SENT", tmp_path / "sent.json")


def test_moneypuck_ne_notifie_pas_une_seule_journee_de_panne():
    assert main.moneypuck_health(ok=False) == []


def test_moneypuck_notifie_au_deuxieme_jour_de_panne():
    main.moneypuck_health(ok=False)
    [e] = main.moneypuck_health(ok=False)
    assert e.kind == "health" and e.key == "moneypuck_down"


def test_moneypuck_un_retour_remet_le_compteur_a_zero():
    main.moneypuck_health(ok=False)
    assert main.moneypuck_health(ok=True) == []
    assert main.moneypuck_health(ok=False) == []


def test_moneypuck_alerte_rearmee_apres_un_retour():
    notify.save_sent({"moneypuck_down"})
    main.moneypuck_health(ok=True)
    assert "moneypuck_down" not in notify.load_sent()
