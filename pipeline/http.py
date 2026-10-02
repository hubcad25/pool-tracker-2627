import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (pool-tracker-2627)"}


class AuthError(Exception):
    """La ligue ESPN refuse les cookies (expirés ou invalides)."""


def get(url: str, *, headers: dict | None = None, cookies: dict | None = None,
        retries: int = 3, timeout: int = 30) -> requests.Response:
    for attempt in range(retries):
        try:
            r = requests.get(url, headers={**HEADERS, **(headers or {})}, cookies=cookies, timeout=timeout)
            if r.status_code in (401, 403) and cookies:
                raise AuthError(f"{r.status_code} sur {url}")
            if r.status_code < 500:
                r.raise_for_status()
                return r
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries - 1:
                raise
        time.sleep(2 ** attempt * 5)
    r.raise_for_status()
    return r


def get_json(url: str, **kwargs):
    return get(url, **kwargs).json()
