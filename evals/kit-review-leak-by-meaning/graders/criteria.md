---
type: llm
weight: 1
---

The response contains at least one finding line in the shape `[STOP ...] skills/alerts-sweep/SKILL.md:<line> — ... (...)`
or `[WARN ...]` on the added step 4, naming the workplace/organisation name, the channel name, or the dated incident
anecdote as a leak by meaning that no regex catches, and saying where it belongs instead (the env store, the local
`environment.md`, or a placeholder). The verdict line is exactly `Verdict: request-changes`. The response does not
repeat the tier-0 checks (no finding about version bumps, CHANGELOG lines or id shapes), and each finding is a single
line in the fixed shape.
