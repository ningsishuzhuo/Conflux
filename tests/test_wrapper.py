import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_dispatch import fake_orca

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-01-01T12:00:00Z"


class WrapperTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cwd = Path(temporary.name)
        home = self.cwd / "test home"
        self.policy = home / ".config/conflux/policy.json"
        self.ledger = home / ".local/state/conflux/ledger.jsonl"
        for path in (self.policy, self.ledger):
            path.parent.mkdir(parents=True)
        self.env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
        for name in ("CONFLUX_POLICY", "CONFLUX_LEDGER", "CONFLUX_AGY_BRAIN_DIR"):
            self.env.pop(name, None)

        if os.name == "nt":
            self.entry = ROOT / "bin/conflux.cmd"
        else:
            shim_dir = self.cwd / "python-bin"
            shim_dir.mkdir()
            (shim_dir / "python3").symlink_to(sys.executable)
            self.env["PATH"] = os.pathsep.join([str(shim_dir), *os.get_exec_path(self.env)])
            self.entry = self.cwd / "conflux"
            (self.cwd / "relative-link").symlink_to(ROOT / "bin/conflux")
            self.entry.symlink_to("relative-link")
        self.policy.write_text((ROOT / "policy.json").read_text(encoding="utf-8"), encoding="utf-8")
        self.local_policy = self.cwd / "policy.json"
        self.local_policy.write_text(
            self.policy.read_text(encoding="utf-8").replace('"paid"', '"subscription"'),
            encoding="utf-8",
        )
        orca = fake_orca(self.cwd / "fake orca", "import json, sys\n"
                         "print(json.dumps(dict(dispatchId='receipt', args=sys.argv[1:])))\n")
        self.dispatch = ("dispatch", "--agent", "claude", "--profile", "default",
                         "--model", "example", "--cwd", ".", "--orca-bin", str(orca),
                         "--now", NOW)

    def run_cli(self, *args):
        return subprocess.run([str(self.entry), *map(str, args)], cwd=self.cwd,
                              env=self.env, capture_output=True, text=True)

    def test_dispatch_rejects_paid_route_using_home_policy(self):
        result = self.run_cli(*self.dispatch)
        self.assertEqual(result.returncode, 2)
        self.assertIn("paid route requires --authorize-paid", result.stderr)
        self.assertFalse(self.ledger.exists())
        self.assertFalse((self.cwd / "ledger.jsonl").exists())

    def test_dispatch_missing_home_policy_fails_closed(self):
        self.policy.unlink()
        result = self.run_cli(*self.dispatch)
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot load policy", result.stderr)
        self.assertIn(repr(str(self.policy)), result.stderr)

    def test_explicit_policy_and_ledger_override_environment(self):
        self.env.update(CONFLUX_POLICY=str(self.policy), CONFLUX_LEDGER=str(self.ledger))
        explicit_ledger = self.cwd / "explicit ledger.jsonl"
        for options in (
            ("--policy", self.local_policy, "--ledger", explicit_ledger),
            (f"--policy={self.local_policy}", f"--ledger={explicit_ledger}"),
        ):
            with self.subTest(options=options):
                result = self.run_cli(*self.dispatch, *options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(explicit_ledger.read_text(encoding="utf-8"))["billing"],
                                 "subscription")
                explicit_ledger.unlink()
        self.assertFalse(self.ledger.exists())

    def test_dispatch_preserves_native_arguments(self):
        self.env["CONFLUX_POLICY"] = str(self.local_policy)
        native = ["--spec", "run a task", "--policy", "--ledger=value", ""]
        result = self.run_cli(*self.dispatch, "--", *native)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["args"],
                         ["orchestration", "worker-start", "--agent", "claude",
                          "--model", "example", *native])
        self.assertEqual(json.loads(self.ledger.read_text(encoding="utf-8"))["dispatch_id"], "receipt")

    def test_usage_reads_home_ledger_and_honors_overrides(self):
        self.ledger.write_text(json.dumps(dict(dispatch_id="one", agent="codex", ts=NOW)) + "\n", encoding="utf-8")
        local_ledger = self.cwd / "ledger.jsonl"
        local_ledger.write_text(json.dumps(dict(dispatch_id="two", agent="claude", ts=NOW)) + "\n", encoding="utf-8")
        result = self.run_cli("usage", "--now", NOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["codex_calls"], 1)
        self.env["CONFLUX_LEDGER"] = str(local_ledger)
        result = self.run_cli("usage", "--now", NOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["other_calls"], 1)
        result = self.run_cli("usage", f"--ledger={self.ledger}", "--now", NOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["codex_calls"], 1)

    def test_usage_detects_agy_brain_and_honors_explicit_options(self):
        default = Path(self.env["HOME"]) / ".gemini/antigravity-cli/brain"
        override = self.cwd / "brain override"
        for brain, tokens in ((default, 12), (override, 34)):
            path = brain / "session/.system_generated/logs/transcript.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(dict(type="PLANNER_RESPONSE", created_at=NOW,
                                            input_tokens=tokens)) + "\n", encoding="utf-8")
        for run in (self.run_cli, self.run_windows_wrapper):
            self.env.pop("CONFLUX_AGY_BRAIN_DIR", None)
            result = run("usage", "--now", NOW)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["agy_coordinator"]["input_tokens"], 12)
            self.env["CONFLUX_AGY_BRAIN_DIR"] = str(override)
            for options, tokens in (((), 34), (("--agy-brain-dir", str(default)), 12),
                                    ((f"--agy-brain-dir={default}",), 12)):
                result = run("usage", "--now", NOW, *options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["agy_coordinator"]["input_tokens"], tokens)
            self.env["CONFLUX_AGY_BRAIN_DIR"] = str(self.cwd / "missing")
            result = run("usage", "--now", NOW)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("agy_coordinator", json.loads(result.stdout))

    def run_windows_wrapper(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "conflux.py"), "--windows-wrapper", *args],
                              cwd=self.cwd, env=self.env, capture_output=True, text=True)

    def test_handoff_preserves_relative_paths(self):
        (self.cwd / "handoff files").mkdir()
        data = "# Example\nID: sample\nRun: run\nTask: task\nDispatch: dispatch\nNext: verify\n"
        (self.cwd / "source file.md").write_bytes(data.encode("utf-8"))
        for action in ("publish", "verify"):
            result = self.run_cli("handoff", action, "--dir", "handoff files",
                                  "--file", "source file.md")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.cwd / "handoff files/sample.md").read_text(encoding="utf-8"), data)

    def test_help_is_passed_through(self):
        expected = subprocess.run([sys.executable, str(ROOT / "conflux.py"), "--help"],
                                  cwd=self.cwd, capture_output=True, text=True)
        result = self.run_cli("--help")
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (expected.returncode, expected.stdout, expected.stderr))
