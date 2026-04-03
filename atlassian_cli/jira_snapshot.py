import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .adf import adf_to_text
from .config import get_jira_cache_root
from .jira_api import (
    DEFAULT_ISSUE_FIELDS,
    download_attachment,
    get_issue,
    get_issue_changelog,
    get_issue_comments,
    search_all_issues,
)
ACTIVE_EXCLUDED_STATUSES = {
    "Released",
    "Passed QA",
    "Closed",
    "Sub-task Closed",
}


def issue_dir(issue_key: str) -> Path:
    return get_jira_cache_root() / issue_key


def assigned_dir() -> Path:
    return get_jira_cache_root() / "assigned"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def summarize_issue_fields(issue: dict) -> dict:
    fields = issue.get("fields", {})
    return {
        "key": issue.get("key"),
        "id": issue.get("id"),
        "summary": fields.get("summary"),
        "status": _name(fields.get("status")),
        "priority": _name(fields.get("priority")),
        "issuetype": _name(fields.get("issuetype")),
        "project": _project(fields.get("project")),
        "assignee": _display_name(fields.get("assignee")),
        "reporter": _display_name(fields.get("reporter")),
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "resolution": _name(fields.get("resolution")),
        "labels": fields.get("labels", []),
        "attachmentCount": len(fields.get("attachment", []) or []),
    }


def fetch_issue_bundle(issue_key: str) -> dict:
    issue = get_issue(issue_key, fields=DEFAULT_ISSUE_FIELDS)
    comments = get_issue_comments(issue_key)
    changelog = get_issue_changelog(issue_key)
    return {
        "issue": issue,
        "fields": summarize_issue_fields(issue),
        "comments": comments,
        "changelog": changelog,
    }


def write_issue_snapshot(issue_key: str, include_attachments: bool = True) -> Dict[str, str]:
    bundle = fetch_issue_bundle(issue_key)
    target_dir = ensure_dir(issue_dir(issue_key))
    attachments_dir = ensure_dir(target_dir / "attachments")

    _write_json(target_dir / "issue.json", bundle["issue"])
    _write_json(target_dir / "fields.json", bundle["fields"])
    _write_json(target_dir / "comments.json", bundle["comments"])
    _write_json(target_dir / "changelog.json", bundle["changelog"])

    (target_dir / "summary.md").write_text(render_summary_md(bundle["issue"]), encoding="utf-8")
    (target_dir / "comments.md").write_text(render_comments_md(issue_key, bundle["comments"]), encoding="utf-8")
    (target_dir / "history.md").write_text(render_history_md(issue_key, bundle["changelog"]), encoding="utf-8")

    attachment_manifest: List[dict] = []
    if include_attachments:
        attachment_manifest = download_issue_attachments(bundle["issue"], attachments_dir)
    _write_json(target_dir / "attachments.json", attachment_manifest)

    return {
        "issueKey": issue_key,
        "dir": str(target_dir),
        "issue": str(target_dir / "issue.json"),
        "fields": str(target_dir / "fields.json"),
        "summary": str(target_dir / "summary.md"),
        "comments": str(target_dir / "comments.md"),
        "history": str(target_dir / "history.md"),
        "attachmentsDir": str(attachments_dir),
        "attachmentsDownloaded": str(len(attachment_manifest)),
    }


def pull_assigned_snapshots(include_all: bool = False, include_attachments: bool = True, limit: Optional[int] = None) -> Dict[str, object]:
    issues = search_all_issues(
        "assignee = currentUser() ORDER BY updated DESC",
        fields=DEFAULT_ISSUE_FIELDS,
    )
    if not include_all:
        issues = [
            issue
            for issue in issues
            if issue.get("fields", {}).get("status", {}).get("name") not in ACTIVE_EXCLUDED_STATUSES
        ]
    if limit is not None:
        issues = issues[:limit]

    out_dir = ensure_dir(assigned_dir())
    pulled = []
    for issue in issues:
        pulled.append(write_issue_snapshot(issue["key"], include_attachments=include_attachments))

    inventory = {
        "mode": "all" if include_all else "active",
        "excludedStatuses": [] if include_all else sorted(ACTIVE_EXCLUDED_STATUSES),
        "totalPulled": len(pulled),
        "issues": [summarize_issue_fields(issue) for issue in issues],
    }
    _write_json(out_dir / "inventory.json", inventory)
    (out_dir / "inventory.md").write_text(render_inventory_md(inventory), encoding="utf-8")

    return {
        "dir": str(out_dir),
        "mode": inventory["mode"],
        "totalPulled": inventory["totalPulled"],
        "inventoryJson": str(out_dir / "inventory.json"),
        "inventoryMd": str(out_dir / "inventory.md"),
    }


