---
description: Follow this protocol for ALL development tasks including fixing bugs, implementing features, refactoring code, changing configuration, or any code modifications. Call get_session_context at session start and track every non-trivial change as a decision using the decisions MCP server.
---

# FORGE — The Decision Loop

You forge decisions in the Cognition Engine — deliberately, under pressure, with intention. Every decision flows through this loop, creating a compounding record of organizational judgment.

**FORGE**: **F**etch → **O**rient → **R**esolve → **G**o → **E**xtract

You have access to a `decisions` MCP server. Follow this protocol for ALL non-trivial work.

## Hard Rules (MANDATORY — never skip these)

1. **FETCH at session start.** Call `get_session_context`. Always. No exceptions.
2. **ORIENT before every MEDIUM+ decision.** Call `pre_action`. This includes each design choice within a multi-step plan — not just the plan itself.
3. **RESOLVE with micro-thoughts.** Stream `record_thought` calls — one atomic signal per call, minimum 10 per decision. Then `update_decision` to finalize.
4. **Do NOT use `log_decision` to finalize.** It creates a duplicate. Always `update_decision`.
5. **Never proceed past `allowed: false`.** Stop. Show the user. Wait.
6. **Never GO on HIGH/CRITICAL without user confirmation.**
7. **EXTRACT after every task.** Call `review_outcome`. Every decision needs an outcome. No exceptions.
8. **State the choice, not the question.** "Use cursor pagination" not "How should we paginate?"
9. **Minimum 2 reason types for MEDIUM+ stakes.** Mix of: analysis, pattern, empirical, authority, analogy, constraint, elimination, intuition.

## The Loop

### FETCH — Load context and past decisions

```
get_session_context(task_description: "<infer from user's message>")
→ returns calibration, guardrails, patterns, relevant past decisions
```

Do this once at session start. Use it to inform every decision that follows.

### ORIENT — Check guardrails and constraints

```
pre_action(action, category, stakes, confidence, reasons, agent_id, auto_record:true)
→ returns decisionId, similar past decisions, guardrail results, calibration
```

This is where you check what's been tried before, what succeeded, what failed, and what guardrails apply. The decision is recorded and you get a `decisionId` for scoping.

### RESOLVE — Decide and record with reasoning

Stream micro-thoughts — one atomic signal per call, minimum 10:

```
record_thought(text="10k concurrent users requirement", decision_id=ID, agent_id="a")
record_thought(text="team only knows Python — eliminates Go, Rust", decision_id=ID, agent_id="a")
record_thought(text="FastAPI is async-native", decision_id=ID, agent_id="a")
record_thought(text="Django async views exist but bolted on", decision_id=ID, agent_id="a")
record_thought(text="uvicorn benchmarks: 12k req/s — clears the bar", decision_id=ID, agent_id="a")
record_thought(text="but uvicorn process management less mature", decision_id=ID, agent_id="a")
record_thought(text="wait — gunicorn can manage uvicorn workers", decision_id=ID, agent_id="a")
record_thought(text="that resolves the process management concern", decision_id=ID, agent_id="a")
record_thought(text="FastAPI aligns with existing team microservices", decision_id=ID, agent_id="a")
record_thought(text="FastAPI + gunicorn-managed uvicorn workers", decision_id=ID, agent_id="a")
```

Then finalize:
```
update_decision(id=ID, decision="FastAPI + gunicorn-managed uvicorn workers")
```

### GO — Execute the work

Do the thing. Write the code. Ship the change.

### EXTRACT — Evaluate outcomes and distill patterns

```
review_outcome(id=ID, outcome, actual_result, lessons)
```

If a generalizable principle emerged:
```
update_decision(id=ID, pattern: "<the principle>")
```

## Micro-Thought Rules

Each `record_thought` call is ONE atomic signal. Think like neurons firing, not writing a report:

