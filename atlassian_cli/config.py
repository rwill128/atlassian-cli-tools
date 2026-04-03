import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "atlassian-cli" / "config.json"
LEGACY_CONFIG_PATH = Path.home() / ".config" / "tillster-atlassian" / "config.json"
DEFAULT_JIRA_CACHE_ROOT = Path.home() / ".local" / "share" / "atlassian-cli" / "jira"
LEGACY_JIRA_CACHE_ROOT = Path.home() / "tillster" / ".jira"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


@dataclass
class AtlassianConfig:
    base_url: str
    email: str
    api_token: str
    jira_cache_root: Path


def _config_path_candidates() -> list[Path]:
    explicit = os.environ.get("ATLASSIAN_CONFIG_PATH")
    if explicit:
        return [Path(explicit).expanduser()]
    return [DEFAULT_CONFIG_PATH, LEGACY_CONFIG_PATH]


def _load_file_config() -> dict:
    for path in _config_path_candidates():
        if path.exists():
            return json.loads(path.read_text())
    return {}


def _load_dotenv() -> dict:
    if not ENV_PATH.exists():
        return {}

    result = {}
    for raw_line in ENV_PATH.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip("'").strip('"')
    return result


def _first_value(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value:
            return value
    return None


def get_jira_cache_root() -> Path:
    file_cfg = _load_file_config()
    dotenv_cfg = _load_dotenv()
    configured = _first_value(
        os.environ.get("ATLASSIAN_CLI_CACHE_ROOT"),
        os.environ.get("TILLSTER_ATLASSIAN_CACHE_ROOT"),
        dotenv_cfg.get("ATLASSIAN_CLI_CACHE_ROOT"),
        dotenv_cfg.get("TILLSTER_ATLASSIAN_CACHE_ROOT"),
        file_cfg.get("jira_cache_root"),
    )
    if configured:
        return Path(configured).expanduser()
    if LEGACY_JIRA_CACHE_ROOT.exists():
        return LEGACY_JIRA_CACHE_ROOT
    return DEFAULT_JIRA_CACHE_ROOT


def load_config() -> AtlassianConfig:
    file_cfg = _load_file_config()
    dotenv_cfg = _load_dotenv()

    base_url = _first_value(
        os.environ.get("ATLASSIAN_BASE_URL"),
        os.environ.get("TILLSTER_ATLASSIAN_BASE_URL"),
        dotenv_cfg.get("ATLASSIAN_BASE_URL"),
        dotenv_cfg.get("TILLSTER_ATLASSIAN_BASE_URL"),
        file_cfg.get("base_url"),
    )
    email = _first_value(
        os.environ.get("ATLASSIAN_EMAIL"),
        os.environ.get("TILLSTER_ATLASSIAN_EMAIL"),
        dotenv_cfg.get("ATLASSIAN_EMAIL"),
        dotenv_cfg.get("TILLSTER_ATLASSIAN_EMAIL"),
        file_cfg.get("email"),
    )
    api_token = _first_value(
        os.environ.get("ATLASSIAN_API_TOKEN"),
        os.environ.get("TILLSTER_ATLASSIAN_API_TOKEN"),
        dotenv_cfg.get("ATLASSIAN_API_TOKEN"),
        dotenv_cfg.get("TILLSTER_ATLASSIAN_API_TOKEN"),
        file_cfg.get("api_token"),
    )

    if not base_url or not email or not api_token:
        raise SystemExit(
            "Missing Atlassian config. Set ATLASSIAN_BASE_URL, ATLASSIAN_EMAIL, and "
            "ATLASSIAN_API_TOKEN, or populate ~/.config/atlassian-cli/config.json. "
            "Legacy TILLSTER_ATLASSIAN_* variables and ~/.config/tillster-atlassian/config.json "
            "are also supported."
        )

    return AtlassianConfig(
        base_url=base_url.rstrip("/"),
        email=email,
        api_token=api_token,
        jira_cache_root=get_jira_cache_root(),
    )
