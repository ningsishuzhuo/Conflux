from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "conflux.py"
NOTE = "# 交接\nID: case-1\nRun: r\nTask: t\nDispatch: d\nNext: n\n".encode()
OTHER = NOTE.replace(b"Next: n", b"Next: other")


HANDOFF_TEMPLATE = (
    b"# <Title>\nID: <id>\nRun: <run>\nTask: <task>\nDispatch: <dispatch>\nNext: <next>\n"
)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.final = self.directory / "case-1.md"

    def handoff(self, action, data=NOTE, file="-"):
        return subprocess.run(
            [sys.executable, str(CLI), "handoff", action, "--dir",
             str(self.directory), "--file", str(file)],
            input=data, capture_output=True,
        ).returncode

    def test_publish_from_file(self):
        source = self.directory / "input"
        source.write_bytes(NOTE)
        self.assertEqual(self.handoff("publish", file=source), 0)
        self.assertEqual(self.final.read_bytes(), NOTE)

    def test_duplicate_and_conflict(self):
        self.assertEqual(self.handoff("publish"), 0)
        self.assertEqual(self.handoff("publish"), 10)
        self.assertEqual(self.handoff("publish", OTHER), 11)
        self.assertEqual(self.final.read_bytes(), NOTE)
        self.assertEqual(list(self.directory.iterdir()), [self.final])

    def test_invalid_input(self):
        invalid = [NOTE.replace(b"# ", b"## "), NOTE.replace(b"\n", b"\r\n"),
                   NOTE.split(b"Next:")[0], NOTE[:-1], NOTE + b"\n",
                   NOTE.replace(b"Next: n", b"Next: "), b"\xff" + NOTE]
        invalid.extend(NOTE.replace(b"case-1", name)
                       for name in (b"../x", b".", b"..", b"a/b"))
        for data in invalid:
            with self.subTest(data=data):
                self.assertEqual(self.handoff("publish", data), 2)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_verify(self):
        self.assertEqual(self.handoff("verify"), 2)
        self.final.write_bytes(NOTE)
        self.assertEqual(self.handoff("verify"), 0)
        self.assertEqual(self.handoff("verify", OTHER), 11)
        self.assertEqual(self.final.read_bytes(), NOTE)

    def test_invalid_directory(self):
        self.directory /= "missing"
        self.assertEqual(self.handoff("publish"), 2)

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "target.md"
            target.write_bytes(NOTE)
            try:
                self.final.symlink_to(target)
            except OSError as error:
                if os.name != "nt" or error.winerror not in (5, 1314):
                    raise
                self.skipTest("Windows symlink creation requires additional privileges")
            self.assertEqual(self.handoff("verify"), 2)
            self.assertEqual(self.handoff("publish"), 2)
            self.assertEqual(target.read_bytes(), NOTE)

    def test_concurrent_publish(self):
        inputs = [NOTE, OTHER] * 8
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda data: self.handoff("publish", data), inputs))
        winner = self.final.read_bytes()
        self.assertIn(winner, inputs)
        self.assertEqual(results.count(0), 1)
        for data, result in zip(inputs, results):
            self.assertEqual(result, (0 if result == 0 else 10) if data == winner else 11)
        self.assertEqual(list(self.directory.iterdir()), [self.final])

    def test_invalid_input_diagnostics(self):
        cases = (
            (NOTE.replace(b"\n", b"\r\n"), b"CRLF"),
            (NOTE.split(b"Next:")[0], b"got 5"),
            (NOTE + b"extra\n", b"got 7"),
            (NOTE[:-1], b"without a final LF"),
            (NOTE.replace(b"Run: r", b"Route: r"), b"line 3: expected field prefix"),
            (NOTE.replace(b"Next: n", b"Next:  "), b"line 6: empty value"),
        )
        for action in ("publish", "verify"):
            for data, reason in cases:
                with self.subTest(action=action, reason=reason):
                    result = subprocess.run(
                        [sys.executable, str(CLI), "handoff", action, "--dir",
                         str(self.directory), "--file", "-"],
                        input=data, capture_output=True,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(reason, result.stderr)
                    self.assertIn(HANDOFF_TEMPLATE, result.stderr.replace(b"\r\n", b"\n"))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_help_describes_format(self):
        for action in ([], ["publish"], ["verify"]):
            with self.subTest(action=action):
                result = subprocess.run(
                    [sys.executable, str(CLI), "handoff", *action, "--help"],
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0)
                self.assertIn(b"ending in LF", result.stdout)
                self.assertIn(HANDOFF_TEMPLATE, result.stdout.replace(b"\r\n", b"\n"))
