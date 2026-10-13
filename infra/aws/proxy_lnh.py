"""Lambda AWS : relais CORS vers l'API de la LNH, pour le direct de la PWA (api-web.nhle.com n'envoie pas de CORS).

Ne relaie que des GET en liste blanche : `v1/score/{date}`, `v1/score/now`, `v1/gamecenter/{id}/boxscore` et
`v1/gamecenter/{id}/play-by-play` (tirs par zone du détail d'un joueur).
Réponse mise en cache ~20 s (comme la LNH). Python 3.13, aucune dépendance.

Déploiement (console AWS, région au choix, ex. ca-central-1) :
1. Lambda → Créer une fonction → « Créer à partir de zéro », nom `pool-tracker-proxy-lnh`, Python 3.13.
2. Coller ce fichier dans `lambda_function.py`, gestionnaire `lambda_function.handler`, puis « Deploy ».
   Configuration → Configuration générale : délai d'attente 10 s (128 Mo suffisent).
3. Configuration → URL de fonction → Créer : type d'authentification `NONE`. **Ne pas activer le CORS de l'URL de
   fonction** (le code gère lui-même `Access-Control-Allow-Origin` ; les deux ensemble doublent l'en-tête).
4. Copier l'URL (https://xxxx.lambda-url.ca-central-1.on.aws/) :
   - dans app/.env.local (non commité) : `VITE_LNH_PROXY=https://xxxx.lambda-url.ca-central-1.on.aws`
   - dans GitHub : Settings → Secrets and variables → Actions → Variables → `LNH_PROXY` (lu par pages.yml).
5. Test : `curl -H 'Origin: https://hubcad25.github.io' https://xxxx.../v1/score/now -i` (200 + l'en-tête CORS).

En CLI (rôle d'exécution `pool-soiree-lambda` déjà créé, avec AWSLambdaBasicExecutionRole) :
    cp infra/aws/proxy_lnh.py lambda_function.py && zip proxy.zip lambda_function.py
    aws lambda create-function --function-name pool-tracker-proxy-lnh --runtime python3.13 --timeout 10 \\
        --handler lambda_function.handler --zip-file fileb://proxy.zip \\
        --role arn:aws:iam::<compte>:role/pool-soiree-lambda
    aws lambda create-function-url-config --function-name pool-tracker-proxy-lnh --auth-type NONE
    aws lambda add-permission --function-name pool-tracker-proxy-lnh --statement-id url-public \\
        --action lambda:InvokeFunctionUrl --principal '*' --function-url-auth-type NONE
    # Depuis oct. 2025, une URL publique exige aussi lambda:InvokeFunction :
    aws lambda add-permission --function-name pool-tracker-proxy-lnh --statement-id url-public-invoke \\
        --action lambda:InvokeFunction --principal '*'

Coût : ~1 requête par minute et par appareil pendant les matchs, largement dans l'offre gratuite.
"""
import re
import urllib.error
import urllib.request

UPSTREAM = "https://api-web.nhle.com/"
ALLOWED = re.compile(r"^/?(v1/score/(now|\d{4}-\d{2}-\d{2})|v1/gamecenter/\d{10}/(boxscore|play-by-play))$")
ORIGINS = {"https://hubcad25.github.io", "http://localhost:5173", "http://192.168.18.12:5173"}
MAX_AGE = 20


def _headers(origin: str | None) -> dict[str, str]:
    h = {"Vary": "Origin"}
    if origin in ORIGINS:
        h |= {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "GET",
              "Access-Control-Max-Age": "86400"}
    return h


def _reply(status: int, origin: str | None, body: str = "", extra: dict | None = None) -> dict:
    return {"statusCode": status, "headers": _headers(origin) | (extra or {}), "body": body}


def handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method", "GET")
    path = event.get("rawPath") or http.get("path") or ""
    origin = {k.lower(): v for k, v in (event.get("headers") or {}).items()}.get("origin")
    if method == "OPTIONS":
        return _reply(204, origin)
    if method != "GET" or not ALLOWED.match(path):
        return _reply(404, origin, "introuvable")
    # Pas de query string : le chemin suffit, et rien d'autre ne passe
    req = urllib.request.Request(UPSTREAM + path.lstrip("/"), headers={"User-Agent": "pool-tracker-2627"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:  # suit la redirection de score/now
            body = r.read().decode()
            status = r.status
    except urllib.error.HTTPError as e:
        return _reply(e.code, origin, "", {"Cache-Control": "no-store"})
    except (urllib.error.URLError, TimeoutError):
        return _reply(502, origin, "LNH injoignable", {"Cache-Control": "no-store"})
    return _reply(status, origin, body, {"Content-Type": "application/json",
                                         "Cache-Control": f"public, max-age={MAX_AGE}"})
