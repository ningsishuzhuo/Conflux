import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ".agents/skills/dispatch/SKILL.md"


class ClientRulesTests(unittest.TestCase):
    def test_entry_points_share_rules_and_skill(self):
        for name, limit in (("AGENTS.md", 30), ("CLAUDE.md", 12), ("GEMINI.md", 12)):
            with self.subTest(name=name):
                path = ROOT / name
                self.assertTrue(path.is_file(), name)
                content = path.read_text(encoding="utf-8")
                self.assertLessEqual(len(content.splitlines()), limit)
                self.assertIn(SKILL, content)
                if name != "AGENTS.md":
                    self.assertIn("AGENTS.md", content)
                else:
                    self.assertIn("orchestration", content)

    def test_dispatch_skill_frontmatter(self):
        path = ROOT / SKILL
        self.assertTrue(path.is_file(), SKILL)
        content = path.read_text(encoding="utf-8")
        self.assertLessEqual(len(content.splitlines()), 60)
        header = re.match(r"\A---\n(.*?)\n---\n", content, re.S)
        self.assertIsNotNone(header)
        self.assertRegex(header[1], r"(?m)^name: conflux-dispatch$")
        self.assertRegex(header[1], r'(?m)^description: "Use when [^"\n]+"$')

    def test_autonomy_skill_entry_and_contract(self):
        path = ".agents/skills/autonomy/SKILL.md"
        self.assertIn(path, (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        content = (ROOT / path).read_text(encoding="utf-8")
        self.assertLessEqual(len(content.splitlines()), 40)
        self.assertRegex(content, r"(?m)^name: conflux-autonomy$")
        for term in ("worktree", "验收命令", "篡改", "git push", "付费授权",
                     "DSH", "Codex", "orchestration", "gate", "handoff publish/verify"):
            self.assertIn(term, content)

    def test_gemini_keeps_orca_hook_and_appends_deny_hook(self):
        path = ROOT / "examples/gemini-before-tool.json"
        self.assertTrue(path.is_file(), path.name)
        entries = json.loads(path.read_text(encoding="utf-8"))["hooks"]["BeforeTool"]
        self.assertIsInstance(entries, list)
        orca = [i for i, entry in enumerate(entries)
                if any("gemini-hook.sh" in hook["command"] for hook in entry["hooks"])]
        deny = [i for i, entry in enumerate(entries)
                if "write_file" in entry["matcher"] and any(
                    '{"decision":"deny","reason":"read-only"}' in hook["command"]
                    for hook in entry["hooks"])]
        self.assertTrue(orca and deny and orca[0] < deny[0])
