#!/usr/bin/env python3
"""
FORGE PreToolUse Hook
Classifies file modifications by stakes level and enforces gates.

- BLOCKED patterns: deny the operation entirely
- CRITICAL/HIGH patterns: require user confirmation (permissionDecision: "ask")
- MEDIUM patterns: allow with advisory context
- Everything else: silent pass-through
"""

import json
import re
import shlex
import sys


# === CONFIGURABLE PATTERNS ===

BLOCKED_PATTERNS = [
    r"\.env\.prod",
    r"\.env\.production",
    r"(^|/)\.git/",
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
    r"(^|/)\.env(\.(?!example$|sample$|template$)[\w.-]+)?$",
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

LEVELS = [
    ("blocked", BLOCKED_PATTERNS),
    ("critical", CRITICAL_PATTERNS),
    ("high", HIGH_PATTERNS),
    ("medium", MEDIUM_PATTERNS),
]
RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3, "blocked": 4}

# Bash commands whose non-option arguments are files being modified.
MODIFYING_COMMANDS = {
    "rm", "mv", "cp", "chmod", "chown", "tee", "touch", "truncate",
    "ln", "install", "dd", "unlink", "shred",
}
REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")"}
IGNORED_TARGETS = {"/dev/null", "/dev/stdout", "/dev/stderr"}


def classify_path(file_path: str) -> tuple[str, str]:
    """Returns (stakes_level, matched_pattern) for a file path."""
    if not file_path:
        return ("low", "")

    # Patterns use "/"; normalize Windows paths
    file_path = file_path.replace("\\", "/")

    for level, patterns in LEVELS:
        for pattern in patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return (level, pattern)

    return ("low", "")


def tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        # Unbalanced quotes: fall back to a plain whitespace split
        return command.split()


def bash_targets(command: str) -> list[str]:
    """Best-effort list of files a shell command writes to or removes."""
    targets = []
    segment: list[str] = []
    tokens = tokenize(command)

    def flush():
        words = [w for w in segment if not re.match(r"^\w+=", w)]
        while words and words[0] in ("sudo", "env", "command", "nohup"):
            words = words[1:]
        if not words:
            return
        cmd, args = words[0].rsplit("/", 1)[-1], words[1:]
        operands = [a for a in args if not a.startswith("-")]
        if cmd in MODIFYING_COMMANDS:
            targets.extend(operands)
        elif cmd == "sed" and any(a.startswith("-i") or a == "--in-place" for a in args):
            targets.extend(operands[1:])

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in REDIRECTS:
            if i + 1 < len(tokens):
                target = tokens[i + 1]
                if not target.startswith("&") and target not in IGNORED_TARGETS:
                    targets.append(target)
            i += 2
            continue
        if tok in SEPARATORS:
            flush()
            segment = []
        elif tok in ("<", "<<", "<<<", ">&", "<&"):
            i += 2
            continue
        else:
            segment.append(tok)
        i += 1
    flush()

    return [t for t in targets if t not in IGNORED_TARGETS]


def extract_paths(hook_input: dict) -> list[str]:
    """Extract file paths from hook input, handling Write/Edit/Bash tools."""
    tool_input = hook_input.get("tool_input") or {}

    # Write/Edit/MultiEdit tools
    for key in ("file_path", "path"):
        if tool_input.get(key):
            return [tool_input[key]]

    command = tool_input.get("command", "")
    if command:
        return bash_targets(command)

    return []


def respond(decision: str | None, reason: str = "", context: str = "") -> None:
    output = {"hookEventName": "PreToolUse"}
    if decision:
        output["permissionDecision"] = decision
        output["permissionDecisionReason"] = reason
    if context:
        output["additionalContext"] = context
    print(json.dumps({"hookSpecificOutput": output}))


def main():
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if not raw.strip():
        sys.exit(0)

    try:
        hook_input = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    stakes, pattern, file_path = "low", "", ""
    for path in extract_paths(hook_input):
        level, matched = classify_path(path)
        if RANK[level] > RANK[stakes]:
            stakes, pattern, file_path = level, matched, path

    if stakes == "blocked":
        respond("deny", f"FORGE: Blocked path {file_path} ({pattern}). This file cannot be modified by the agent.")
    elif stakes == "critical":
        respond("ask", f"FORGE CRITICAL: {file_path} matches critical pattern ({pattern}). Schema/migration changes require explicit user approval.")
    elif stakes == "high":
        respond("ask", f"FORGE HIGH: {file_path} matches high-stakes pattern ({pattern}). Security/config changes require user approval.")
    elif stakes == "medium":
        respond(None, context=f"FORGE advisory: {file_path} is a medium-stakes file ({pattern}). If this is a design decision, call pre_action before modifying it.")

    # LOW stakes — silent pass
    sys.exit(0)


if __name__ == "__main__":
    main()
