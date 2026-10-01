#!/usr/bin/env python3
"""row-state.py --queue FILE --ledger FILE

Derives one `state` (+ `section`, `state_label`) per pr-scan candidate row from the
pr-review ledger's latest entries for that PR, scoped to the row's own head. No `gh`
calls — everything needed is already in queue.json and the ledger.

Precedence (first match wins), per row:
  1. a `held` ledger entry on this exact head           -> needs_you (STOP)
  2. kind == follow_up (author replied after our review) -> needs_you (author replied)
  3. our REQUEST_CHANGES on this head, still open        -> needs_you (you REQUEST_CHANGES)
  4. our APPROVE on this head, still open                -> watching
  5. a reviewed/auto_commented ledger entry on this head -> handled this tick
  6. an older-head review, or kind == re_review          -> follow-up (auto|manual policy)
  7. otherwise                                           -> new (auto|manual policy)

The auto/manual policy bit for states 6 and 7 is read straight off the row's own
`auto_comment.eligible` field (already computed by pr-scan.sh's gh-call-free gate) —
this script does not re-read config.json or recompute eligibility itself. An
auto-policy follow-up (a direct re-request `auto_comment` already covers via
`include_re_review`) needs no action from the user, same as an auto-eligible new
request, so it renders in the New section; only a manual-policy follow-up — the one
that actually needs a human decision — lands in the Follow-up section, matching that
section's "— manual" name.

Reads queue.json (a JSON array) and ledger.jsonl (JSON-lines, may be missing or
empty); writes the same array back to stdout with `state`, `section` and
`state_label` added to every row.
"""
import argparse
import json
import sys

SECTION_NEEDS_YOU = "Needs you"
SECTION_NEW = "New — not started"
SECTION_HANDLED = "Handled this tick"
SECTION_FOLLOWUP = "Follow-up — manual"
SECTION_WATCHING = "Watching"


def load_ledger(path):
    rows = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except FileNotFoundError:
        pass
    return rows


def derive_state(row, ledger_rows):
    repo, pr, head = row.get("repo"), row.get("pr"), row.get("head")
    kind = row.get("kind", "new")
    mine = [e for e in ledger_rows if e.get("repo") == repo and e.get("pr") == pr]
    cur = [e for e in mine if e.get("head") == head]
    held = any(e.get("status") == "held" for e in cur)
    handled_cur = [e for e in cur if e.get("status") in ("reviewed", "auto_commented")]
    request_changes = any(e.get("event") == "REQUEST_CHANGES" for e in handled_cur)
    approve = any(e.get("event") == "APPROVE" for e in handled_cur)
    older_handled = any(
        e.get("status") in ("reviewed", "auto_commented") and e.get("head") != head
        for e in mine
    )
    review_id = next(
        (e.get("review_id") for e in handled_cur if e.get("review_id") is not None), None
    )
    eligible = bool((row.get("auto_comment") or {}).get("eligible"))

    if held:
        return "needs_you", SECTION_NEEDS_YOU, "needs you (STOP)"
    if kind == "follow_up":
        return "needs_you", SECTION_NEEDS_YOU, "needs you (author replied)"
    if request_changes:
        return "needs_you", SECTION_NEEDS_YOU, "needs you (you REQUEST_CHANGES)"
    if approve:
        return "watching", SECTION_WATCHING, "watching"
    if handled_cur:
        label = f"handled (review #{review_id})" if review_id is not None else "handled"
        return "handled", SECTION_HANDLED, label

    policy = "auto" if eligible else "manual"
    if older_handled or kind == "re_review":
        section = SECTION_NEW if policy == "auto" else SECTION_FOLLOWUP
        return "follow_up", section, f"follow-up ({policy})"
    return "new", SECTION_NEW, f"new ({policy})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--ledger", required=True)
    args = ap.parse_args()

    with open(args.queue) as f:
        rows = json.load(f)
    ledger_rows = load_ledger(args.ledger)

    out = []
    for row in rows:
        state, section, label = derive_state(row, ledger_rows)
        out.append({**row, "state": state, "section": section, "state_label": label})
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
