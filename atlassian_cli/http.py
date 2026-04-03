import base64
import json
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from .config import load_config


def _auth_header(email: str, api_token: str) -> str:
    raw = f"{email}:{api_token}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def request_json(
    path: str,
    params: Optional[Dict] = None,
    *,
    method: str = "GET",
    body: Optional[Any] = None,
) -> dict:
    cfg = load_config()
    url = cfg.base_url + path
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"

    payload = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Authorization": _auth_header(cfg.email, cfg.api_token),
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(request) as response:
        body = response.read().decode()
        return json.loads(body) if body else {}


def request_bytes(url_or_path: str, params: Optional[Dict] = None) -> bytes:
    cfg = load_config()
    url = url_or_path
    if not url.startswith("http://") and not url.startswith("https://"):
        url = cfg.base_url + url_or_path
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": _auth_header(cfg.email, cfg.api_token),
            "Accept": "*/*",
        },
    )

    with urllib.request.urlopen(request) as response:
        return response.read()
