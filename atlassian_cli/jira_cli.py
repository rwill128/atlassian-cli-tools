import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .adf import text_to_adf
from .formatting import dump_json
from .http import request_json
from .jira_api import create_issue, get_issue_changelog, get_issue_comments, search_users
from .jira_snapshot import (
    ACTIVE_EXCLUDED_STATUSES,
    download_issue_attachments,
    fetch_issue_bundle,
    ensure_dir,
    issue_dir,
    pull_assigned_snapshots,
    render_comments_md,
    render_history_md,
    write_issue_snapshot,
)

DEFAULT_ASSIGNED_FIELDS = "summary,status,assignee,reporter,issuetype,project,created,updated,priority"


def cmd_whoami(_: argparse.Namespace) -> int:
    data = request_json("/rest/api/3/myself")
    dump_json(
        {
            "accountId": data.get("accountId"),
            "displayName": data.get("displayName"),
            "emailAddress": data.get("emailAddress"),
            "active": data.get("active"),
        }
    )
    return 0


def cmd_projects(args: argparse.Namespace) -> int:
    data = request_json("/rest/api/3/project/search", params={"maxResults": args.limit})
    dump_json(
        {
            "total": data.get("total"),
            "values": [
                {
                    "key": item.get("key"),
                    "name": item.get("name"),
                    "projectTypeKey": item.get("projectTypeKey"),
                    "simplified": item.get("simplified"),
                }
                for item in data.get("values", [])
            ],
        }
    )
    return 0


def cmd_issue(args: argparse.Namespace) -> int:
    data = request_json(
        f"/rest/api/3/issue/{args.key}",
        params={"fields": args.fields},
    )
    dump_json(data)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    data = request_json(
        "/rest/api/3/search/jql",
        params={
            "jql": args.jql,
            "maxResults": args.limit,
            "fields": args.fields,
        },
    )
    dump_json(data)
    return 0


def _search_all_issues(jql: str, max_results: int, fields: str) -> List[dict]:
    params: Dict[str, object] = {
        "jql": jql,
        "maxResults": max_results,
        "fields": fields,
    }
    issues: List[dict] = []
    while True:
        data = request_json("/rest/api/3/search/jql", params=params)
        issues.extend(data.get("issues", []))
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields,
            "nextPageToken": next_page_token,
        }
    return issues


def cmd_assigned(args: argparse.Namespace) -> int:
    issues = _search_all_issues(
        "assignee = currentUser() ORDER BY updated DESC",
        max_results=100,
        fields=args.fields,
    )
    filtered_issues = issues
    excluded_statuses = []
    if not args.all:
        excluded_statuses = sorted(ACTIVE_EXCLUDED_STATUSES)
        filtered_issues = [
            issue
            for issue in issues
            if issue.get("fields", {}).get("status", {}).get("name") not in ACTIVE_EXCLUDED_STATUSES
        ]

    if args.limit is not None:
        filtered_issues = filtered_issues[: args.limit]

    dump_json(
        {
            "mode": "all" if args.all else "active",
            "excludedStatuses": excluded_statuses,
            "totalAssigned": len(issues),
            "totalReturned": len(filtered_issues),
            "issues": filtered_issues,
        }
    )
    return 0


def cmd_comments(args: argparse.Namespace) -> int:
    comments = get_issue_comments(args.key)
    if args.json:
        dump_json(comments)
        return 0
    print(render_comments_md(args.key, comments), end="")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    changelog = get_issue_changelog(args.key)
    if args.json:
        dump_json(changelog)
        return 0
    print(render_history_md(args.key, changelog), end="")
    return 0


def cmd_attachments(args: argparse.Namespace) -> int:
    issue = fetch_issue_bundle(args.key)["issue"]
    manifest = download_issue_attachments(issue, ensure_dir(args.dir))
    dump_json(
        {
            "issueKey": args.key,
            "dir": str(args.dir),
            "downloaded": len(manifest),
            "attachments": manifest,
        }
    )
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    result = write_issue_snapshot(args.key, include_attachments=not args.no_attachments)
    dump_json(result)
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    result = write_issue_snapshot(args.key, include_attachments=not args.no_attachments)
    dump_json(result)
    return 0


def cmd_pull_assigned(args: argparse.Namespace) -> int:
    result = pull_assigned_snapshots(
        include_all=args.all,
        include_attachments=not args.no_attachments,
        limit=args.limit,
    )
    dump_json(result)
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    fields: Dict[str, Any] = {
        "project": {"key": args.project},
        "summary": args.summary,
        "issuetype": {"name": args.type},
    }

    description_text = _read_description_text(args)
    if description_text is not None:
        fields["description"] = text_to_adf(description_text)

    if args.assignee:
        fields["assignee"] = {"accountId": _resolve_account_id(args.assignee)}

    if args.priority:
        fields["priority"] = {"name": args.priority}

    if args.parent:
        fields["parent"] = {"key": args.parent}

    if args.dry_run:
        dump_json({"dryRun": True, "payload": {"fields": fields}})
        return 0

    created = create_issue(fields)
    dump_json(created)
    return 0


