# gh-cli — the lessons behind the traps

Why each rule in `SKILL.md` exists, in general form (no machine, no organisation, no person): the symptom,
the cause, the rule it left. Loaded on demand; the body carries the rules themselves.

## The token and the proxy

Where `gh` works through a token-injecting proxy (a sandbox), `gh auth status` reports "not logged in" although
every request succeeds — the proxy adds the credential at the network layer. `gh` still refuses to run without
*some* token, so the environment carries a placeholder as `github.sandbox_token_prefix` (`NAME=value`) and every
kit script applies it through `kit_profile.py gh-env`. On a machine whose `gh` is logged in natively the
placeholder must stay off: set, it overrides the real login and every call answers 401 — which is why the
helpers check `gh auth token` first and let a native login win. Rule: never type a token value; apply the
prefix through the helper only.

## `update-branch` needs the `workflow` scope

`PUT pulls/N/update-branch` writes a merge commit onto the PR branch. When the PR changes `.github/workflows/**`,
GitHub requires the `workflow` scope on the token, and a proxy-injected token usually lacks it: 403 on that one
call while every other call, including the later `gh pr merge`, works. Rule: on that 403 rebase the worktree and
hand the push to `sign-queue --rebase`, or hand the user the single `gh pr update-branch <n>` for their own
machine; never retry it in a loop.

## `gh pr edit` applies nothing and exits 0

On repositories still attached to the classic Projects API, `gh pr edit` fails inside its GraphQL mutation and
reports success while changing no field. Rule: edit through REST (`gh api -X PATCH repos/<o>/<r>/pulls/<n>
-f title=… -f body=…`, `POST issues/<n>/labels`) and re-read the PR afterwards — every write is verified by a read.

## A pushed head gets a bot review only when asked

A review bot re-reviews a moved head only on a fresh review request, and re-requesting an already-requested
reviewer emits no event at all. Rule: after every push (yours, an `update-branch`, a rebase) remove and re-add
the bot as reviewer (`DELETE` then `POST pulls/<n>/requested_reviewers`); `gh pr ready --undo && gh pr ready`
forces a full run when a re-request is a no-op. The `pr-watch` skill runs the sequence.

## One watcher per PR

Two sessions polling the same PR double the wake-ups and disagree about what was already reported. Rule: the
`pr-watch` skill's script is the one watcher — one process per repo per session, never a hand-rolled loop, and
never on a PR another session owns (`.context/SESSION_INDEX.md`).

## A process listing shows exported secrets

The Bash tool passes `export NAME=value` in the command's argv, so `ps -o cmd` (or `ps aux`) from any process
on the machine prints every token exported in a running command. Rule: list processes with `ps -o comm` only;
never paste a `ps` listing into the transcript.

## Two more that left a rule in the table

- `--jq` inside `gh api` takes no `--arg`: in a loop the error repeats on every iteration and only the error
  file grows. Rule: pipe into `jq`, and check both the output and the error file before trusting a background run.
- `gh pr checks --json` does not exist on older `gh`; behind `2>/dev/null` the empty output read as "still
  pending" for ten minutes. Rule: `wait-checks.sh`, and never silence a query whose empty output decides a loop.
