"""Coverage of `install.py`, installing into real throwaway directories."""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT_ROOT))

import install


def _run(cwd: Path, *args: str) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()


class InstallTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.gitconfig = self.root / "gitconfig"
        self.gitconfig.write_text(
            "[user]\n\tname = Test Holder\n\temail = holder@example.com\n"
            "[init]\n\tdefaultBranch = trunk\n",
            encoding="utf-8",
        )
        patch = mock.patch.dict(
            os.environ,
            {"GIT_CONFIG_GLOBAL": str(self.gitconfig), "GIT_CONFIG_NOSYSTEM": "1"},
        )
        patch.start()
        self.addCleanup(patch.stop)


class SuccessfulInstallTest(InstallTestCase):
    def assert_installed(self, target: Path) -> None:
        self.assertEqual(_run(target, "git", "branch", "--show-current"), "main")
        self.assertEqual(_run(target, "git", "rev-list", "--count", "HEAD"), "1")
        self.assertEqual(_run(target, "git", "status", "--porcelain"), "")

    def test_creates_a_missing_directory(self) -> None:
        target = self.root / "a" / "new"
        install.install(target)
        self.assert_installed(target)

    def test_accepts_an_empty_directory(self) -> None:
        target = self.root / "empty"
        target.mkdir()
        install.install(target)
        self.assert_installed(target)

    def test_accepts_an_unborn_repo_on_another_branch(self) -> None:
        target = self.root / "unborn"
        target.mkdir()
        _run(target, "git", "init", "-q")
        install.install(target)
        self.assert_installed(target)

    def test_license_takes_the_git_identity_and_template_stays_neutral(self) -> None:
        target = self.root / "project"
        install.install(target)
        year = datetime.date.today().year
        license_text = (target / "LICENSE").read_text(encoding="utf-8")
        self.assertIn(f"Copyright (c) {year} Test Holder\n", license_text)
        self.assertNotIn("{{", license_text)
        self.assertIn(
            "{{COPYRIGHT_HOLDER}}",
            (install.TEMPLATE / "LICENSE").read_text(encoding="utf-8"),
        )

    def test_stamp_and_commit_name_the_kit_version(self) -> None:
        target = self.root / "project"
        version = install.install(target)
        self.assertEqual(
            (target / install.VERSION_STAMP).read_text(encoding="utf-8"),
            f"{version}\n",
        )
        self.assertIn(version, _run(target, "git", "log", "-1", "--format=%s"))

    def test_check_stub_is_executable_and_fails_naming_task_001(self) -> None:
        target = self.root / "project"
        install.install(target)
        result = subprocess.run(
            [target / "tools" / "check"], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("task-001", result.stderr)

    def test_installed_status_tool_runs_without_third_party_packages(self) -> None:
        target = self.root / "project"
        install.install(target)
        out = _run(target, sys.executable, "-I", "tools/task_status.py", "--next-id")
        self.assertEqual(out, "task-001")

    def test_empty_task_directories_survive_the_commit(self) -> None:
        target = self.root / "project"
        install.install(target)
        tracked = _run(target, "git", "ls-files", "tasks").splitlines()
        self.assertEqual(
            tracked,
            [
                "tasks/abandoned/.gitkeep",
                "tasks/active/.gitkeep",
                "tasks/completed/.gitkeep",
            ],
        )

    def test_main_reports_the_next_step(self) -> None:
        target = self.root / "project"
        with mock.patch("sys.stdout") as stdout:
            self.assertEqual(install.main([str(target)]), 0)
        written = "".join(call.args[0] for call in stdout.write.call_args_list)
        self.assertIn("/init-pipeline", written)


class RefusalTest(InstallTestCase):
    def assert_refused(self, target: Path, message: str) -> None:
        with self.assertRaisesRegex(install.InstallError, message):
            install.install(target)

    def test_refuses_a_directory_with_files(self) -> None:
        target = self.root / "full"
        target.mkdir()
        (target / "README.md").write_text("hello\n", encoding="utf-8")
        self.assert_refused(target, "not empty: README.md")
        self.assertFalse((target / "CLAUDE.md").exists())

    def test_refuses_a_file_target(self) -> None:
        target = self.root / "file"
        target.write_text("", encoding="utf-8")
        self.assert_refused(target, "not a directory")

    def test_refuses_a_repo_with_commits(self) -> None:
        target = self.root / "used"
        target.mkdir()
        _run(target, "git", "init", "-q")
        _run(target, "git", "commit", "-q", "--allow-empty", "-m", "first")
        self.assert_refused(target, "already has commits")

    def test_refuses_a_repo_with_staged_files(self) -> None:
        target = self.root / "staged"
        target.mkdir()
        _run(target, "git", "init", "-q")
        (target / "file").write_text("x\n", encoding="utf-8")
        _run(target, "git", "add", "file")
        (target / "file").unlink()
        self.assert_refused(target, "staged files")

    def test_refuses_to_nest_inside_another_repo(self) -> None:
        outer = self.root / "outer"
        outer.mkdir()
        _run(outer, "git", "init", "-q")
        self.assert_refused(outer / "inner" / "new", "inside another git repository")
        self.assertFalse((outer / "inner").exists())

    def test_refuses_without_a_git_identity_and_creates_nothing(self) -> None:
        self.gitconfig.write_text("", encoding="utf-8")
        target = self.root / "project"
        self.assert_refused(target, "user.name and user.email")
        self.assertFalse(target.exists())


class KitVersionTest(unittest.TestCase):
    def test_unknown_outside_git(self) -> None:
        with mock.patch.object(install, "_git", return_value=None):
            self.assertEqual(install.kit_version(), "unknown")

    def test_dirty_suffix(self) -> None:
        with mock.patch.object(install, "_git", side_effect=["abc", " M file"]):
            self.assertEqual(install.kit_version(), "abc-dirty")

    def test_clean(self) -> None:
        with mock.patch.object(install, "_git", side_effect=["abc", ""]):
            self.assertEqual(install.kit_version(), "abc")


if __name__ == "__main__":
    unittest.main()
