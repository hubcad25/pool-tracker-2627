"""Lambda AWS : lance le workflow `soiree.yml` aux 15 min (le cron GitHub saute des heures).

Déclenchée par EventBridge Scheduler, `rate(15 minutes)`. Python 3.13, aucune dépendance.
Variables d'environnement :
- GITHUB_TOKEN : jeton fine-grained, repo pool-tracker-2627 seulement, permission « Actions : Read and write »
- TARGET : topic ntfy (test | prod), « test » par défaut
"""
import json
import os
import urllib.request

URL = "https://api.github.com/repos/hubcad25/pool-tracker-2627/actions/workflows/soiree.yml/dispatches"


def handler(event, context):
    body = {"ref": "main", "inputs": {"target": os.environ.get("TARGET", "test")}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        return {"status": r.status}  # 204 : workflow lancé
