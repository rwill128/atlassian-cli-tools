from typing import Any, Dict, List

from .http import request_bytes, request_json


DEFAULT_ISSUE_FIELDS = ",".join(
    [
        "summary",
        "description",
        "status",
        "assignee",
        "reporter",
        "issuetype",
        "project",
        "created",
        "updated",
        "priority",
        "resolution",
        "labels",
        "attachment",
    ]
)


def search_all_issues(jql: str, fields: str, max_results: int = 100) -> List[dict]:
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


def get_issue(issue_key: str, fields: str = DEFAULT_ISSUE_FIELDS) -> dict:
    return request_json(
        f"/rest/api/3/issue/{issue_key}",
        params={"fields": fields},
    )


def get_issue_comments(issue_key: str, max_results: int = 100) -> List[dict]:
    comments: List[dict] = []
    start_at = 0
    while True:
        data = request_json(
            f"/rest/api/3/issue/{issue_key}/comment",
            params={"startAt": start_at, "maxResults": max_results},
        )
        batch = data.get("comments", [])
        comments.extend(batch)
        start_at += len(batch)
        if start_at >= data.get("total", 0) or not batch:
            break
    return comments


def get_issue_changelog(issue_key: str, max_results: int = 100) -> List[dict]:
    histories: List[dict] = []
    start_at = 0
    while True:
        data = request_json(
            f"/rest/api/3/issue/{issue_key}/changelog",
            params={"startAt": start_at, "maxResults": max_results},
        )
        batch = data.get("values", [])
        histories.extend(batch)
        start_at += len(batch)
        if start_at >= data.get("total", 0) or not batch:
            break
    return histories


def download_attachment(attachment_url: str) -> bytes:
    return request_bytes(attachment_url)


def create_issue(fields: Dict[str, Any]) -> dict:
    return request_json(
        "/rest/api/3/issue",
        method="POST",
        body={"fields": fields},
    )


def add_issue_comment(issue_key: str, body: Dict[str, Any]) -> dict:
    return request_json(
        f"/rest/api/3/issue/{issue_key}/comment",
        method="POST",
        body={"body": body},
    )


def update_issue_comment(issue_key: str, comment_id: str, body: Dict[str, Any]) -> dict:
    return request_json(
        f"/rest/api/3/issue/{issue_key}/comment/{comment_id}",
        method="PUT",
        body={"body": body},
    )


def update_issue(issue_key: str, fields: Dict[str, Any]) -> dict:
    return request_json(
        f"/rest/api/3/issue/{issue_key}",
        method="PUT",
        body={"fields": fields},
    )


def get_issue_transitions(issue_key: str) -> List[dict]:
    data = request_json(f"/rest/api/3/issue/{issue_key}/transitions")
    return data.get("transitions", [])


def transition_issue(issue_key: str, transition_id: str) -> dict:
    return request_json(
        f"/rest/api/3/issue/{issue_key}/transitions",
        method="POST",
        body={"transition": {"id": transition_id}},
    )


def search_users(query: str, max_results: int = 20) -> List[dict]:
    data = request_json(
        "/rest/api/3/user/search",
        params={"query": query, "maxResults": max_results},
    )
    return data if isinstance(data, list) else []
