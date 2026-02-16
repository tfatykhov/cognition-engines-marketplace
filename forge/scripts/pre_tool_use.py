#!/usr/bin/env python3
"""
ACCER PreToolUse Hook
Classifies file modifications by stakes level and enforces gates.

- BLOCKED patterns: deny the operation entirely
- CRITICAL/HIGH patterns: require user confirmation (permissionDecision: "ask")
- MEDIUM patterns: allow with advisory context
- Everything else: silent pass-through
"""

import json
import re
import sys


# === CONFIGURABLE PATTERNS ===

BLOCKED_PATTERNS = [
    r"\.env\.prod",
    r"\.env\.production",
    r"\.git/",
    r"\.ssh/",
    r"id_rsa",
    r"\.pem$",
    r"secrets\.ya?ml",
]

CRITICAL_PATTERNS = [
    r"migrations?/",
    r"schema\.(sql|prisma|graphql)",
    r"flyway",
    r"liquibase",
    r"alembic/versions/",
]

HIGH_PATTERNS = [
    r"(auth|security|permission|rbac|acl)",
    r"(password|credential|token|secret|encrypt)",
    r"(docker-compose|Dockerfile)\.prod",
    r"\.env\b",
    r"(api|openapi|swagger)\.(ya?ml|json)",
    r"(nginx|traefik|haproxy)\.conf",
    r"application(-prod)?\.ya?ml",
    r"settings\.prod\.",
]

MEDIUM_PATTERNS = [
    r"\.(github|gitlab)/",
    r"ci/cd|\.ci\.",
    r"(Makefile|Rakefile|Taskfile)",
    r"(webpack|vite|rollup|tsconfig)\..*\.(js|json|ts)",
    r"(pom|build\.gradle|package\.json|Cargo\.toml)",
]


def classify_path(file_path: str) -> tuple[str, str]:
    """Returns (stakes_level, matched_pattern) for a file path."""
    if not file_path:
        return ("low", "")

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return ("blocked", pattern)

    for pattern in CRITICAL_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return ("critical", pattern)

    for pattern in HIGH_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return ("high", pattern)

    for pattern in MEDIUM_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return ("medium", pattern)

    return ("low", "")


def extract_path(hook_input: dict) -> str:
    """Extract file path from hook input, handling Write/Edit/Bash tools."""
    tool_input = hook_input.get("toolInput", {})

    # Write/Edit/MultiEdit tools
    for key in ("file_path", "filePath", "path"):
        if key in tool_input:
            return tool_input[key]

    # Bash tool — check command for file-modifying operations
    command = tool_input.get("command", "")
    if command:
        # Look for common file-modifying commands
        for pattern in [
            r"(?:rm|mv|cp|chmod|chown)\s+.*?(\S+)$",
            r"(?:tee|cat\s*>)\s+(\S+)",
            r">\s*(\S+)",
        ]:
            match = re.search(pattern, command)
            if match:
                return match.group(1)

    return ""


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)

    try:
        hook_input = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    file_path = extract_path(hook_input)
    if not file_path:
        sys.exit(0)

    stakes, pattern = classify_path(file_path)

    if stakes == "blocked":
        result = {
            "permissionDecision": "deny",
            "reason": f"ACCER: Blocked path ({pattern}). This file cannot be modified by the agent."
        }
        print(json.dumps(result))
        sys.exit(0)

    if stakes == "critical":
        result = {
            "permissionDecision": "ask",
            "reason": f"ACCER CRITICAL: {file_path} matches critical pattern ({pattern}). Schema/migration changes require explicit user approval."
        }
        print(json.dumps(result))
        sys.exit(0)

    if stakes == "high":
        result = {
            "permissionDecision": "ask",
            "reason": f"ACCER HIGH: {file_path} matches high-stakes pattern ({pattern}). Security/config changes require user approval."
        }
        print(json.dumps(result))
        sys.exit(0)

    if stakes == "medium":
        result = {
            "additionalContext": f"ACCER advisory: {file_path} is a medium-stakes file ({pattern}). Ensure pre_action was called before this modification."
        }
        print(json.dumps(result))
        sys.exit(0)

    # LOW stakes — silent pass
    sys.exit(0)


if __name__ == "__main__":
    main()
