"""session_stats.py + transcripts.py on a synthetic transcript (usage de-dup, tool mix, PRs, subagents, pricing,
the rendered line/block). Stdlib unittest. Run: make -C .claude/context-db test."""
from __future__ import annotations
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "bin"
sys.path.insert(0, str(BIN))

import session_stats as ss  # noqa: E402
import transcripts  # noqa: E402


def usage(i=1000, cw=0, cr=0, out=100):
    return {"input_tokens": i, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr, "output_tokens": out}


def assistant(rid: str, ts: str, content=None, model="claude-opus-x", u=None):
    return {"type": "assistant", "requestId": rid, "timestamp": ts,
            "message": {"id": f"msg_{rid}", "model": model, "usage": u or usage(), "content": content or [{"type": "text", "text": "ok"}]}}


def tool(name: str, **inp):
    return {"type": "tool_use", "name": name, "input": inp}


LINES = [
    {"type": "user", "timestamp": "2026-09-26T10:00:00Z", "message": {"content": "start the work"}},
    assistant("r1", "2026-09-26T10:00:05Z", [tool("Bash", command="gh pr create --title x"), tool("Read", file_path="a")]),
    assistant("r1", "2026-09-26T10:00:05Z"),  # the same request written twice: one turn, not two
    {"type": "user", "timestamp": "2026-09-26T10:01:00Z", "message": {"content": [{"type": "tool_result", "content": "done"}]}},
    assistant("r2", "2026-09-26T10:30:00Z", [tool("Agent", prompt="x"), tool("Bash", command="see https://github.com/acme/repo/pull/42")],
              model="claude-sonnet-x", u=usage(i=0, cr=10_000, cw=2_000, out=50)),
    {"type": "pr-link", "prRepository": "acme/repo", "prNumber": 7, "timestamp": "2026-09-26T10:31:00Z"},
    {"type": "assistant", "isCompactSummary": True, "timestamp": "2026-09-26T11:00:00Z", "message": {}},
    "this line is not json",
    {"type": "user", "timestamp": "2026-09-26T12:00:00Z", "message": {"content": "<system-reminder>ignored</system-reminder>"}},
]


class Transcript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        proj = Path(self.tmp.name) / ".claude" / "projects" / "-home-x"
        proj.mkdir(parents=True)
        self.path = proj / "sess-1.jsonl"
        self.path.write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in LINES) + "\n", encoding="utf-8")
        sub = proj / "sess-1" / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-a.jsonl").write_text(json.dumps(assistant("s1", "2026-09-26T10:31:00Z", model="claude-haiku-x", u=usage(i=1_000_000))) + "\n"
                                           + json.dumps(assistant("s1", "2026-09-26T10:31:00Z")) + "\n", encoding="utf-8")
        (sub / "agent-b.jsonl").write_text("garbage\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_usage_records_dedupe_across_files_and_skip_junk(self):
        seen: set[str] = set()
        recs = list(transcripts.usage_records(str(self.path), seen))
        self.assertEqual([r[3] for r in recs], ["r1", "r2"])
        self.assertEqual(transcripts.tokens(recs[1][2]), (0, 2_000, 10_000, 50))
        self.assertEqual(list(transcripts.usage_records(str(self.path), seen)), [])  # already seen
        self.assertEqual(list(transcripts.usage_records("/nonexistent.jsonl")), [])
        self.assertEqual(len(transcripts.subagent_files(str(self.path))), 2)
        home = self.tmp.name
        self.assertEqual(transcripts.find_transcript("sess-1", home), str(self.path))
        self.assertIsNone(transcripts.find_transcript("nope", home))
        self.assertEqual(len(transcripts.all_transcripts(home)), 3)

    def test_collect(self):
        s = ss.collect(str(self.path))
        self.assertEqual(s["turns"], 2)
        self.assertEqual(s["prompts"], 1)  # the tool_result and the <system-reminder> lines are not prompts
        self.assertEqual(s["tokens"], {"input": 1000, "cache_write": 2000, "cache_read": 10000, "output": 150, "thinking": 0})
        self.assertEqual(s["context"], {"peak": 12000, "avg": 6500})
        self.assertEqual(s["compactions"], 1)
        self.assertEqual(s["tool_calls"], 4)
        self.assertEqual(dict(s["tools_top"])["Bash"], 2)
        self.assertEqual(s["subagents"], 1)
        self.assertEqual(s["prs_opened"], 1)
        self.assertEqual(s["prs_touched"], [("acme/repo", "42"), ("acme/repo", "7")])
        self.assertEqual(s["models"], {"claude-opus-x": 1, "claude-sonnet-x": 1})
        self.assertEqual(s["wall_hours"], 2.0)  # 10:00 → 12:00 (the last timestamped line, whatever its type)
        # spend: opus 1000 in + 100 out = 0.015 + 0.0075; sonnet 2000 cw + 10000 cr + 50 out = 0.0075 + 0.003 + 0.00075
        self.assertAlmostEqual(s["spend_usd_est"], 0.03, places=2)
        sub = s["subagents_cost"]
        self.assertEqual((sub["files"], sub["turns"]), (2, 1))
        self.assertEqual(sub["models"], {"claude-haiku-x": 1})
        self.assertAlmostEqual(sub["spend_usd_est"], 1.0 + 0.0005, places=3)  # haiku: 1M in at $1 + 100 out
        self.assertAlmostEqual(s["spend_total_usd_est"], s["spend_usd_est"] + sub["spend_usd_est"], places=2)

    def test_render_line_and_block(self):
        s = ss.collect(str(self.path))
        line = ss.fmt_line(s)
        self.assertNotIn("|", line)
        self.assertNotIn("\n", line)
        self.assertIn("2 turns · 2.0h · ctx peak 12k avg 6k", line)
        self.assertIn("2 PRs (1 opened)", line)
        block = ss.fmt_block(s)
        self.assertIn("| Stat | Value |", block)
        self.assertIn("| Subagents | 2 transcripts · 1 API turns", block)

    def test_prices(self):
        self.assertEqual(ss.price_for("claude-sonnet-4"), (3.0, 3.75, 0.3, 15.0))
        self.assertEqual(ss.price_for("claude-haiku-4"), (1.0, 1.25, 0.1, 5.0))
        self.assertEqual(ss.price_for("claude-opus-4"), ss.DEFAULT_PRICES)
        self.assertEqual(ss.price_for(None), ss.DEFAULT_PRICES)
        os.environ["SESSION_STATS_PRICES"] = "1,2,3,4"
        try:
            self.assertEqual(ss.prices(), (1.0, 2.0, 3.0, 4.0))
            self.assertEqual(ss.price_for("mythos"), (1.0, 2.0, 3.0, 4.0))
            os.environ["SESSION_STATS_PRICES"] = "bad"
            self.assertEqual(ss.prices(), ss.DEFAULT_PRICES)
        finally:
            del os.environ["SESSION_STATS_PRICES"]

    def test_k_and_stats_for(self):
        self.assertEqual([ss._k(n) for n in (5, 1500, 2_500_000)], ["5", "2k", "2.5M"])
        saved = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)  # the test may itself run inside a Claude session
        try:
            self.assertIsNone(ss.stats_for(""))
            self.assertIsNone(ss.stats_for("no-such-session"))
        finally:
            if saved is not None:
                os.environ["CLAUDE_CODE_SESSION_ID"] = saved


if __name__ == "__main__":
    unittest.main()
