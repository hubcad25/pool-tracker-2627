"""infra/aws/proxy_lnh.py : liste blanche et CORS du relais vers l'API de la LNH."""
import importlib.util
import io
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("proxy_lnh", Path(__file__).parents[1] / "infra/aws/proxy_lnh.py")
proxy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proxy)


def event(path, method="GET", origin="https://hubcad25.github.io"):
    return {"rawPath": path, "headers": {"origin": origin}, "requestContext": {"http": {"method": method}}}


class Reponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def lnh(monkeypatch):
    urls = []

    def urlopen(req, timeout):
        urls.append(req.full_url)
        return Reponse(b'{"games": []}')

    monkeypatch.setattr(proxy.urllib.request, "urlopen", urlopen)
    return urls


@pytest.mark.parametrize("path", ["/v1/score/now", "/v1/score/2026-10-12", "/v1/gamecenter/2026020088/boxscore"])
def test_relaie_les_chemins_permis_avec_cors_et_cache_court(lnh, path):
    r = proxy.handler(event(path), None)
    assert r["statusCode"] == 200 and r["body"] == '{"games": []}'
    assert r["headers"]["Access-Control-Allow-Origin"] == "https://hubcad25.github.io"
    assert r["headers"]["Cache-Control"] == "public, max-age=20"
    assert lnh == ["https://api-web.nhle.com" + path]


@pytest.mark.parametrize("path", ["/v1/roster/MTL/current", "/v1/score/now/../../x", "/v1/gamecenter/1/boxscore",
                                  "/v1/score/2026-10-12?x=1", "/"])
def test_ne_relaie_rien_d_autre(lnh, path):
    assert proxy.handler(event(path), None)["statusCode"] == 404
    assert lnh == []


def test_ne_relaie_pas_les_post(lnh):
    assert proxy.handler(event("/v1/score/now", method="POST"), None)["statusCode"] == 404
    assert lnh == []


def test_pas_d_en_tete_cors_pour_une_autre_origine(lnh):
    r = proxy.handler(event("/v1/score/now", origin="https://ailleurs.example"), None)
    assert "Access-Control-Allow-Origin" not in r["headers"]


def test_preflight_options(lnh):
    r = proxy.handler(event("/v1/score/now", method="OPTIONS", origin="http://localhost:5173"), None)
    assert r["statusCode"] == 204 and r["headers"]["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert lnh == []
