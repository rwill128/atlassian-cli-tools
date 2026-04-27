import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from .config import load_config


class AtlassianHttpError(RuntimeError):
    pass


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

    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise AtlassianHttpError(_format_http_error(exc, method, url, body)) from exc


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

    try:
        with urllib.request.urlopen(request) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise AtlassianHttpError(_format_http_error(exc, "GET", url, body)) from exc


def _format_http_error(exc: urllib.error.HTTPError, method: str, url: str, body: str) -> str:
    lines = [f"HTTP {exc.code} {exc.reason}: {method} {url}"]
    if body:
        lines.append(_pretty_json_or_raw(body))
    return "\n".join(lines)


def _pretty_json_or_raw(body: str) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body
    return json.dumps(parsed, indent=2, sort_keys=True)
