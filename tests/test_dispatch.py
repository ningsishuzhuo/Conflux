import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "conflux.py"


class DispatchTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.policy = self.root / "policy.json"
        self.calls = self.root / "calls.json"
        self.stub = self.root / "orca"
        self.routes = [
            dict(agent=agent, profile="default", model="example",
                 billing=billing, keep_open_default=keep)
            for agent, billing, keep in [
                ("codex", "subscription", False),
                ("dsh", "low_cost", True),
                ("claude", "paid", False),
            ]
        ]
        self.write_policy()
        self.write_stub()

    def write_policy(self):
        self.policy.write_text(json.dumps({"routes": self.routes}))

    def write_stub(self, status=0):
        self.stub.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            f"pathlib.Path({str(self.calls)!r}).write_text("
            "json.dumps([os.getcwd(), sys.argv[1:]]))\n"
            "print('{\"dispatchId\":\"d1\",\"requestId\":\"r1\"}')\n"
            "print('orca stderr', file=sys.stderr)\n"
            f"sys.exit({status})\n"
        )
        self.stub.chmod(0o700)

    def dispatch(self, agent="codex", *, model="example", cwd=None, options=(), native=()):
        return subprocess.run(
            [sys.executable, str(CLI), "dispatch", "--policy", str(self.policy),
             "--agent", agent, "--profile", "default", "--model", model,
             "--cwd", str(cwd or self.root), "--orca-bin", str(self.stub),
             *options, "--", *native],
            capture_output=True, text=True,
        )

    def assert_called(self, agent, *native):
        cwd, argv = json.loads(self.calls.read_text())
        self.assertEqual(Path(cwd).resolve(), self.root.resolve())
        self.assertEqual(argv, [
            "orchestration", "worker-start", "--agent", agent, "--model",
            "example", *native,
        ])

    def assert_rejected(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("usage:", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_subscription_preserves_native_order_and_values(self):
        native = ("--spec", "two words", "--json", "--timeout-ms=500")
        result = self.dispatch(native=native)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_called("codex", *native)

    def test_default_model_follows_client(self):
        self.assert_rejected(self.dispatch(model="default"))
        self.routes.append(dict(self.routes[0], model="default"))
        self.write_policy()
        self.assert_rejected(self.dispatch(model="default", native=("--model=example",)))
        result = self.dispatch(model="default", native=("--json",))
        self.assertEqual(result.returncode, 0, result.stderr)
        _, argv = json.loads(self.calls.read_text())
        self.assertEqual(argv, ["orchestration", "worker-start", "--agent", "codex", "--json"])

    def test_low_cost_adds_keep_open_only_when_absent(self):
        for native in [("--json",), ("--keep-open", "--json")]:
            with self.subTest(native=native):
                result = self.dispatch("dsh", native=native)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = native if "--keep-open" in native else (*native, "--keep-open")
                self.assert_called("dsh", *expected)

    def test_paid_requires_nonblank_authorization(self):
        self.assert_rejected(self.dispatch("claude"))
        self.assert_rejected(self.dispatch("claude", options=("--authorize-paid", " ")))
        result = self.dispatch("claude", options=("--authorize-paid", "review"), native=("--json",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_called("claude", "--json")

    def test_invalid_route_directory_and_overrides_are_rejected(self):
        self.assert_rejected(self.dispatch("unknown"))
        self.assert_rejected(self.dispatch(cwd=self.root / "missing"))
        for flag in ("agent", "profile", "model", "cwd"):
            for native in [(f"--{flag}", "other"), (f"--{flag}=other",)]:
                with self.subTest(native=native):
                    self.assert_rejected(self.dispatch(native=native))

    def test_invalid_policy_is_rejected(self):
        good = self.routes[0]
        for invalid in [good, dict(good, extra=True), dict(good, billing="free"),
                        dict(good, keep_open_default=1), dict(good, model=5)]:
            with self.subTest(route=invalid):
                self.routes.append(invalid)
                self.write_policy()
                self.assert_rejected(self.dispatch())
                self.routes.pop()

    def test_orca_failure_preserves_exit_code_and_output(self):
        self.write_stub(7)
        result = self.dispatch()
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stdout, '{"dispatchId":"d1","requestId":"r1"}\n')
        self.assertEqual(result.stderr, "orca stderr\n")

    def test_production_line_limit(self):
        lines = CLI.read_text().splitlines()
        self.assertLessEqual(sum(bool(line.strip()) and not line.lstrip().startswith("#")
                                 for line in lines), 200)
