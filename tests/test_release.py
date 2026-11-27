from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATHS = (
    "conflux.py", "conflux_handoff.py", "install.sh", "bin/conflux", "policy.json", "README.md", "LICENSE",
    "bin/conflux.cmd", ".github/workflows/test.yml",
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".agents", "examples",
    "docs/design.md", "docs/cli-contract.md", "docs/release-checklist.md",
    "docs/friction-log.md", "docs/adr",
)
PRIVATE_PATTERNS = {
    "personal path": r"/Users/",
    "private key": r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----",
    "API token": (
        r"\b(?:sk-(?:proj-|ant-api\d+-)?[\w-]{16,}|"
        r"AIza[\w-]{35}|gh[pousr]_[\w]{30,}|github_pat_[\w]{30,}|"
        r"(?:AKIA|ASIA)[A-Z0-9]{16}|xox[baprs]-[\w-]{10,})"
    ),
    "literal credential": r"""(?im)\b(?:api[_-]?key|access[_-]?token)["']?\s*[:=]\s*["'][A-Za-z0-9_+/=-]{12,}["']""",
    "private relay": r"(?i)\bccs-(?:openai|deepseek)\b",
}


class ReleaseTests(unittest.TestCase):
    def test_mit_license(self):
        path = ROOT / "LICENSE"
        self.assertTrue(path.is_file())
        license_text = path.read_text(encoding="utf-8")
        for clause in (
            "MIT License", "Copyright (c) 2026 Conflux Contributors",
            "Permission is hereby granted, free of charge",
            "THE SOFTWARE IS PROVIDED \"AS IS\"",
        ):
            self.assertIn(clause, license_text)

    def test_production_line_limits(self):
        for name, limit in (("conflux.py", 200), ("conflux_handoff.py", 70)):
            with self.subTest(name=name):
                lines = (ROOT / name).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(sum(
                    bool(line.strip()) and not line.lstrip().startswith("#")
                    for line in lines
                ), limit)

    def test_public_files_are_sanitized(self):
        for name in PUBLIC_PATHS:
            with self.subTest(path=name):
                root = ROOT / name
                self.assertTrue(root.exists(), name)
                paths = sorted(root.rglob("*")) if root.is_dir() else [root]
                for path in paths:
                    if not path.is_file():
                        continue
                    content = path.read_text(encoding="utf-8")
                    for category, pattern in PRIVATE_PATTERNS.items():
                        match = re.search(pattern, content)
                        if match:
                            line = content.count("\n", 0, match.start()) + 1
                            self.fail(f"{path.relative_to(ROOT)}:{line}: {category}")


    def test_research_directory_is_ignored(self):
        rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("docs/research/", rules)

    def test_public_docs_have_no_research_links(self):
        research_link = r"(?im)(?:\]\(\s*|^\s*\[[^\]]+\]:\s*|href=[\"']|<)[^\s)>]*research/"
        for name in PUBLIC_PATHS:
            root = ROOT / name
            paths = sorted(root.rglob("*.md")) if root.is_dir() else [root]
            for path in paths:
                if path.suffix == ".md":
                    with self.subTest(path=path.relative_to(ROOT)):
                        self.assertNotRegex(path.read_text(encoding="utf-8"), research_link)
