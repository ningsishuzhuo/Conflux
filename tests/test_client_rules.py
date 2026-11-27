import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ".agents/skills/dispatch/SKILL.md"


class ClientRulesTests(unittest.TestCase):
    def test_entry_points_share_rules_and_skill(self):
        for name, limit in (("AGENTS.md", 28), ("CLAUDE.md", 12), ("GEMINI.md", 12)):
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
        self.assertLessEqual(len(content.splitlines()), 28)
        header = re.match(r"\A---\n(.*?)\n---\n", content, re.S)
        self.assertIsNotNone(header)
        self.assertRegex(header[1], r"(?m)^name: conflux-dispatch$")
        self.assertRegex(header[1], r'(?m)^description: "派发 Orca worker、[^"\n]+按需加载。"$')

    def test_autonomy_skill_entry_and_contract(self):
        path = ".agents/skills/autonomy/SKILL.md"
        self.assertIn(path, (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        content = (ROOT / path).read_text(encoding="utf-8")
        self.assertLessEqual(len(content.splitlines()), 28)
        self.assertRegex(content, r"(?m)^name: conflux-autonomy$")
        for name in ("review-checklists.md", "edge-cases.md"):
            relative = f"references/{name}"
            self.assertIn(relative, content)
            reference = (ROOT / path).parent / relative
            lines = reference.read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines)
            self.assertLessEqual(len(lines), 50)
        for term in ("读取成功后才继续", "停止相关动作并报告", "禁止 schedule", "阻塞轮询",
                     "dispatchId", "messageId", "worker_done", "gate-create"):
            self.assertIn(term, content)

        self.assertRegex(content, r"(?m)^1\. .*代码、文案、PPT、科研.*显式写明"
                                  r"“独立语义审查：安排（由谁）/ 不安排（原因）”")
        self.assertRegex(content, r"(?m)^3\. .*DSH 客观初筛.*冻结契约约定的独立语义审查"
                                  r".*审写分离.*DSH 初筛不可替代独立语义审查")
        self.assertRegex(content, r"(?m)^6\. .*收尾和发布 handoff 前核对"
                                  r"独立语义审查已按冻结契约完成或已记录不安排原因")

    def test_global_boundaries_have_one_source(self):
        content = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for term in ("不分冻结前后", "联网检索", "≥2", "跑业务命令", "首步一律派 DSH"):
            self.assertIn(term, content.splitlines()[0])
        for term in ("硬隔离", "辅助检测", "软约束", "-s read-only -a never",
                     "间接写", "免二次确认", "--authorize-paid"):
            self.assertIn(term, content)
            for client in ("CLAUDE.md", "GEMINI.md", SKILL):
                if client == SKILL and term == "--authorize-paid":
                    continue
                self.assertNotIn(term, (ROOT / client).read_text(encoding="utf-8"))

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

    def test_frozen_execution_boundaries(self):
        contracts = {
            "AGENTS.md": (
                "policy", "CLI `--help`", "scratch", "禁止跨工作区读取无关文件",
                "外部工具源码", "未覆盖报错即停机报告", "四项契约无悬空项",
                "用户明示拍板", "按你的下一步来做", "/conflux-autonomy",
                "零状态改动", "git fetch/pull/switch", "自查业务源码",
                "git push", "PR/Issue", "Refs", "Closes", "发版",
                "唯一默认值与执行归属", "执行前必二次确认", "参数或目标变化时重批",
            ),
            ".agents/skills/autonomy/SKILL.md": (
                "零状态改动", "git fetch/pull/switch", "仍先出草案",
                "外部工具未覆盖报错", "外部写未决项", "冻结契约内已拍板的收尾动作",
            ),
            SKILL: (
                '--from "$ORCA_SESSION"', "非空", "聊天会话省略", "--spec-file",
                "会话 scratch 或临时目录", "禁写入未冻结的业务仓库", "阶段、权限边界",
                "# <Title>", "ID: <id>", "Run: <run>", "Task: <task>",
                "Dispatch: <dispatch>", "Next: <next>",
            ),
            ".agents/skills/autonomy/references/edge-cases.md": (
                "原样报告命令与报错", "禁止跨工作区翻源码", "执行前必二次确认",
                "里程碑切新会话交接", "max_turn_context_tokens >= 80000",
                "同一问题连续 2 次无收敛", "发布并核验 6 行 handoff",
                "<id>-notes.md", "确认可读", "可复制的新会话续跑首句",
            ),
        }
        for name, terms in contracts.items():
            content = (ROOT / name).read_text(encoding="utf-8")
            for term in terms:
                with self.subTest(name=name, term=term):
                    self.assertIn(term, content)
        self.assertNotIn("/compact", content)
