"""gen_sessions.py — the archive sweep and the two generated indexes, on a throwaway CONTEXT_ROOT."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "bin"


def session_file(root: Path, name: str, status: str, ended_days_ago: float, next_prompt: str, hb: str = "") -> Path:
    hb = hb or (datetime.now(timezone.utc) - timedelta(days=ended_days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = f"# Session: {name}\n\n## Next session\n\n{next_prompt}\n\n## Session stats\n\nnone\n"
    p = root / "sessions" / f"{name}.md"
    p.write_text(f"---\nsession: {name}\nref: abc123\nstatus: {status}\nepic: E-1\nworking_on: x\n"
                 f"responsibilities: y\nstats: 1 turns · 0.1h · ~$1\nheartbeat: {hb}\nupdated: 2026-09-26\n---\n\n{body}",
                 encoding="utf-8")
    return p


def env_for(root: Path, **extra: str) -> dict:
    # No WORKSPACE_TZ: the generator must resolve the zone from the temp root's own (blank) env store,
    # exactly as it does on a CI runner — a shell that exports it would otherwise mask a missing store.
    env = {k: v for k, v in os.environ.items() if k != "WORKSPACE_TZ"}
    return {**env, "CONTEXT_ROOT": str(root), **extra}


def run(root: Path, *args: str, days: str = "7") -> str:
    env = env_for(root, SESSION_ARCHIVE_DAYS=days, SESSION_ARCHIVE_NOPROMPT_HOURS="48", SESSION_INDEX_MAX_ENDED="5")
    r = subprocess.run([sys.executable, str(BIN / "gen_sessions.py"), *args], env=env, cwd=BIN,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


class ArchiveSweep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # the generator reads the env config (tz_default) from CONTEXT_ROOT — give the temp root a blank store
        r = subprocess.run([sys.executable, str(BIN / "kb.py"), "init", "--blank"], env=env_for(self.root),
                           cwd=BIN, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        (self.root / "sessions").mkdir()
        session_file(self.root, "live", "active", 0, "")
        session_file(self.root, "fresh-with-prompt", "ended", 1, "Register as fresh-2, read X.")
        session_file(self.root, "fresh-no-prompt", "ended", 1, "")  # crashed session inside the 48 h grace window
        session_file(self.root, "stale-no-prompt", "ended", 3, "")
        session_file(self.root, "old-with-prompt", "ended", 30, "Register as old-2.")
        session_file(self.root, "bad-heartbeat", "ended", 0, "Register as bad-2.", hb="yesterday")
        (self.root / "sessions" / "_ledger.md").write_text("| a | b |\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_moves_nothing(self):
        out = run(self.root, "--dry-run")
        self.assertIn("would archive stale-no-prompt", out)
        self.assertIn("would archive old-with-prompt", out)
        self.assertNotIn("would archive fresh-with-prompt", out)
        self.assertNotIn("would archive fresh-no-prompt", out)
        self.assertNotIn("would archive bad-heartbeat", out)
        self.assertFalse((self.root / "sessions" / "archive").exists())
        self.assertFalse((self.root / "SESSION_INDEX.md").exists())

    def test_sweep_moves_only_what_nothing_waits_on(self):
        out = run(self.root)
        self.assertIn("2 archived (2 in sessions/archive/)", out)
        live = sorted(p.name for p in (self.root / "sessions").glob("*.md"))
        self.assertEqual(live, ["_ledger.md", "bad-heartbeat.md", "fresh-no-prompt.md", "fresh-with-prompt.md", "live.md"])
        arch = sorted(p.name for p in (self.root / "sessions" / "archive").glob("*.md"))
        self.assertEqual(arch, ["INDEX.md", "old-with-prompt.md", "stale-no-prompt.md"])
        idx = (self.root / "SESSION_INDEX.md").read_text()
        self.assertIn("`fresh-with-prompt`", idx)
        self.assertIn("`fresh-no-prompt`", idx)
        self.assertNotIn("old-with-prompt", idx)
        self.assertNotIn("<details>", idx)
        aidx = (self.root / "sessions" / "archive" / "INDEX.md").read_text()
        self.assertIn("| `old-with-prompt` | E-1 |", aidx)
        self.assertIn("Register as old-2.", aidx)
        self.assertIn("2 archived_", aidx)
        # a second run is a no-op that keeps the archive index in step
        out2 = run(self.root)
        self.assertNotIn(" archived", out2)  # no new moves
        self.assertIn("(2 in sessions/archive/)", out2)

    def test_no_archive_flag_and_zero_days(self):
        run(self.root, "--no-archive")
        self.assertFalse((self.root / "sessions" / "archive").exists())
        self.assertTrue((self.root / "SESSION_INDEX.md").exists())
        run(self.root, days="0")  # every ended session — except one whose ended-at cannot be parsed
        self.assertEqual(sorted(p.name for p in (self.root / "sessions").glob("*.md")),
                         ["_ledger.md", "bad-heartbeat.md", "live.md"])

    def test_name_collision_gets_dated_suffix(self):
        run(self.root)  # archives stale-no-prompt
        session_file(self.root, "stale-no-prompt", "ended", 4, "")
        run(self.root)
        names = sorted(p.name for p in (self.root / "sessions" / "archive").glob("stale-no-prompt*.md"))
        self.assertEqual(len(names), 2)
        self.assertTrue(any(n.startswith("stale-no-prompt-20") for n in names))

    def test_vanished_file_is_skipped_not_fatal(self):
        # a concurrent regen sweeps a row between our glob and our os.replace: in-process, with archive_path
        # patched to remove the source first, so the real os.replace raises and the except branch is exercised
        import importlib
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        env = env_for(self.root, SESSION_ARCHIVE_DAYS="7", SESSION_ARCHIVE_NOPROMPT_HOURS="48")
        with mock.patch.dict(os.environ, env, clear=True):  # undone on exit — nothing leaks into later tests
            sys.path.insert(0, str(BIN))
            try:
                gen = importlib.reload(importlib.import_module("gen_sessions"))
            finally:
                sys.path.pop(0)
            real = gen.archive_path

            def steal_then_path(name, m):
                dst = real(name, m)
                if name == "old-with-prompt":
                    os.unlink(m["_path"])  # the other regen got there first
                return dst

            buf = io.StringIO()
            with mock.patch.object(gen, "archive_path", steal_then_path), redirect_stdout(buf):
                rc = gen.main([])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("1 archived", out)  # stale-no-prompt moved, old-with-prompt skipped, no traceback
        self.assertNotIn("old-with-prompt", (self.root / "SESSION_INDEX.md").read_text())
        self.assertFalse((self.root / "sessions" / "archive" / "old-with-prompt.md").exists())

    def test_doc_without_session_field_restores_by_stem(self):
        # a hand-written doc has no `session:` line — the sweep names it by its stem, so the restore must too
        p = session_file(self.root, "handmade", "ended", 3, "")
        p.write_text("\n".join(l for l in p.read_text().splitlines() if not l.startswith("session:")) + "\n")
        run(self.root)
        self.assertTrue((self.root / "sessions" / "archive" / "handmade.md").exists())
        r = subprocess.run([sys.executable, str(BIN / "session.py"), "touch", "--name", "handmade", "--no-stats"],
                           env=env_for(self.root), cwd=BIN, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("restored handmade.md from sessions/archive/handmade.md", r.stdout)
        self.assertTrue((self.root / "sessions" / "handmade.md").exists())
        live = self.root / "sessions" / "handmade.md"
        self.assertIn("session: handmade", live.read_text())  # the write-back names the doc, no blank field
        self.assertFalse((self.root / "sessions" / "archive" / "handmade.md").exists())  # moved, not copied
        # age it past the window again: the round-trip must land under the same archive name, never `.md`
        old_hb = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        live.write_text(re.sub(r"^heartbeat: .*$", f"heartbeat: {old_hb}", live.read_text(), flags=re.M))
        run(self.root)
        self.assertEqual(sorted(p.name for p in (self.root / "sessions" / "archive").glob("handmade*.md")), ["handmade.md"])
        self.assertFalse((self.root / "sessions" / "archive" / ".md").exists())

    def test_resumed_session_refines_handoff_after_archive(self):
        # crashed session: ended without a prompt, archived after the grace window, resumed later —
        # session-end … --next must find the file (moved back from the archive) and the prompt then keeps it live
        run(self.root)
        self.assertTrue((self.root / "sessions" / "archive" / "stale-no-prompt.md").exists())
        nxt = self.root / "next.md"
        nxt.write_text("Register as stale-2, re-arm the watch on #1.")
        r = subprocess.run([sys.executable, str(BIN / "session.py"), "end", "--name", "stale-no-prompt",
                            "--next", str(nxt), "--no-stats"], env=env_for(self.root), cwd=BIN,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("restored stale-no-prompt.md from sessions/archive/", r.stdout)
        self.assertTrue((self.root / "sessions" / "stale-no-prompt.md").exists())
        self.assertFalse((self.root / "sessions" / "archive" / "stale-no-prompt.md").exists())
        self.assertIn("Register as stale-2", (self.root / "SESSION_INDEX.md").read_text())

    def test_restore_picks_the_newest_archived_file_for_a_reused_name(self):
        run(self.root)  # stale-no-prompt (3 d) → archive/stale-no-prompt.md
        session_file(self.root, "stale-no-prompt", "ended", 2.5, "")  # same name, later lane, 60 h > 48 h
        run(self.root)  # → archive/stale-no-prompt-YYYYMMDD.md (name taken)
        self.assertEqual(len(list((self.root / "sessions" / "archive").glob("stale-no-prompt*.md"))), 2)
        session_file(self.root, "stale-no-prompt-20260901", "ended", 2.2, "")  # a lane named after a date, newer
        run(self.root)  # swept too — must never be restored under the other name
        # a successor re-registering the swept name (step 1: "register under the name it proposes") continues
        # the newest doc — never the older lane's — and a later touch finds the live file
        outs = []
        for cmd in (["register"], ["touch"]):
            r = subprocess.run([sys.executable, str(BIN / "session.py"), cmd[0], "--name", "stale-no-prompt",
                                *cmd[1:], "--no-stats"], env=env_for(self.root), cwd=BIN,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            outs.append(r.stdout)
        self.assertRegex(outs[0], r"restored stale-no-prompt\.md from sessions/archive/stale-no-prompt-\d{8}\.md")
        self.assertNotIn("restored", outs[1])
        left = sorted(p.name for p in (self.root / "sessions" / "archive").glob("stale-no-prompt*.md"))
        self.assertEqual(left, ["stale-no-prompt-20260901.md", "stale-no-prompt.md"])  # older lane + stranger stay archived
        self.assertIn("status: active", (self.root / "sessions" / "stale-no-prompt.md").read_text())  # re-registered = active
        self.assertIn("`stale-no-prompt`", (self.root / "SESSION_INDEX.md").read_text().split("## Ended")[0])

    def test_bad_days_value_falls_back(self):
        out = run(self.root, "--dry-run", days="abc")
        self.assertIn("would archive old-with-prompt", out)
        self.assertNotIn("would archive fresh-with-prompt", out)


if __name__ == "__main__":
    unittest.main()
