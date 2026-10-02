---
description: Decision-logging protocol for non-trivial development work (bug fixes, features, refactors, config changes). Uses the decisions MCP server to check guardrails and record design decisions with their rationale and outcomes.
---

# FORGE  Decision Logging Protocol

This project uses a `decisions` MCP server to keep a shared log of design decisions: what was chosen, why, and how it turned out. The log lets future work reuse what succeeded and avoid repeating what failed.

The loop: **F**etch  **O**rient  **R**esolve  **G**o  **E**xtract

## Scope

Use this protocol for non-trivial development decisions. Skip it for formatting, import ordering, typo fixes, mechanical steps (creating a file from an agreed spec, installing a dependency, running tests), and questions that don't change code.

**Test:** if you could reasonably have done this step differently and the difference would matter, it's a decision worth logging. In a multi-step plan, each such design choice is its own decision.

## Rules

1. Call `get_session_context` once at the start of a session.
2. Call `pre_action` before each MEDIUM or higher decision.
3. Call the tools in sequence. Wait for `pre_action` to return a `decisionId` before calling `record_thought`, and make `record_thought` calls one at a time rather than in parallel.
4. Finalize with `update_decision`. Don't use `log_decision` for this, because it creates a duplicate record.
5. If `pre_action` returns `allowed: false`, stop, explain the guardrail to the user, and wait for their direction.
6. For HIGH and CRITICAL decisions, get the user's confirmation before executing.
7. When the work for a decision is done, call `review_outcome`.
8. Phrase decisions as the choice made ("Use cursor pagination"), not as a question.
9. For MEDIUM and higher, give at least two kinds of reason: analysis, pattern, empirical, authority, analogy, constraint, elimination, or intuition.

## The Loop

### FETCH  Load context

```
get_session_context(task_description: "<summary of the user's request>")
```

Returns calibration data, guardrails, known patterns and relevant past decisions. Use them to inform the decisions that follow.

### ORIENT  Check guardrails and history

```
pre_action(action, category, stakes, confidence, reasons, agent_id, auto_record: true)
```

Returns a `decisionId`, similar past decisions, guardrail results and calibration.

### RESOLVE  Record the rationale

Write short rationale notes with `record_thought`, one consideration per call. These are concise summaries for the decision log (the facts, constraints, trade-offs and eliminated options that drove the choice), not a transcript of internal reasoning.

Good notes are short and specific:

- `"Requirement: 2k writes/sec"`
- `"Redis TTL covers expiry natively"`
- `"Redis single-threaded limit (~50k writes/sec) is well above need"`
- `"Memcached ruled out: no persistence"`
- `"Risk: cache warm-up after restart; mitigated by lazy loading"`

Example:

```
record_thought(text="Requirement: 10k concurrent users", decision_id=ID, agent_id="a")
record_thought(text="Team works in Python, so Go and Rust are out", decision_id=ID, agent_id="a")
record_thought(text="FastAPI is async-native; Django async support is newer", decision_id=ID, agent_id="a")
record_thought(text="Process management handled by gunicorn with uvicorn workers", decision_id=ID, agent_id="a")
record_thought(text="Matches the team's existing microservices", decision_id=ID, agent_id="a")
update_decision(id=ID, decision="FastAPI with gunicorn-managed uvicorn workers")
```

### GO  Do the work

Write the code and make the change.

### EXTRACT  Record the outcome

```
review_outcome(id=ID, outcome, actual_result, lessons)
```

If a generalizable principle emerged:

```
update_decision(id=ID, pattern: "<the principle>")
```

## Stakes Triage

Classify before acting.

| Level | Signal | Flow | Rationale notes |
|-------|--------|------|-----------------|
| **LOW** | Single file, easily reverted | Log only if it's a real design choice: ORIENT  RESOLVE  GO  EXTRACT | 23 |
| **MEDIUM** | Multiple files, design choices | ORIENT  RESOLVE  GO  EXTRACT | 36 |
| **HIGH** | Hard to reverse, wide blast radius | Confirmation flow below | 510, including risks |
| **CRITICAL** | Irreversible or security-sensitive | Confirmation flow below | 510, including risks and alternatives |

Signals:

- Reverted with a single `git revert`  LOW. Needs a migration rollback  HIGH or above.
- One file  LOW. One service  MEDIUM. Multiple services  HIGH. Affects production users  CRITICAL.
- Touches PII, credentials or user data  at least HIGH.
- A similar past decision succeeded  consider lowering the level. Novel territory  consider raising it.

### Confirmation flow (HIGH and CRITICAL)

1. Call `pre_action(..., auto_record: false)` to check guardrails and similar past decisions without creating a record.
2. Present the proposed choice to the user in chat: the decision, key reasons, risks and (for CRITICAL) the alternatives considered.
3. Wait for the user's confirmation.
4. Once approved, call `pre_action(..., auto_record: true)` to create the record and get a `decisionId`.
5. Record the rationale notes and call `update_decision`.
6. Do the work, then call `review_outcome`.

If the user declines, don't create a record unless they ask for the rejected option to be logged.

## Agent Scoping

When several agents share one MCP connection, pass both `agent_id` and `decision_id` on every `record_thought` call so notes stay attached to the right decision.

| Parameters | Tracker key | Use |
|-----------|-------------|-----|
| Neither | `mcp-session` | Single agent (fallback) |
| `agent_id` only | `agent:name` | Agent-scoped, no specific decision |
| `decision_id` only | `decision:id` | Decision-scoped, single agent |
| Both | `agent:name:decision:id` | Recommended |

## Pattern Extraction

After `review_outcome`:

- Success, no existing pattern, and two or more similar past successes  add a pattern with `update_decision`.
- Failure where a pattern exists  refine the pattern with the new constraint.
- Success that followed an existing pattern  nothing further needed.

## Calibration

Session context includes calibration data. Use it when setting confidence:

- `tendency: underconfident`  estimates of 0.70.9 usually succeed.
- `tendency: overconfident`  lower estimates by 510%.
- Check `by_category` for category-specific accuracy.

## Working With the User

- Keep logging lightweight in chat. There's no need to narrate each tool call, but if the user asks what was logged or why, tell them.
- When a past decision or pattern changes your recommendation, mention it as a recommendation rather than raw data.
- Report confidence honestly in outcomes, including partial successes and failures.
