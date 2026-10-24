#!/usr/bin/env python3
"""
FORGE Stop Hook
Checks for unreflected decisions and blocks session stop if found.

Reads the session transcript (transcript_path from the hook input) and
collects decision IDs returned by pre_action / log_decision that have no
matching review_outcome call. If any are found, it blocks the stop once
and asks Claude to record the outcomes.
"""

import json
import re
import sys


RECORDING_TOOLS = ("pre_action", "log_decision")
ID_KEYS = ("decisionId", "decision_id", "id")


def tool_name(name: str) -> str:
    """Strip the MCP prefix: mcp__plugin_forge_decisions__pre_action -> pre_action."""
    return name.rsplit("__", 1)[-1]


def result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def find_id(obj) -> str | None:
    """Find a decision ID in a parsed tool result."""
    if isinstance(obj, dict):
        for key in ID_KEYS:
            if isinstance(obj.get(key), str) and obj[key]:
                return obj[key]
        for value in obj.values():
            found = find_id(value)
            if found:
                return found
    return None


def decision_id_from_result(text: str) -> str | None:
    try:
        return find_id(json.loads(text))
    except json.JSONDecodeError:
        match = re.search(r'"(?:decisionId|decision_id)"\s*:\s*"([^"]+)"', text)
        return match.group(1) if match else None


def content_blocks(entry: dict) -> list:
    message = entry.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    return content if isinstance(content, list) else []


def scan_for_unreflected(transcript_path: str) -> list[str]:
    """Return decision IDs created in this session that lack review_outcome."""
    pending_calls = {}  # tool_use id -> tool name, for recording tools
    logged_ids = []
    reviewed_ids = set()

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue

                for block in content_blocks(entry):
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use":
                        name = tool_name(block.get("name", ""))
                        tool_input = block.get("input") or {}
                        if name in RECORDING_TOOLS:
                            # pre_action with auto_record false creates no record
                            if name == "pre_action" and tool_input.get("auto_record") is False:
                                continue
                            pending_calls[block.get("id")] = name
                        elif name == "review_outcome":
                            rid = tool_input.get("id") or tool_input.get("decision_id")
                            if rid:
                                reviewed_ids.add(str(rid))
                    elif block.get("type") == "tool_result":
                        if block.get("tool_use_id") in pending_calls and not block.get("is_error"):
                            did = decision_id_from_result(result_text(block.get("content")))
                            if did and did not in logged_ids:
                                logged_ids.append(did)

    except OSError:
        return []

    return [did for did in logged_ids if did not in reviewed_ids]


def main():
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        hook_input = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        sys.exit(0)

    # Claude is already continuing because of this hook: let it stop
    if hook_input.get("stop_hook_active"):
        sys.exit(0)

    transcript = hook_input.get("transcript_path")
    if not transcript:
        sys.exit(0)

    unreflected = scan_for_unreflected(transcript)

    if unreflected:
        ids_str = ", ".join(unreflected)
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"FORGE: {len(unreflected)} decision(s) recorded without an outcome: [{ids_str}]. "
                f"If the work for them is done, call review_outcome for each so the decision log "
                f"stays accurate. If a decision is still in progress, say so to the user and stop."
            ),
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
