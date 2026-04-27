import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .adf import text_to_adf
from .formatting import dump_json
from .http import AtlassianHttpError, request_json
from .jira_api import (
    add_issue_comment,
    create_issue,
    get_issue_changelog,
    get_issue_comments,
    get_issue_transitions,
    search_users,
    transition_issue,
    update_issue,
    update_issue_comment,
)
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
POSAAS_PROJECT_KEY = "POSAAS"
POSAAS_HR_TYPE_FIELD = "customfield_13102"
POSAAS_HR_TYPE_POS_INTERNAL_OPTION_ID = "14200"
POSAAS_DEFAULT_ORIGINAL_ESTIMATE = "1d"
POSAAS_DEFAULT_ISSUE_TYPE = "Defect"
POSAAS_DEFAULT_PRIORITY = "Major"
POSAAS_ISSUE_TYPE_ALIASES = {
    "defect": "Defect",
    "improve defect": "Defect",
    "bug": "Defect",
}


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


def cmd_add_comment(args: argparse.Namespace) -> int:
    comment_text = _read_comment_text(args)
    if not comment_text.strip():
        raise SystemExit("Comment body cannot be empty")

    body = text_to_adf(comment_text)
    payload = {"body": body}
    if args.dry_run:
        dump_json({"dryRun": True, "issueKey": args.key, "payload": payload})
        return 0

    created = add_issue_comment(args.key, body)
    if args.json:
        dump_json(created)
        return 0

    dump_json(
        {
            "issueKey": args.key,
            "commentId": created.get("id"),
            "self": created.get("self"),
            "created": created.get("created"),
            "author": created.get("author", {}).get("displayName"),
        }
    )
    return 0


def cmd_edit_comment(args: argparse.Namespace) -> int:
    comment_text = _read_comment_text(args)
    if not comment_text.strip():
        raise SystemExit("Comment body cannot be empty")

    body = text_to_adf(comment_text)
    payload = {"body": body}
    if args.dry_run:
        dump_json({"dryRun": True, "issueKey": args.key, "commentId": args.comment_id, "payload": payload})
        return 0

    updated = update_issue_comment(args.key, args.comment_id, body)
    if args.json:
        dump_json(updated)
        return 0

    dump_json(
        {
            "issueKey": args.key,
            "commentId": updated.get("id"),
            "self": updated.get("self"),
            "updated": updated.get("updated"),
            "author": updated.get("author", {}).get("displayName"),
        }
    )
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
    issue_type = _resolve_issue_type(args)
    fields: Dict[str, Any] = {
        "project": {"key": args.project},
        "summary": args.summary,
        "issuetype": {"name": issue_type},
    }

    description_text = _read_description_text(args)
    if description_text is not None:
        fields["description"] = text_to_adf(description_text)

    if args.assignee:
        fields["assignee"] = {"accountId": _resolve_account_id(args.assignee)}

    priority = _resolve_priority(args)
    if priority:
        fields["priority"] = {"name": priority}

    if args.parent:
        fields["parent"] = {"key": args.parent}

    _apply_create_defaults(fields, args)

    if args.dry_run:
        dump_json({"dryRun": True, "payload": {"fields": fields}})
        return 0

    created = create_issue(fields)
    dump_json(created)
    return 0


def cmd_edit_ticket(args: argparse.Namespace) -> int:
    fields = _build_edit_fields(args)
    if not fields:
        raise SystemExit("No fields supplied. Use --summary, --description, --description-file, --assignee, --priority, --field, --fields-json, or --fields-file.")

    payload = {"fields": fields}
    if args.dry_run:
        dump_json({"dryRun": True, "issueKey": args.key, "payload": payload})
        return 0

    updated = update_issue(args.key, fields)
    if args.json:
        dump_json(updated)
        return 0

    dump_json({"issueKey": args.key, "updated": True, "fields": sorted(fields.keys())})
    return 0


def cmd_transitions(args: argparse.Namespace) -> int:
    transitions = get_issue_transitions(args.key)
    if args.json:
        dump_json(transitions)
        return 0

    dump_json(
        {
            "issueKey": args.key,
            "transitions": [_format_transition_summary(transition) for transition in transitions],
        }
    )
    return 0


def cmd_transition(args: argparse.Namespace) -> int:
    transitions = get_issue_transitions(args.key)
    transition = _resolve_transition(args.target, transitions)
    payload = {"transition": {"id": transition["id"]}}

    if args.dry_run:
        dump_json(
            {
                "dryRun": True,
                "issueKey": args.key,
                "transition": _format_transition_summary(transition),
                "payload": payload,
            }
        )
        return 0

    response = transition_issue(args.key, transition["id"])
    if args.json:
        dump_json(response)
        return 0

    dump_json(
        {
            "issueKey": args.key,
            "transitioned": True,
            "transition": _format_transition_summary(transition),
        }
    )
    return 0