def _read_description_text(args: argparse.Namespace) -> Optional[str]:
    if args.description is not None:
        return args.description
    if args.description_file is None:
        return None
    if args.description_file == "-":
        return sys.stdin.read()
    return Path(args.description_file).read_text(encoding="utf-8")


def _resolve_account_id(assignee: str) -> str:
    if assignee == "current":
        data = request_json("/rest/api/3/myself")
        account_id = data.get("accountId")
        if account_id:
            return account_id
        raise ValueError("Could not resolve current Jira user accountId")

    if "@" not in assignee:
        return assignee

    matches = search_users(assignee)
    for match in matches:
        if match.get("emailAddress", "").lower() == assignee.lower():
            account_id = match.get("accountId")
            if account_id:
                return account_id

    raise ValueError(f"Could not resolve Jira assignee email: {assignee}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tjira", description="Jira CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    whoami = sub.add_parser("whoami", help="Show the Jira user bound to the configured credentials")
    whoami.set_defaults(func=cmd_whoami)

    projects = sub.add_parser("projects", help="List accessible Jira projects")
    projects.add_argument("--limit", type=int, default=10)
    projects.set_defaults(func=cmd_projects)

    issue = sub.add_parser("issue", help="Fetch a Jira issue by key")
    issue.add_argument("key")
    issue.add_argument("--fields", default="summary,status,assignee,reporter,issuetype,project,description")
    issue.set_defaults(func=cmd_issue)

    create = sub.add_parser("create", help="Create a Jira issue")
    create.add_argument("--project", required=True, help="Project key, for example POSAAS")
    create.add_argument("--summary", required=True, help="Issue summary")
    create.add_argument("--type", required=True, help="Issue type name, for example Story")
    description_group = create.add_mutually_exclusive_group()
    description_group.add_argument("--description", help="Plain-text or markdown-ish description")
    description_group.add_argument(
        "--description-file",
        help="Read description text from a file path, or '-' to read from stdin",
    )
    create.add_argument(
        "--assignee",
        help="Assignee accountId, email address, or 'current' for the configured Jira user",
    )
    create.add_argument("--priority", help="Priority name, for example Major")
    create.add_argument("--parent", help="Parent issue key")
    create.add_argument("--dry-run", action="store_true", help="Print the create payload without posting it")
    create.set_defaults(func=cmd_create)

    comments = sub.add_parser("comments", help="Fetch issue comments")
    comments.add_argument("key")
    comments.add_argument("--json", action="store_true", help="Emit raw comment JSON instead of markdown")
    comments.set_defaults(func=cmd_comments)

    history = sub.add_parser("history", help="Fetch issue changelog/history")
    history.add_argument("key")
    history.add_argument("--json", action="store_true", help="Emit raw changelog JSON instead of markdown")
    history.set_defaults(func=cmd_history)

    attachments = sub.add_parser("attachments", help="Download issue attachments")
    attachments.add_argument("key")
    attachments.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to ~/.jira/<ISSUE>/attachments",
    )
    attachments.set_defaults(func=cmd_attachments)

    assigned = sub.add_parser(
        "assigned",
        help="List tickets assigned to the current user. Defaults to active tickets only.",
    )
    assigned.add_argument(
        "--all",
        action="store_true",
        help="Include done tickets like Released and Passed QA.",
    )
    assigned.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of returned issues after filtering.",
    )
    assigned.add_argument("--fields", default=DEFAULT_ASSIGNED_FIELDS)
    assigned.set_defaults(func=cmd_assigned)

    pull = sub.add_parser(
        "pull",
        help="Fetch an issue into ~/.jira/<ISSUE>/ with issue, comments, history, and attachments.",
    )
    pull.add_argument("key")
    pull.add_argument("--no-attachments", action="store_true")
    pull.set_defaults(func=cmd_pull)

    refresh = sub.add_parser(
        "refresh",
        help="Refresh the existing ~/.jira/<ISSUE>/ snapshot from Jira.",
    )
    refresh.add_argument("key")
    refresh.add_argument("--no-attachments", action="store_true")
    refresh.set_defaults(func=cmd_refresh)

    pull_assigned = sub.add_parser(
        "pull-assigned",
        help="Pull assigned tickets into ~/.jira/assigned and per-ticket folders. Defaults to active tickets only.",
    )
    pull_assigned.add_argument("--all", action="store_true", help="Include Released/Passed QA/etc.")
    pull_assigned.add_argument("--no-attachments", action="store_true")
    pull_assigned.add_argument("--limit", type=int, default=None)
    pull_assigned.set_defaults(func=cmd_pull_assigned)

    search = sub.add_parser("search", help="Run JQL")
    search.add_argument("jql")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--fields", default=DEFAULT_ASSIGNED_FIELDS)
    search.set_defaults(func=cmd_search)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "dir", None) is None and getattr(args, "command", None) == "attachments":
        args.dir = issue_dir(args.key) / "attachments"
    return args.func(args)
