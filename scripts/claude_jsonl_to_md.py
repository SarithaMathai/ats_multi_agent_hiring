#!/usr/bin/env python3
"""
Convert Claude Code JSONL conversation history into clean Markdown.

Usage:
    python claude_jsonl_to_md.py                       # uses the 3 default paths below
    python claude_jsonl_to_md.py file1.jsonl file2.jsonl ...

For each input X.jsonl, writes X.md alongside it.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

DEFAULT_FILES = [
    r"C:\Users\thoma\.claude\projects\c--Thomas-IK-CapStone-Project\2a1f4bd3-df24-44ae-a3b6-2e8235240595.jsonl",
    r"C:\Users\thoma\.claude\projects\c--Thomas-IK-CapStone-Project\03fbbac7-8f48-4443-ad87-1f4cd9c53c75.jsonl",
    r"C:\Users\thoma\.claude\projects\c--Thomas-IK-CapStone-Project\5dcebbf9-9a91-4541-8a6e-08e38cf97629.jsonl",
]

# How much of a tool result to keep in the markdown before truncating.
TOOL_RESULT_MAX_CHARS = 4000


def format_timestamp(ts):
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def content_to_md(content):
    """Render Claude Code's `content` field (str or list of blocks) as Markdown."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return str(content)

    parts = []
    for block in content:
        if not isinstance(block, dict):
            parts.append(str(block))
            continue

        btype = block.get("type")

        if btype == "text":
            parts.append(block.get("text", "").strip())

        elif btype == "thinking":
            thinking = block.get("thinking", "").strip()
            if thinking:
                parts.append(
                    f"<details><summary>Thinking</summary>\n\n{thinking}\n\n</details>"
                )

        elif btype == "tool_use":
            name = block.get("name", "tool")
            inp = block.get("input", {})
            try:
                inp_str = json.dumps(inp, indent=2, ensure_ascii=False)
            except Exception:
                inp_str = str(inp)
            parts.append(f"**Tool call: `{name}`**\n\n```json\n{inp_str}\n```")

        elif btype == "tool_result":
            result = block.get("content", "")
            if isinstance(result, list):
                result = content_to_md(result)
            elif not isinstance(result, str):
                result = str(result)
            result = result.strip()
            if len(result) > TOOL_RESULT_MAX_CHARS:
                result = result[:TOOL_RESULT_MAX_CHARS] + "\n\n... [truncated]"
            parts.append(
                f"<details><summary>Tool result</summary>\n\n```\n{result}\n```\n\n</details>"
            )

        elif btype == "image":
            parts.append("*(image omitted)*")

        else:
            # Unknown block type — keep a marker so nothing is silently lost.
            parts.append(f"*(unknown content block: {btype})*")

    return "\n\n".join(p for p in parts if p)


def convert_file(input_path: Path, output_path: Path):
    lines_out = []
    session_meta = {}
    msg_count = 0

    with input_path.open("r", encoding="utf-8") as f:
        for line_num, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as e:
                lines_out.append(f"<!-- Skipped malformed line {line_num}: {e} -->")
                continue

            etype = entry.get("type")

            # Capture session metadata once.
            if not session_meta:
                session_meta = {
                    "sessionId": entry.get("sessionId"),
                    "cwd": entry.get("cwd"),
                    "version": entry.get("version"),
                    "gitBranch": entry.get("gitBranch"),
                }

            if etype == "summary":
                summary = entry.get("summary", "")
                if summary:
                    lines_out.append(f"> **Summary:** {summary}\n")
                continue

            message = entry.get("message")
            if not isinstance(message, dict):
                continue

            role = message.get("role") or etype or "unknown"
            content = message.get("content")
            ts = format_timestamp(entry.get("timestamp"))

            md_content = content_to_md(content)
            if not md_content:
                continue

            msg_count += 1
            header = f"## {role.capitalize()}"
            if ts:
                header += f"  \n*{ts}*"
            lines_out.append(f"{header}\n\n{md_content}\n")

    # Top-of-file header
    header_parts = ["# Claude Code Conversation", "", f"*Source: `{input_path.name}`*", ""]
    if session_meta.get("sessionId"):
        header_parts.append(f"- Session ID: `{session_meta['sessionId']}`")
    if session_meta.get("cwd"):
        header_parts.append(f"- Working directory: `{session_meta['cwd']}`")
    if session_meta.get("gitBranch"):
        header_parts.append(f"- Git branch: `{session_meta['gitBranch']}`")
    if session_meta.get("version"):
        header_parts.append(f"- Claude Code version: `{session_meta['version']}`")
    header_parts.append(f"- Messages: {msg_count}")
    header_parts.append("\n---\n")

    output = "\n".join(header_parts) + "\n" + "\n".join(lines_out)
    output_path.write_text(output, encoding="utf-8")
    print(f"Wrote {output_path} ({msg_count} messages)")


def main():
    files = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_FILES
    any_processed = False
    for f in files:
        p = Path(f)
        if not p.exists():
            print(f"Skipping (not found): {p}", file=sys.stderr)
            continue
        out = p.with_suffix(".md")
        convert_file(p, out)
        any_processed = True
    if not any_processed:
        print("No input files were processed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()