def _format_transition_summary(transition: Dict[str, Any]) -> Dict[str, Optional[str]]:
    to_status = transition.get("to") or {}
    return {
        "id": transition.get("id"),
        "name": transition.get("name"),
        "to": to_status.get("name"),
    }


def _resolve_transition(target: str, transitions: List[dict]) -> dict:
    normalized_target = _normalize_transition_name(target)
    matches = [
        transition
        for transition in transitions
        if transition.get("id") == target
        or _normalize_transition_name(transition.get("name")) == normalized_target
        or _normalize_transition_name((transition.get("to") or {}).get("name")) == normalized_target
    ]

    if len(matches) == 1:
        return matches[0]

    available = ", ".join(
        f"{transition.get('id')}:{transition.get('name')}->{(transition.get('to') or {}).get('name')}"
        for transition in transitions
    )
    if not matches:
        raise SystemExit(f"No transition matched {target!r}. Available transitions: {available}")

    matching = ", ".join(
        f"{transition.get('id')}:{transition.get('name')}->{(transition.get('to') or {}).get('name')}"
        for transition in matches
    )
    raise SystemExit(f"Transition target {target!r} is ambiguous. Matching transitions: {matching}")


def _normalize_transition_name(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _read_description_text(args: argparse.Namespace) -> Optional[str]:
    if args.description is not None:
        return args.description
    if args.description_file is None:
        return None
    if args.description_file == "-":
        return sys.stdin.read()
    return Path(args.description_file).read_text(encoding="utf-8")


def _read_optional_description_text(args: argparse.Namespace) -> Optional[str]:
    if args.description is not None:
        return args.description
    if args.description_file is None:
        return None
    if args.description_file == "-":
        return sys.stdin.read()
    return Path(args.description_file).read_text(encoding="utf-8")


def _read_comment_text(args: argparse.Namespace) -> str:
    if args.body is not None:
        return args.body
    if args.body_file == "-":
        return sys.stdin.read()
    return Path(args.body_file).read_text(encoding="utf-8")


def _build_edit_fields(args: argparse.Namespace) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}

    if args.summary is not None:
        fields["summary"] = args.summary

    description_text = _read_optional_description_text(args)
    if description_text is not None:
        fields["description"] = text_to_adf(description_text)

    if args.assignee is not None:
        fields["assignee"] = _assignee_field(args.assignee)

    if args.priority is not None:
        fields["priority"] = {"name": args.priority}

    for field_map in _read_fields_json_sources(args):
        fields.update(field_map)

    for assignment in args.field or []:
        key, value = _parse_field_assignment(assignment)
        fields[key] = value

    return fields


def _assignee_field(assignee: str) -> Optional[Dict[str, str]]:
    if assignee.lower() in {"none", "null", "unassigned"}:
        return None
    return {"accountId": _resolve_account_id(assignee)}


def _read_fields_json_sources(args: argparse.Namespace) -> List[Dict[str, Any]]:
    field_maps: List[Dict[str, Any]] = []
    for raw in args.fields_json or []:
        parsed = _parse_json_object(raw, "--fields-json")
        field_maps.append(parsed)
    for file_path in args.fields_file or []:
        raw = sys.stdin.read() if file_path == "-" else Path(file_path).read_text(encoding="utf-8")
        parsed = _parse_json_object(raw, "--fields-file")
        field_maps.append(parsed)
    return field_maps


def _parse_json_object(raw: str, source: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON for {source}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"{source} must be a JSON object")
    return parsed


def _parse_field_assignment(assignment: str) -> tuple[str, Any]:
    if "=" not in assignment:
        raise SystemExit("--field values must use KEY=VALUE")
    key, raw_value = assignment.split("=", 1)
    key = key.strip()
    if not key:
        raise SystemExit("--field key cannot be empty")
    return key, _parse_field_value(raw_value)


def _parse_field_value(raw_value: str) -> Any:
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value


def _resolve_issue_type(args: argparse.Namespace) -> str:
    project_key = str(args.project).upper()
    if args.type:
        issue_type = str(args.type).strip()
        if project_key == POSAAS_PROJECT_KEY:
            return POSAAS_ISSUE_TYPE_ALIASES.get(issue_type.lower(), issue_type)
        return issue_type

    if project_key == POSAAS_PROJECT_KEY:
        return POSAAS_DEFAULT_ISSUE_TYPE

    raise SystemExit("--type is required unless --project POSAAS is used")


def _resolve_priority(args: argparse.Namespace) -> Optional[str]:
    if args.priority:
        return args.priority
    if str(args.project).upper() == POSAAS_PROJECT_KEY:
        return POSAAS_DEFAULT_PRIORITY
    return None


