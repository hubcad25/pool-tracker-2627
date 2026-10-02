import pytest

from pipeline import events, notify
from pipeline.events import Event


@pytest.fixture(autouse=True)
def sent_file(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "SENT", tmp_path / "sent.json")


@pytest.fixture
def posted(monkeypatch):
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

    monkeypatch.setenv("NTFY_TOPIC_TEST", "topic-test")
    monkeypatch.setattr(notify.requests, "post", lambda url, json, timeout: calls.append(json) or Resp())
    return calls


def test_rien_a_envoyer():
    assert notify.send([], dry_run=True) is None


def test_une_seule_notif_par_execution_priorite_max_en_tete(posted):
    evts = [Event("status", "a", "Jarvis → IR"), Event("fa_alert", "b", "FA : prendre X", events.MAX)]
    notify.send(evts, dry_run=False)
    assert len(posted) == 1
    assert posted[0]["priority"] == events.MAX
    assert posted[0]["message"].splitlines()[0] == "• FA : prendre X"
    assert posted[0]["topic"] == "topic-test"


def test_meme_cle_jamais_renvoyee(posted):
    evt = Event("status", "jarvis:IR", "Jarvis → IR")
    notify.send([evt], dry_run=False)
    assert notify.send([evt], dry_run=False) is None
    assert len(posted) == 1


def test_dry_run_n_enregistre_rien(posted):
    evt = Event("status", "jarvis:IR", "Jarvis → IR")
    notify.send([evt], dry_run=True)
    assert posted == []
    assert notify.load_sent() == set()


def test_forget_rearme_l_alerte_cookies(posted):
    notify.send([events.cookies_expired()], dry_run=False)
    notify.forget("cookies_expired")
    notify.send([events.cookies_expired()], dry_run=False)
    assert len(posted) == 2
