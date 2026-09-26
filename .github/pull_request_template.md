<!--
Title = the squash commit on main. Conventional Commits (docs/commit-style.md), lower-case subject,
no trailing period, ≤ 72 characters:

  feat(pr-open): derive the diagram set from the diff
  fix(sync): release the mkdir lock on hosts without flock
  docs(kit): new-environment migration steps
  ci(kit): add the pr-issue check

Types: feat fix docs chore refactor test ci build perf style revert
-->

Closes #
<!-- Every PR comes from an issue. "Closes #N" = this PR finishes it (GitHub closes it on merge).
     "Refs #N" = one step of a larger issue, which stays open. No issue yet? Create it first.
     The pr-issue check fails without one. -->

## What

## Why

## Units touched

<!-- Each skill/agent whose behaviour changes: `name vN → vN+1`. Wording-only edits bump nothing — say so. -->

## Verified how

- [ ] `make -C context-db kit-verify` green locally (CI runs it against a blank env store)
- [ ] versions bumped + `docs/CHANGELOG.md` line added — or wording only
- [ ] no environment-specific value (ids, orgs, channels, hosts, token prefixes) added to a core file
- [ ] capabilities affected (every machine, or the `systems.*` flags involved) named above, with any `kb.py migrate` / `kb.py config-set …` or
      migration step a machine needs after `make claude_sync`
- [ ] `/kit-health` run on at least one machine after the change