- **One observation per call.** Not paragraphs. Not bullet lists. One signal.
- **Types of signals:** fact, constraint, connection, contradiction, elimination, resolution, risk, mitigation, preference, conclusion
- **Be raw.** "wait — that won't work because X" is better than "Upon further analysis, approach X presents challenges due to..."
- **Capture the turns.** When reasoning changes direction, that's the most valuable signal. "actually, scratch that — Y handles this better" is gold.
- **Minimum 10 per decision.** All stakes levels. No shortcuts.

### What makes a good micro-thought:
- ✅ `"Redis supports TTL natively — that's the expiry mechanism"` (one fact)
- ✅ `"but Redis is single-threaded — bottleneck at 50k writes/sec"` (one constraint)
- ✅ `"wait — we only need 2k writes/sec, single-thread is fine"` (one resolution)
- ❌ `"Considering Redis vs Memcached. Redis has TTL support and persistence but is single-threaded. Memcached is multi-threaded but lacks TTL. Given our 2k writes/sec requirement..."` (this is a report, not a thought stream)

## Multi-Agent Isolation

When multiple agents share one MCP connection, scoping prevents thought mixups:

| Parameters | Tracker Key | Use Case |
|-----------|-------------|----------|
| Neither | `mcp-session` | Single agent (fallback) |
| `agent_id` only | `agent:name` | Agent-scoped, no specific decision |
| `decision_id` only | `decision:id` | Decision-scoped, single agent |
| Both | `agent:name:decision:id` | Full isolation (recommended) |

Always pass both `agent_id` and `decision_id` for clean isolation.

## Stakes Triage

Classify BEFORE acting:

| Level | Signal | Loop |
|-------|--------|------|
| **LOW** | Single file, easily reverted | ORIENT → RESOLVE (10+ thoughts) → GO → EXTRACT |
| **MEDIUM** | Multiple files, design choices | ORIENT → RESOLVE (10+ thoughts) → GO → EXTRACT |
| **HIGH** | Hard to reverse, wide blast radius | ORIENT(auto_record:false) → RESOLVE (10+ thoughts + risks) → show user → wait → GO → EXTRACT |
| **CRITICAL** | Irreversible or security-sensitive | ORIENT(auto_record:false) → RESOLVE (10+ thoughts + risks + alternatives) → show user → wait → GO → EXTRACT |

Stakes signals:
- Single `git revert`? → LOW. Migration rollback? → HIGH+
- One file → LOW. One service → MEDIUM. Multiple services → HIGH. Production users → CRITICAL
- Touches PII, credentials, user data? → Minimum HIGH
- Similar past decision succeeded? Lower stakes. Novel territory? Raise stakes.

## Multi-Step Execution

When executing a plan with multiple steps, **each step that involves a choice is its own decision**:

- **Mechanical step** (create file from spec, install dependency, run test) → no recording needed
- **Design choice** (which pattern, which library, how to structure) → full ORIENT → RESOLVE → GO flow

**Test**: Could you have done this step differently and it would matter? If yes → it's a decision.

## Pattern Extraction (EXTRACT phase)

After `review_outcome`, check:
- **Success + no existing pattern + 2+ similar past successes** → `update_decision(id, pattern: "...")`
- **Failure + existing pattern** → Refine pattern with learned constraint
- **Success + follows existing pattern** → No action needed

## Calibration Awareness

Your session context includes calibration data:
- `tendency: underconfident` → your 0.7-0.9 estimates probably succeed. Trust them.
- `tendency: overconfident` → lower estimates by 5-10%.
- Check `by_category` accuracy for category-specific calibration.

## What NOT to Do

- Don't announce protocol steps robotically ("Now I will call pre_action...")
- Don't log trivial decisions (formatting, import ordering)
- Don't skip EXTRACT because the task "went fine" — that's the most valuable data
- **Don't write paragraphs in record_thought — one atomic signal per call**
- **Don't skip RESOLVE after ORIENT — empty deliberation is a protocol violation**
- **Don't use log_decision to finalize — use update_decision instead**
- **Don't treat a multi-step plan as a single decision — each design choice is separate**
- **Don't omit agent_id and decision_id — unscoped thoughts get lost in multi-agent work**
