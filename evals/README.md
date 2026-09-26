# evals/ — the eval suite, one case per directory, per skill

Cases live **outside** `skills/<name>/` so the installed skill stays lean (CONTRIBUTING.md § Skills). The format is
the one `claude plugin eval` runs: `evals/<skill>-<case>/prompt.md` (frontmatter `max_turns`, `allowed_tools`; the
body is what the user says) plus `graders/*.md` (frontmatter `type: llm`, `weight`; the body is the pass criterion).
`claude plugin eval init --bare <skill>-<case>` writes a blank case; `claude plugin eval` scores the suite and writes
`evals/results/` (not committed).

Every skill ships ≥ 10 trigger cases: positives and **same-domain near misses** (the description's "Not for …"
clause, as a case that must not fire). `docs/templates/evals/` holds one of each — copy here, rename to
`<skill>-<case>`, fill the `<…>` marks (the scaffold sits under `docs/` so the runner never scores a placeholder). No case carries a real id, host, person or organisation — placeholders only. The wiring into CI and
the plugin manifest (`experimental.evals`) is #98's.
