#!/usr/bin/env python3
"""
FORGE Session Start Hook
Injects the decision-logging protocol (and optionally live context from the
CSTP API) at Claude Code session start.
FORGE: Fetch → Orient → Resolve → Go → Extract
"""

import json
import os
import sys
import urllib.request
import urllib.error


FORGE_CONTEXT = """## FORGE decision logging is active

This project uses the `decisions` MCP server to keep a shared log of design decisions: what was chosen, why, and how it turned out. The full protocol is in the `forge-protocol` skill; load it before your first logged decision.

Summary:
- **Fetch**: call `get_session_context(task_description=...)` once, early in the session.
- **Orient**: before each MEDIUM or higher decision, call `pre_action(action, category, stakes, confidence, reasons, agent_id, auto_record=true)`. It returns a `decisionId`. If it returns `allowed: false`, stop and explain the guardrail to the user.
- **Resolve**: record the rationale with `record_thought(text, decision_id, agent_id)`, one short note per call (facts, constraints, trade-offs, ruled-out options), sequentially after `pre_action` returns. Scale by stakes: LOW 2-3, MEDIUM 3-6, HIGH/CRITICAL 5-10. Then finalize with `update_decision(id, decision)`; `log_decision` would create a duplicate record.
- **Go**: do the work. For HIGH and CRITICAL decisions, get the user's confirmation first.
- **Extract**: when the work for a decision is done, call `review_outcome(id, outcome, actual_result, lessons)`.

Skip logging for trivial or mechanical steps (formatting, typos, installing a dependency, running tests). Keep logging quiet in chat unless the user asks about it.
"""


def hook_output(context: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }


def api_mode(cstp_url):
    """Call CSTP REST API directly and append live cognitive context."""
    token = os.environ.get("CSTP_TOKEN", "")

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    project_name = os.path.basename(project_dir) if project_dir else "unknown"

    payload = json.dumps({
        "task_description": f"Development session in {project_name}",
        "include": ["decisions", "guardrails", "calibration", "patterns"]
    }).encode()

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(
            f"{cstp_url.rstrip('/')}/api/session-context",
            data=payload,
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        lines = [FORGE_CONTEXT, "\n### Cognitive Context (auto-loaded)\n"]

        cal = data.get("calibration", {})
        if cal:
            lines.append(f"Brier: {cal.get('brier_score', '?')} | Bias: {cal.get('confidence_bias', 'unknown')}")

        guardrails = data.get("active_guardrails", [])
        if guardrails:
            lines.append("\nGuardrails:")
            for g in guardrails:
                lines.append(f"- {g.get('rule', '?')}")

        patterns = data.get("patterns", [])
        if patterns:
            lines.append("\nPatterns:")
            for p in patterns:
                lines.append(f"- {p.get('pattern', '?')} ({p.get('reinforced_by', 1)}x)")

        return "\n".join(lines)

    except (urllib.error.URLError, TimeoutError, ValueError, AttributeError) as e:
        print(f"CSTP API unavailable ({e}), falling back to prompt mode", file=sys.stderr)
        return FORGE_CONTEXT


def main():
    # ACCER_MODE is the legacy name, still honored
    mode = (os.environ.get("FORGE_MODE") or os.environ.get("ACCER_MODE") or "prompt").lower()
    cstp_url = os.environ.get("CSTP_URL", "")

    if mode == "api" and cstp_url:
        context = api_mode(cstp_url)
    else:
        if mode == "api":
            print("FORGE_MODE=api but CSTP_URL is not set, using prompt mode", file=sys.stderr)
        context = FORGE_CONTEXT

    print(json.dumps(hook_output(context)))


if __name__ == "__main__":
    main()