def download_issue_attachments(issue: dict, attachments_dir: Path) -> List[dict]:
    manifest: List[dict] = []
    fields = issue.get("fields", {})
    for attachment in fields.get("attachment", []) or []:
        filename = attachment.get("filename", "attachment.bin")
        safe_name = _safe_filename(filename)
        local_name = f"{attachment.get('id', 'attachment')}-{safe_name}"
        local_path = attachments_dir / local_name
        local_path.write_bytes(download_attachment(attachment["content"]))
        manifest.append(
            {
                "id": attachment.get("id"),
                "filename": filename,
                "mimeType": attachment.get("mimeType"),
                "size": attachment.get("size"),
                "created": attachment.get("created"),
                "author": _display_name(attachment.get("author")),
                "localPath": str(local_path),
                "contentUrl": attachment.get("content"),
            }
        )
    return manifest


def render_summary_md(issue: dict) -> str:
    fields = issue.get("fields", {})
    summary = fields.get("summary", "")
    description = adf_to_text(fields.get("description")).strip()
    lines = [
        f"# {issue.get('key')}: {summary}",
        "",
        "## Fields",
        "",
        f"- Status: `{_name(fields.get('status'))}`",
        f"- Priority: `{_name(fields.get('priority'))}`",
        f"- Type: `{_name(fields.get('issuetype'))}`",
        f"- Project: `{_project(fields.get('project'))}`",
        f"- Assignee: `{_display_name(fields.get('assignee'))}`",
        f"- Reporter: `{_display_name(fields.get('reporter'))}`",
        f"- Created: `{fields.get('created', '')}`",
        f"- Updated: `{fields.get('updated', '')}`",
        f"- Resolution: `{_name(fields.get('resolution'))}`",
        f"- Labels: `{', '.join(fields.get('labels', []))}`",
        "",
        "## Description",
        "",
    ]
    if description:
        lines.append(description)
    else:
        lines.append("_No description_")
    lines.append("")
    return "\n".join(lines)


def render_comments_md(issue_key: str, comments: Iterable[dict]) -> str:
    comments = list(comments)
    lines = [f"# {issue_key} Comments", ""]
    if not comments:
        lines.append("_No comments_")
        lines.append("")
        return "\n".join(lines)
    for idx, comment in enumerate(comments, start=1):
        author = _display_name(comment.get("author"))
        created = comment.get("created", "")
        updated = comment.get("updated", "")
        body = adf_to_text(comment.get("body")).strip() or "_Empty comment_"
        lines.extend(
            [
                f"## {idx}. {author}",
                "",
                f"- Created: `{created}`",
                f"- Updated: `{updated}`",
                "",
                body,
                "",
            ]
        )
    return "\n".join(lines)


def render_history_md(issue_key: str, changelog: Iterable[dict]) -> str:
    histories = list(changelog)
    lines = [f"# {issue_key} History", ""]
    if not histories:
        lines.append("_No changelog entries_")
        lines.append("")
        return "\n".join(lines)
    for entry in histories:
        author = _display_name(entry.get("author"))
        created = entry.get("created", "")
        lines.append(f"## {created} - {author}")
        lines.append("")
        items = entry.get("items", []) or []
        if not items:
            lines.append("- No field-level changes captured")
        for item in items:
            field = item.get("field", "unknown")
            from_string = item.get("fromString")
            to_string = item.get("toString")
            lines.append(f"- `{field}`: `{from_string}` -> `{to_string}`")
        lines.append("")
    return "\n".join(lines)


def render_inventory_md(inventory: dict) -> str:
    lines = [
        "# Jira Assigned Snapshot",
        "",
        f"Mode: `{inventory.get('mode')}`",
        f"Total pulled: `{inventory.get('totalPulled')}`",
    ]
    excluded = inventory.get("excludedStatuses") or []
    if excluded:
        lines.append(f"Excluded statuses: `{', '.join(excluded)}`")
    lines.append("")
    for issue in inventory.get("issues", []):
        lines.append(
            f"- `{issue.get('key')}` [{issue.get('project')}] `{issue.get('status')}` `{issue.get('priority')}`: {issue.get('summary')}"
        )
    lines.append("")
    return "\n".join(lines)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _name(obj: Optional[dict]) -> str:
    return (obj or {}).get("name", "")


def _project(obj: Optional[dict]) -> str:
    if not obj:
        return ""
    key = obj.get("key", "")
    name = obj.get("name", "")
    return f"{key} - {name}" if key and name else key or name


def _display_name(obj: Optional[dict]) -> str:
    return (obj or {}).get("displayName", "")


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    return cleaned or "attachment"
