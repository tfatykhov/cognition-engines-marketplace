# /forge:status

Show FORGE decision protocol status dashboard.

Call `get_session_context` and display:
1. **Calibration**: Brier score, accuracy, confidence tendency
2. **Pending reviews**: Decisions awaiting `review_outcome`
3. **Active guardrails**: Current blocking/warning rules
4. **Confirmed patterns**: Patterns with 2+ reinforcements
