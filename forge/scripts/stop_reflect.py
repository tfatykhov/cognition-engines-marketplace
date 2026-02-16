#!/usr/bin/env python3
"""
ACCER Stop Hook
Checks for unreflected decisions and blocks session stop if found.

Scans the conversation transcript for logged decisions that lack
a corresponding review_outcome call. If any are found, returns
exit code 2 to block the stop and tells Claude to reflect.
"""

import json
import os
import re
import sys


def find_transcript() -> str | None:
    """Find the current session's JSONL transcript."""
    # Claude Code stores transcripts in ~/.claude/projects/<hash>/
    claude_dir = os.path.expanduser("~/.claude")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")

    if not os.path.isdir(claude_dir):
        return None

    # Look for the most recent JSONL file in project sessions
    candidates = []
    for root, dirs, files in os.walk(claude_dir):
        for f in files:
            if f.endswith(".jsonl"):
                full = os.path.join(root, f)
                candidates.append((os.path.getmtime(full), full))

    if not candidates:
        return None

    # Return most recently modified
    candidates.sort(reverse=True)
    return candidates[0][1]


def scan_for_unreflected(transcript_path: str) -> list[str]:
    """Scan JSONL transcript for decision IDs without review_outcome."""
    logged_ids = set()
    reviewed_ids = set()

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                text = json.dumps(entry).lower()

                # Look for log_decision calls that returned an ID
                # Pattern: decision IDs are 8-char hex
                if "log_decision" in text or "pre_action" in text:
                    # Extract decision IDs from responses
                    ids = re.findall(r'"(?:decisionId|decision_id|id)":\s*"([a-f0-9]{8})"', json.dumps(entry))
                    logged_ids.update(ids)

                if "review_outcome" in text:
                    ids = re.findall(r'"id":\s*"([a-f0-9]{8})"', json.dumps(entry))
                    reviewed_ids.update(ids)

    except (IOError, PermissionError):
        return []

    return list(logged_ids - reviewed_ids)


def main():
    raw = sys.stdin.read()

    # Prevent infinite loops — if stop_hook already ran, pass through
    if os.environ.get("ACCER_STOP_HOOK_ACTIVE"):
        sys.exit(0)

    os.environ["ACCER_STOP_HOOK_ACTIVE"] = "1"

    transcript = find_transcript()
    if not transcript:
        sys.exit(0)

    unreflected = scan_for_unreflected(transcript)

    if unreflected:
        ids_str = ", ".join(unreflected)
        count = len(unreflected)
        result = {
            "additionalContext": (
                f"ACCER: {count} decision(s) logged without reflection: [{ids_str}]. "
                f"Call review_outcome for each before ending. "
                f"The ACCER feedback loop requires every decision to have an outcome recorded."
            )
        }
        print(json.dumps(result))
        # Exit code 2 = block the stop, send message back to Claude
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
