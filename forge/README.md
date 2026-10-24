# FORGE — The Decision Loop

A Claude Code plugin that implements the FORGE cognitive decision protocol.

**FORGE**: **F**etch → **O**rient → **R**esolve → **G**o → **E**xtract

You forge decisions in the Cognition Engine — deliberately, under pressure, with intention. Every decision flows through this loop, creating a compounding record of organizational judgment.

## What it does

- **FETCH**: Loads cognitive context (past decisions, calibration, patterns, guardrails) at session start
- **ORIENT**: Checks guardrails and constraints before every non-trivial decision via `pre_action`
- **RESOLVE**: Records short rationale notes (2–10 per decision, scaled by stakes) via `record_thought`
- **GO**: Executes with confidence, gates HIGH/CRITICAL decisions on user confirmation
- **EXTRACT**: Reviews outcomes and distills patterns via `review_outcome`

## Components

- **Skill** (`skills/forge-protocol/SKILL.md`): Protocol rules loaded contextually
- **Hooks** (`hooks/hooks.json`): SessionStart injects protocol, PreToolUse gates risky file ops, Stop enforces reflection
- **MCP** (`.mcp.json`): Connects to the decisions server
- **Commands**: `/forge:status` dashboard, `/forge:reflect` batch review

## Installation

```bash
claude --plugin-dir ./path-to-forge-plugin
```

Or from the marketplace:

```
/plugin marketplace add tfatykhov/cognition-engines-marketplace
/plugin install forge@cognition-engines
```

## Requirements

- Decisions MCP server running
- Python 3.10+ for hook scripts

## Configuration

| Variable | Used by | Default |
|----------|---------|---------|
| `CSTP_MCP_URL` | `.mcp.json` | `http://localhost:9991/mcp` |
| `CSTP_TOKEN` | MCP server and API mode | (none) |
| `FORGE_MODE` | SessionStart hook: `prompt` injects the protocol only, `api` also loads live context | `prompt` |
| `CSTP_URL` | SessionStart hook in `api` mode, e.g. `http://localhost:9991` | (none; required for `api` mode) |

`ACCER_MODE` is still accepted as a legacy alias for `FORGE_MODE`.

## Tests

```bash
python3 -m unittest discover -s forge/tests
```
