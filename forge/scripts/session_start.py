#!/usr/bin/env python3
"""
FORGE Session Start Hook
Injects cognitive context and protocol enforcement at Claude Code session start.
FORGE: Fetch → Orient → Resolve → Go → Extract
"""

import json
import os
import sys
import urllib.request
import urllib.error


FORGE_CONTEXT = """## FORGE — The Decision Loop — ACTIVE

You forge decisions in the Cognition Engine — deliberately, under pressure, with intention.
**FORGE**: **F**etch → **O**rient → **R**esolve → **G**o → **E**xtract

You have the `decisions` MCP server. Follow this loop for EVERY session:

### FETCH — Load context
Call `get_session_context(task_description: "<infer from user's first message>")` FIRST.

### Decision Recording Flow (MANDATORY for all non-trivial changes)
You MUST follow this EXACT sequence for every design choice:

```
ORIENT:
  pre_action(action, category, stakes, confidence, reasons, agent_id, auto_record:true)
  → returns decisionId

RESOLVE:
  record_thought(text="one atomic signal", decision_id=decisionId, agent_id="agent")
  record_thought(text="another atomic signal", decision_id=decisionId, agent_id="agent")
  ... minimum 10 micro-thoughts per decision ...
  record_thought(text="conclusion: chose X", decision_id=decisionId, agent_id="agent")

  update_decision(id=decisionId, decision="Final: chose X")
  → finalizes decision text

GO:
  Execute the work.

EXTRACT:
  review_outcome(id=decisionId, outcome, actual_result, lessons)
```

⚠️ Skipping RESOLVE creates decisions with EMPTY deliberation — protocol violation.
⚠️ Do NOT use log_decision to finalize — it creates a duplicate. Always use update_decision.
⚠️ Each record_thought is ONE atomic signal. Not paragraphs. Think neurons firing. Minimum 10.

### What counts as a decision?
Any step where you CHOOSE between alternatives. If you could have done it differently and it would matter — it's a decision.

### Multi-agent
Always pass both agent_id and decision_id to record_thought for full isolation.

### When done
EXTRACT: Call review_outcome for EVERY recorded decision before ending the session.
"""


def prompt_mode():
    """Inject FORGE protocol instructions."""
    return {"additionalContext": FORGE_CONTEXT}


def api_mode(cstp_url):
    """Call CSTP REST API directly and inject full cognitive context."""
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
            f"{cstp_url}/api/session-context",
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

        return {"additionalContext": "\n".join(lines)}

    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"CSTP API unavailable ({e}), falling back to prompt mode", file=sys.stderr)
        return prompt_mode()


def main():
    mode = os.environ.get("ACCER_MODE", "prompt").lower()
    cstp_url = os.environ.get("CSTP_URL", "http://192.168.1.141:9991")

    if mode == "api":
        result = api_mode(cstp_url)
    else:
        result = prompt_mode()

    print(json.dumps(result))


if __name__ == "__main__":
    main()
