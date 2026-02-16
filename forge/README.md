# FORGE — The Decision Loop

A Claude Code plugin that implements the FORGE cognitive decision protocol.

**FORGE**: **F**etch → **O**rient → **R**esolve → **G**o → **E**xtract

You forge decisions in the Cognition Engine — deliberately, under pressure, with intention. Every decision flows through this loop, creating a compounding record of organizational judgment.

## What it does

- **FETCH**: Loads cognitive context (past decisions, calibration, patterns, guardrails) at session start
- **ORIENT**: Checks guardrails and constraints before every non-trivial decision via `pre_action`
- **RESOLVE**: Streams micro-thought deliberation (10+ atomic signals per decision) via `record_thought`
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

## Requirements

- Decisions MCP server running (default: http://192.168.1.141:9991/mcp)
- Python 3 for hook scripts
