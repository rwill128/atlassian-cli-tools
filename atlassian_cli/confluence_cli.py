import argparse
from typing import List, Optional

from .formatting import dump_json
from .http import request_json


def cmd_spaces(args: argparse.Namespace) -> int:
    data = request_json("/wiki/rest/api/space", params={"limit": args.limit})
    dump_json(
        {
            "size": data.get("size"),
            "results": [
                {
                    "key": item.get("key"),
                    "name": item.get("name"),
                    "type": item.get("type"),
                }
                for item in data.get("results", [])
            ],
        }
    )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    data = request_json(
        "/wiki/rest/api/content/search",
        params={"cql": f'type=page and text~"{args.query}"', "limit": args.limit},
    )
    dump_json(
        {
            "size": data.get("size"),
            "results": [
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "type": item.get("type"),
                    "webui": item.get("_links", {}).get("webui"),
                }
                for item in data.get("results", [])
            ],
        }
    )
    return 0


def cmd_page(args: argparse.Namespace) -> int:
    expand = "body.storage,version,space"
    if not args.body:
        expand = "version,space"
    data = request_json(f"/wiki/rest/api/content/{args.page_id}", params={"expand": expand})
    if not args.body:
        dump_json(
            {
                "id": data.get("id"),
                "title": data.get("title"),
                "type": data.get("type"),
                "space": (data.get("space") or {}).get("key"),
                "version": ((data.get("version") or {}).get("number")),
                "webui": (data.get("_links") or {}).get("webui"),
            }
        )
        return 0

    dump_json(data)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tconf", description="Confluence CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    spaces = sub.add_parser("spaces", help="List accessible Confluence spaces")
    spaces.add_argument("--limit", type=int, default=10)
    spaces.set_defaults(func=cmd_spaces)

    search = sub.add_parser("search", help="Search Confluence pages by text")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(func=cmd_search)

    page = sub.add_parser("page", help="Fetch a Confluence page by id")
    page.add_argument("page_id")
    page.add_argument("--body", action="store_true", help="Include page body.storage")
    page.set_defaults(func=cmd_page)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
