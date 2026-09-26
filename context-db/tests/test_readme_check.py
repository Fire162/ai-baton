"""skills/repo-docs/readme-check.py — the house-style front-page checker."""
import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("readme_check", KIT / "skills" / "repo-docs" / "readme-check.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

BADGE = "[![CI](https://example.invalid/ci.svg)](https://example.invalid/ci)"
GOOD = "\n".join([
    "# tool", "", "**One line on what it is.**", "",
    BADGE, BADGE, BADGE, "",
    "It turns a thing into another thing for you.", "",
    "```sh", "pip install tool", "```", "",
    "## Usage", "", "Run it.", "",
    "## License", "", "MIT.", "",
])


def results(text: str, kind: str = "readme") -> dict:
    return {name: status for status, name, _ in rc.check(rc.parse(text), kind)}


class Readme(unittest.TestCase):
    def test_a_short_front_page_passes(self):
        r = results(GOOD)
        self.assertNotIn("FAIL", r.values(), r)
        self.assertEqual(r["section: install"], "ok")  # the first code block installs it

    def test_a_wall_of_text_fails_length_pitch_and_paragraphs(self):
        wall = " ".join(["word"] * 200)
        r = results(f"# tool\n\n{wall}\n\n{wall} {wall} {wall} {wall} {wall} {wall} {wall} {wall}\n")
        for rule in ("length", "pitch", "badges", "paragraphs", "first code block", "section: license"):
            self.assertEqual(r[rule], "FAIL", rule)

    def test_code_below_the_first_screen_fails(self):
        r = results(GOOD.replace("```sh", "\n" * 40 + "```sh", 1))
        self.assertEqual(r["first code block"], "FAIL")

    def test_code_block_contents_are_not_prose(self):
        stats = rc.parse(GOOD.replace("pip install tool", "\n".join(["x " * 300] * 5)))
        self.assertLess(stats["total_words"], 100)

    def test_a_fat_table_row_fails(self):
        r = results(GOOD + "\n| a | " + "b" * 450 + " |\n")
        self.assertEqual(r["table rows"], "FAIL")

    def test_list_lines_do_not_count_as_pitch(self):
        stats = rc.parse(GOOD.replace("It turns", "- " + "item " * 100 + "\n\nIt turns", 1))
        self.assertLess(stats["pitch_words"], 20)


class Contributing(unittest.TestCase):
    def test_short_version_in_the_intro_counts(self):
        r = results("# Contributing\n\n**The short version**\n\n- Open an issue.\n\n## Setup\n\nRun it.\n",
                    "contributing")
        self.assertEqual(r["section: short version"], "ok")
        self.assertNotIn("badges", r)  # a CONTRIBUTING has no badge rule

    def test_missing_short_version_fails(self):
        r = results("# Contributing\n\nRead the rules.\n\n## Setup\n\nRun it.\n", "contributing")
        self.assertEqual(r["section: short version"], "FAIL")

    def test_kind_follows_the_file_name(self):
        # the kit's own front pages are the live calibration: they must stay green
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rc.main([str(KIT / "CONTRIBUTING.md")]), 0)
            self.assertEqual(rc.main([str(KIT / "README.md")]), 0)


if __name__ == "__main__":
    unittest.main()
