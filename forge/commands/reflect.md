# /forge:reflect

Walk through unreflected decisions from this session.

For each pending decision:
1. Show the decision summary, confidence, and stakes
2. Ask: what was the outcome? (success / partial / failure / abandoned)
3. Ask: what actually happened?
4. Ask: any lessons learned?
5. Call `review_outcome` with the answers
6. If a pattern emerged, call `update_decision(id, pattern: "...")`
