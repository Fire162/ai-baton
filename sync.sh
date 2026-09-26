#!/usr/bin/env bash
# sync.sh — keep the .claude kit in step with origin, PR-only: the kit is PULLED (fast-forward of
# `main`), never committed or pushed from here. Kit changes travel branch → PR → merge on GitHub;
# a versioned pre-push hook (hooks/pre-push, installed via core.hooksPath by this script and
# setup.sh) refuses any push to the kit's `main`. Nothing else is synced: an environment's facts
# live in the local env store (.context/reference/env/, never in git), its prose in
# .context/reference/environment.md. Idempotent, lock-guarded, never fails the caller (it is also
# run from a SessionEnd hook). Takes no arguments.
#
#   sh .claude/sync.sh                  (from the workspace root, or via `make claude_sync`)
#
# Outcome is recorded in .sync-status (ignored; one line: `<utc-ts> ok|error <detail>`) so a
# later session can see that a background sync failed — the SessionEnd hook swallows all output.
# `sync-check.sh` (run by `make -C .claude/context-db session-register`) reads it. The sync
# reports `error` — and pulls nothing — when .claude/ is not on main, has uncommitted changes, or
# carries local commits on main: each of those is work that must move to a branch + PR.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG="$HERE/sync.log"
STATUS="$HERE/.sync-status"
FAIL=""; PULLED=""

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >>"$LOG"; }
status() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >"$STATUS"; }
# " (v0.3.0)" on a release commit, " (v0.3.0+2)" two commits after it, "" before the first release tag
kit_version() {
  d="$(git describe --tags --match 'v[0-9]*' --long 2>/dev/null)" || return 0
  n="${d%-g*}"; n="${n##*-}"; t="${d%-*-g*}"
  [ "$n" = 0 ] && printf ' (%s)' "$t" || printf ' (%s+%s)' "$t" "$n"
}

# sync_kit — PR-only: install the pre-push guard, then fast-forward main to origin/main when the
# checkout is clean. Never stages, commits or pushes. Sets FAIL (and pulls nothing) when the
# checkout is off main, dirty, or ahead of origin — that work belongs on a branch + PR.
sync_kit() {
  cd "$HERE" || return 1
  [ -d .git ] || { log "kit: skip, not a git repo"; return 0; }
  if [ "$(git config --get core.hooksPath 2>/dev/null)" != "$HERE/hooks" ]; then
    git config core.hooksPath "$HERE/hooks" >>"$LOG" 2>&1 && log "kit: installed git hooks pre-push + commit-msg (core.hooksPath=$HERE/hooks)"
  fi
  local branch; branch="$(git symbolic-ref -q --short HEAD 2>/dev/null || echo DETACHED)"
  if [ "$branch" != "main" ]; then
    log "kit: ERROR checked out on '$branch' — .claude/ must stay on main"
    FAIL="kit is on '$branch' — .claude/ must stay on main (git switch main); branch work lives in a worktree under .worktrees/"
    return 1
  fi
  if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    log "kit: ERROR uncommitted changes in .claude/ — pull skipped (main is PR-only)"
    FAIL="kit has uncommitted changes in .claude/ — main is PR-only: move them to a branch worktree (git worktree add .worktrees/kit_<topic> -b <topic>) and open a PR"
    return 1
  fi
  git remote get-url origin >/dev/null 2>&1 || { log "kit: skip, no origin"; return 0; }
  if ! git fetch -q origin >>"$LOG" 2>&1; then
    log "kit: ERROR fetch failed"; FAIL="kit fetch failed (see sync.log)"; return 1
  fi
  local ahead; ahead="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
  if [ "$ahead" -gt 0 ]; then
    log "kit: ERROR $ahead local commit(s) on main not on origin — main is PR-only, nothing pushed"
    FAIL="kit has $ahead local commit(s) on main that will never be pushed — main is PR-only: git branch <topic> && git reset --hard origin/main, then open a PR from <topic>"
    return 1
  fi
  if git merge -q --ff-only origin/main >>"$LOG" 2>&1; then
    log "kit: main at $(git rev-parse --short HEAD)$(kit_version)"; PULLED="kit@$(git rev-parse --short HEAD)"
  else
    log "kit: ERROR fast-forward failed"; FAIL="kit fast-forward to origin/main failed (see sync.log)"; return 1
  fi
}

# lock: flock where it exists (Linux); on hosts without it (macOS without coreutils) an atomic mkdir
# lock, treated as stale after 10 minutes. A busy lock is logged AND recorded in .sync-status so
# `make claude_sync` / sync-check.sh say why nothing was pulled.
LOCKDIR="$HERE/.sync.lock.d"
release_lockdir() { rmdir "$LOCKDIR" 2>/dev/null; }
take_lock() {
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$HERE/.sync.lock"
    flock -w 30 9 && return 0
    log "skip: lock busy — another sync.sh holds .sync.lock (hung SessionEnd sync? \`pgrep -af sync.sh\`, kill it)"
  else
    if mkdir "$LOCKDIR" 2>/dev/null; then trap release_lockdir EXIT; return 0; fi
    if [ -n "$(find "$LOCKDIR" -maxdepth 0 -mmin +10 2>/dev/null)" ]; then
      rmdir "$LOCKDIR" 2>/dev/null
      if mkdir "$LOCKDIR" 2>/dev/null; then log "lock: removed a stale lock dir (>10 min)"; trap release_lockdir EXIT; return 0; fi
    fi
    log "skip: lock busy — no flock on this host and $LOCKDIR exists (another sync running; \`rmdir\` it if none is)"
  fi
  status "error lock busy — another sync.sh is running or a stale lock is left; see sync.log"
  return 1
}
take_lock || exit 0

[ -d "$HERE/.git" ] || { log "skip: .claude is not a git repo"; exit 0; }
sync_kit

if [ -n "$FAIL" ]; then status "error $FAIL"
else status "ok ${PULLED:-kit no-origin}"; fi
exit 0