def _apply_create_defaults(fields: Dict[str, Any], args: argparse.Namespace) -> None:
    if str(args.project).upper() != POSAAS_PROJECT_KEY:
        return

    fields.setdefault(
        POSAAS_HR_TYPE_FIELD,
        {"id": POSAAS_HR_TYPE_POS_INTERNAL_OPTION_ID},
    )
    fields.setdefault(
        "timetracking",
        {"originalEstimate": POSAAS_DEFAULT_ORIGINAL_ESTIMATE},
    )


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
    create.add_argument(
        "--type",
        help=(
            "Issue type name, for example Story. Defaults to Defect for POSAAS; "
            "POSAAS aliases like 'Improve Defect' are normalized to Defect."
        ),
    )
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

    add_comment = sub.add_parser(
        "add-comment",
        aliases=["comment"],
        help="Add a comment to a Jira issue",
    )
    add_comment.add_argument("key")
    comment_body_group = add_comment.add_mutually_exclusive_group(required=True)
    comment_body_group.add_argument("--body", help="Plain-text or markdown-ish comment body")
    comment_body_group.add_argument(
        "--body-file",
        help="Read comment text from a file path, or '-' to read from stdin",
    )
    add_comment.add_argument("--dry-run", action="store_true", help="Print the comment payload without posting it")
    add_comment.add_argument("--json", action="store_true", help="Emit raw Jira create-comment response")
    add_comment.set_defaults(func=cmd_add_comment)

    edit_comment = sub.add_parser(
        "edit-comment",
        aliases=["update-comment"],
        help="Replace an existing Jira comment body",
    )
    edit_comment.add_argument("key")
    edit_comment.add_argument("comment_id")
    edit_comment_body_group = edit_comment.add_mutually_exclusive_group(required=True)
    edit_comment_body_group.add_argument("--body", help="Plain-text or markdown-ish comment body")
    edit_comment_body_group.add_argument(
        "--body-file",
        help="Read comment text from a file path, or '-' to read from stdin",
    )
    edit_comment.add_argument("--dry-run", action="store_true", help="Print the update payload without posting it")
    edit_comment.add_argument("--json", action="store_true", help="Emit raw Jira update-comment response")
    edit_comment.set_defaults(func=cmd_edit_comment)

    edit_ticket = sub.add_parser(
        "edit-ticket",
        aliases=["update-ticket", "edit-issue", "update-issue"],
        help="Update Jira issue fields",
    )
    edit_ticket.add_argument("key")
    edit_ticket.add_argument("--summary", help="Replace issue summary")
    edit_ticket_description_group = edit_ticket.add_mutually_exclusive_group()
    edit_ticket_description_group.add_argument("--description", help="Replace issue description")
    edit_ticket_description_group.add_argument(
        "--description-file",
        help="Read replacement description from a file path, or '-' to read from stdin",
    )
    edit_ticket.add_argument(
        "--assignee",
        help="Assignee accountId, email address, 'current', or 'unassigned'",
    )
    edit_ticket.add_argument("--priority", help="Priority name, for example Major")
    edit_ticket.add_argument(
        "--field",
        action="append",
        help="Set a raw Jira field using KEY=VALUE. VALUE is parsed as JSON when valid, otherwise as a string.",
    )
    edit_ticket.add_argument(
        "--fields-json",
        action="append",
        help="Merge raw Jira fields from a JSON object string.",
    )
    edit_ticket.add_argument(
        "--fields-file",
        action="append",
        help="Merge raw Jira fields from a JSON object file, or '-' to read from stdin.",
    )
    edit_ticket.add_argument("--dry-run", action="store_true", help="Print the update payload without posting it")
    edit_ticket.add_argument("--json", action="store_true", help="Emit raw Jira update-issue response")
    edit_ticket.set_defaults(func=cmd_edit_ticket)

    transitions = sub.add_parser("transitions", help="List available transitions for a Jira issue")
    transitions.add_argument("key")
    transitions.add_argument("--json", action="store_true", help="Emit raw Jira transitions response")
    transitions.set_defaults(func=cmd_transitions)

    transition = sub.add_parser("transition", help="Transition a Jira issue by transition id, transition name, or target status name")
    transition.add_argument("key")
    transition.add_argument("target", help="Transition id, transition name, or target status name")
    transition.add_argument("--dry-run", action="store_true", help="Print the transition payload without posting it")
    transition.add_argument("--json", action="store_true", help="Emit raw Jira transition response")
    transition.set_defaults(func=cmd_transition)

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
    try:
        return args.func(args)
    except AtlassianHttpError as exc:
        print(str(exc), file=sys.stderr)
        return 1
