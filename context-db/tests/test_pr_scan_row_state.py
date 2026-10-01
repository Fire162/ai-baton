"""`skills/pr-scan/row-state.py`: derives one `state` (+ `section`, `state_label`) per pr-scan
candidate row from the pr-review ledger's latest entries for that PR, scoped to the row's own head.
No `gh` call — the brief (`pr-scan/SKILL.md` § Answer) renders by `.section` straight off `queue.json`
instead of re-deriving the grouping itself.

A fixture candidate set (`queue.json` shape, one row per rendered section, plus one extra row showing
an auto-policy follow-up landing in "New — not started" rather than "Follow-up — manual") and a ledger
fixture drive the script directly — no `gh` stub needed, this is a pure function of its two input
files. Stdlib unittest. Run: make -C .claude/context-db test."""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROW_STATE = Path(__file__).resolve().parents[2] / "skills" / "pr-scan" / "row-state.py"
REPO = "acme/widgets"

# one made-up 40-char head sha per row, for readability keyed by row number
HEADS = {
    601: "a" * 40, 602: "b" * 40, 603: "c" * 40, 604: "d" * 40,
    605: "e" * 40, 606: "f" * 40, 607: "1" * 40, 608: "2" * 40,
}
OLD_HEAD_607 = "0" * 40  # the head our prior review on #607 was posted against
OLD_HEAD_608 = "9" * 40  # ditto for #608


def row(pr: int, kind: str = "new", eligible: bool = False) -> dict:
    return {"repo": REPO, "pr": pr, "head": HEADS[pr], "kind": kind,
            "auto_comment": {"eligible": eligible}}


QUEUE = [
    row(601),                                   # no ledger entry at all
    row(602),                                   # held on this head
    row(603, kind="follow_up"),                 # author replied in a thread we opened
    row(604),                                   # our REQUEST_CHANGES on this head, still open
    row(605),                                   # our APPROVE on this head, still open
    row(606),                                   # our COMMENT review on this head — handled
    row(607, kind="re_review", eligible=False),  # review on an older head, manual policy
    row(608, kind="re_review", eligible=True),   # review on an older head, auto policy
]

LEDGER = [
    {"repo": REPO, "pr": 602, "head": HEADS[602], "status": "held", "ts": "2026-09-01T00:00:00Z"},
    {"repo": REPO, "pr": 604, "head": HEADS[604], "status": "reviewed", "event": "REQUEST_CHANGES",
     "review_id": 400004, "ts": "2026-09-01T00:00:00Z"},
    {"repo": REPO, "pr": 605, "head": HEADS[605], "status": "reviewed", "event": "APPROVE",
     "review_id": 500005, "ts": "2026-09-01T00:00:00Z"},
    {"repo": REPO, "pr": 606, "head": HEADS[606], "status": "reviewed", "event": "COMMENT",
     "review_id": 600006, "ts": "2026-09-01T00:00:00Z"},
    {"repo": REPO, "pr": 607, "head": OLD_HEAD_607, "status": "reviewed", "event": "COMMENT",
     "review_id": 700007, "ts": "2026-08-01T00:00:00Z"},
    {"repo": REPO, "pr": 608, "head": OLD_HEAD_608, "status": "reviewed", "event": "COMMENT",
     "review_id": 800008, "ts": "2026-08-01T00:00:00Z"},
]

EXPECTED = {
    601: ("new", "New — not started"),
    602: ("needs_you", "Needs you"),
    603: ("needs_you", "Needs you"),
    604: ("needs_you", "Needs you"),
    605: ("watching", "Watching"),
    606: ("handled", "Handled this tick"),
    607: ("follow_up", "Follow-up — manual"),
    608: ("follow_up", "New — not started"),
}


class RowStateSections(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kit-prscan-rowstate-test."))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.queue_path = self.tmp / "queue.json"
        self.ledger_path = self.tmp / "ledger.jsonl"
        self.queue_path.write_text(json.dumps(QUEUE))
        self.ledger_path.write_text("".join(json.dumps(r) + "\n" for r in LEDGER))

    def run_row_state(self) -> list[dict]:
        r = subprocess.run(
            [sys.executable, str(ROW_STATE), "--queue", str(self.queue_path), "--ledger", str(self.ledger_path)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def test_each_row_lands_in_the_expected_section(self):
        out = self.run_row_state()
        by_pr = {r["pr"]: r for r in out}
        self.assertEqual(set(by_pr), set(EXPECTED))
        for pr, (state, section) in EXPECTED.items():
            got = by_pr[pr]
            self.assertEqual(got["state"], state, f"pr {pr}: {got}")
            self.assertEqual(got["section"], section, f"pr {pr}: {got}")

    def test_handled_row_links_the_review_id_in_its_label(self):
        out = self.run_row_state()
        row606 = next(r for r in out if r["pr"] == 606)
        self.assertIn("600006", row606["state_label"])

    def test_missing_ledger_file_treats_every_row_as_new(self):
        missing = self.tmp / "no-such-ledger.jsonl"
        r = subprocess.run(
            [sys.executable, str(ROW_STATE), "--queue", str(self.queue_path), "--ledger", str(missing)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        by_pr = {row["pr"]: row for row in out}
        # #603 is still "needs_you" on an empty ledger — `kind=follow_up` alone drives that state
        self.assertEqual(by_pr[603]["section"], "Needs you")
        self.assertEqual(by_pr[601]["section"], "New — not started")
        self.assertEqual(by_pr[605]["section"], "New — not started")  # no ledger entry -> no APPROVE to find


if __name__ == "__main__":
    unittest.main()
