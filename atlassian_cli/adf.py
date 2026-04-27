import re
from typing import Any, Dict, List, Optional


def adf_to_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(item) for item in node)
    if not isinstance(node, dict):
        return str(node)

    node_type = node.get("type")
    content = node.get("content", [])
    attrs = node.get("attrs") or {}
    text = node.get("text", "")

    if node_type in {"doc", "bodiedExtension"}:
        return "".join(adf_to_text(item) for item in content)
    if node_type == "text":
        return text
    if node_type == "hardBreak":
        return "\n"
    if node_type == "paragraph":
        inner = "".join(adf_to_text(item) for item in content).strip()
        return inner + ("\n\n" if inner else "\n")
    if node_type == "heading":
        level = max(1, min(6, int(attrs.get("level", 1))))
        inner = "".join(adf_to_text(item) for item in content).strip()
        return ("#" * level) + " " + inner + "\n\n"
    if node_type == "bulletList":
        return _render_list(content, ordered=False)
    if node_type == "orderedList":
        return _render_list(content, ordered=True)
    if node_type == "listItem":
        return "".join(adf_to_text(item) for item in content)
    if node_type == "blockquote":
        inner = "".join(adf_to_text(item) for item in content).strip().splitlines()
        return "\n".join(f"> {line}" if line else ">" for line in inner) + "\n\n"
    if node_type == "codeBlock":
        inner = "".join(adf_to_text(item) for item in content).rstrip()
        return f"```\n{inner}\n```\n\n"
    if node_type == "rule":
        return "---\n\n"
    if node_type == "mention":
        return attrs.get("text") or attrs.get("id", "")
    if node_type in {"emoji", "status"}:
        return attrs.get("text") or attrs.get("title", "")
    if node_type in {"inlineCard", "blockCard", "embedCard"}:
        return attrs.get("url", "")
    if node_type == "link":
        return attrs.get("href", "")
    if node_type == "mediaSingle":
        return "".join(adf_to_text(item) for item in content)
    if node_type == "media":
        return attrs.get("alt", attrs.get("id", "[media]"))
    if node_type == "table":
        rows = [_render_table_row(item) for item in content if item.get("type") == "tableRow"]
        rows = [row for row in rows if row]
        return "\n".join(rows) + "\n\n" if rows else ""
    if node_type in {"tableHeader", "tableCell"}:
        return " ".join(adf_to_text(item).strip() for item in content if adf_to_text(item).strip())
    if node_type == "panel":
        inner = "".join(adf_to_text(item) for item in content).strip()
        panel_type = attrs.get("panelType", "info").upper()
        return f"[{panel_type}] {inner}\n\n" if inner else ""

    return "".join(adf_to_text(item) for item in content) or text


def _render_list(items: List[Dict[str, Any]], ordered: bool) -> str:
    lines: List[str] = []
    for idx, item in enumerate(items, start=1):
        prefix = f"{idx}. " if ordered else "- "
        body = "".join(adf_to_text(child) for child in item.get("content", [])).strip()
        if body:
            body_lines = body.splitlines()
            lines.append(prefix + body_lines[0])
            for extra in body_lines[1:]:
                lines.append("   " + extra)
    return "\n".join(lines) + ("\n\n" if lines else "")


def _render_table_row(row: Dict[str, Any]) -> str:
    cells = []
    for cell in row.get("content", []):
        cell_text = adf_to_text(cell).strip().replace("\n", " ")
        if cell_text:
            cells.append(cell_text)
    return " | ".join(cells)


def text_to_adf(text: str) -> Dict[str, Any]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    content: List[Dict[str, Any]] = []
    index = 0

    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue

        fence_match = re.match(r"^```(.*)$", stripped)
        if fence_match:
            language = fence_match.group(1).strip() or None
            index += 1
            code_lines: List[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            content.append(_code_block_node("\n".join(code_lines), language=language))
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            content.append(
                {
                    "type": "heading",
                    "attrs": {"level": len(heading_match.group(1))},
                    "content": [{"type": "text", "text": heading_match.group(2)}],
                }
            )
            index += 1
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if bullet_match:
            items: List[str] = []
            while index < len(lines):
                match = re.match(r"^[-*]\s+(.*)$", lines[index].strip())
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            content.append(_list_node(items, ordered=False))
            continue

        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered_match:
            items = []
            while index < len(lines):
                match = re.match(r"^\d+\.\s+(.*)$", lines[index].strip())
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            content.append(_list_node(items, ordered=True))
            continue

        if stripped.startswith("|"):
            table_lines: List[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].rstrip())
                index += 1
            content.append(_table_node(table_lines))
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            next_line = lines[index].strip()
            if not next_line:
                break
            if re.match(r"^```", next_line):
                break
            if re.match(r"^(#{1,6})\s+", next_line):
                break
            if re.match(r"^[-*]\s+", next_line):
                break
            if re.match(r"^\d+\.\s+", next_line):
                break
            if next_line.startswith("|"):
                break
            paragraph_lines.append(next_line)
            index += 1

        content.append(_paragraph_node(" ".join(paragraph_lines)))

    return {"type": "doc", "version": 1, "content": content}


def _paragraph_node(text: str) -> Dict[str, Any]:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _code_block_node(text: str, *, language: Optional[str] = None) -> Dict[str, Any]:
    node: Dict[str, Any] = {"type": "codeBlock", "content": [{"type": "text", "text": text}]}
    if language:
        node["attrs"] = {"language": language}
    return node


def _table_node(lines: List[str]) -> Dict[str, Any]:
    rows = [_split_table_row(line) for line in lines]
    rows = [row for row in rows if row]
    if not rows:
        return _code_block_node("\n".join(lines), language="text")

    header = rows[0]
    data_rows = rows[1:]
    if data_rows and _is_table_separator(data_rows[0]):
        data_rows = data_rows[1:]

    width = max(len(header), *(len(row) for row in data_rows)) if data_rows else len(header)
    normalized_rows = [_pad_row(header, width), *[_pad_row(row, width) for row in data_rows]]

    return {
        "type": "table",
        "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
        "content": [
            {
                "type": "tableRow",
                "content": [
                    _table_cell_node(cell, header=row_index == 0)
                    for cell in row
                ],
            }
            for row_index, row in enumerate(normalized_rows)
        ],
    }


def _split_table_row(line: str) -> List[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_table_separator(row: List[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in row)


def _pad_row(row: List[str], width: int) -> List[str]:
    return [*row, *([""] * (width - len(row)))]


def _table_cell_node(text: str, *, header: bool) -> Dict[str, Any]:
    return {
        "type": "tableHeader" if header else "tableCell",
        "content": [_paragraph_node(text)],
    }


def _list_node(items: List[str], *, ordered: bool) -> Dict[str, Any]:
    return {
        "type": "orderedList" if ordered else "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [_paragraph_node(item)],
            }
            for item in items
        ],
    }
