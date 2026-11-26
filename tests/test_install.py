import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(sys.platform == "win32", "POSIX installer")
class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        shim = Path(self.temp.name) / "bin"
        shim.mkdir()
        (shim / "python3").symlink_to(sys.executable)
        self.env = dict(os.environ, HOME=str(self.home),
                        PATH=f"{shim}{os.pathsep}{os.environ.get('PATH', '')}")

    def run_install(self, *args):
        return subprocess.run([str(ROOT / "install.sh"), "--skip-orca-check", *args],
                              env=self.env, text=True, capture_output=True)

    def test_install_and_repeat_preserves_policy(self):
        self.assertEqual(self.run_install().returncode, 0)
        policy = self.home / ".config/conflux/policy.json"
        self.assertNotIn('"example"', policy.read_text())
        policy.write_text('custom policy')
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual(policy.read_text(), 'custom policy')
        self.assertEqual((self.home / '.local/bin/conflux').resolve(), ROOT / 'bin/conflux')
        self.assertEqual((self.home / '.agents/skills/conflux-dispatch').resolve(), ROOT / '.agents/skills/dispatch')

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.run_install('--dry-run').returncode, 0)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_conflicts_are_preserved(self):
        for relative in ('.local/bin/conflux', '.agents/skills/conflux-dispatch'):
            for kind in ('file', 'link'):
                with self.subTest(relative=relative, kind=kind), tempfile.TemporaryDirectory() as tmp:
                    self.env['HOME'] = tmp
                    path = Path(tmp) / relative
                    path.parent.mkdir(parents=True)
                    if kind == 'file':
                        path.write_text('keep')
                    else:
                        path.symlink_to('/nonexistent/other')
                    self.assertNotEqual(self.run_install().returncode, 0)
                    self.assertTrue(path.is_symlink() if kind == 'link' else path.read_text() == 'keep')
                    self.assertFalse((Path(tmp) / '.config').exists())
