# Kit changelog

Newest first. One line per behaviour change: `date · unit vN · what changed`. Typo/wording fixes
do not bump a version. The generated per-release log is the root [`CHANGELOG.md`](../CHANGELOG.md)
(conventional-release, [`contributing.md`](contributing.md) § Releases); this file stays the per-unit behaviour log. Dates are the
merge date in UTC, as GitHub shows it — a shared file cannot carry one machine's zone. A removed
skill or agent keeps its last version in git history: `git log --diff-filter=D -- skills/<name>` names the commit.

- 2026-09-26 · **all units** — first public release; every skill and agent starts at its current `metadata.version`.
