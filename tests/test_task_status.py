"""Coverage of the template's `tools/task_status.py`: helpers, then a throwaway repo."""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT_ROOT / "template" / "tools"))

from task_status import (
    Frontmatter,
    TaskParseError,
    build_backlog,
    compute_next_id,
    derive_status,
    last_review_round,
    layered_topological_order,
    main,
    parse_frontmatter,
)


def _task_text(
    task_id: str, blocked_by: list[str] | None = None, review_log: str = ""
) -> str:
    blocked = f"blocked_by: [{', '.join(blocked_by)}]\n" if blocked_by else ""
    return (
        f'---\nid: {task_id}\ntitle: "Title {task_id}"\n{blocked}---\n\n'
        f"# {task_id}: Title\n\n## Review log\n{review_log}"
    )


class ParseFrontmatterTest(unittest.TestCase):
    def test_reads_id_title_and_blockers(self) -> None:
        self.assertEqual(
            parse_frontmatter(_task_text("task-003", ["task-001", "task-002"])),
            Frontmatter("task-003", "Title task-003", ("task-001", "task-002")),
        )

    def test_ignores_other_keys_and_their_nested_lines(self) -> None:
        text = '---\nid: task-001\nother: 1\nnested:\n  child: 2\ntitle: "T"\n---\n'
        self.assertEqual(parse_frontmatter(text), Frontmatter("task-001", "T"))

    def test_skips_comments_and_blank_lines(self) -> None:
        text = (
            '---\nid: task-001\ntitle: "T"\n\n'
            "# blocked_by: [task-002]   # hard blockers only\n---\n"
        )
        self.assertEqual(parse_frontmatter(text), Frontmatter("task-001", "T"))

    def test_scalar_forms(self) -> None:
        for raw, expected in [
            ("plain words", "plain words"),
            ("plain # trailing comment", "plain"),
            ('"with: colon # and hash"', "with: colon # and hash"),
            ('"escaped \\" quote"  # comment', 'escaped " quote'),
            ("'it''s quoted'", "it's quoted"),
        ]:
            with self.subTest(raw=raw):
                text = f"---\nid: task-001\ntitle: {raw}\n---\n"
                self.assertEqual(parse_frontmatter(text).title, expected)

    def test_blocker_list_forms(self) -> None:
        for raw, expected in [
            ("[]", ()),
            ("[task-001]  # comment", ("task-001",)),
            ('["task-001", task-002]', ("task-001", "task-002")),
        ]:
            with self.subTest(raw=raw):
                text = f"---\nid: task-003\ntitle: T\nblocked_by: {raw}\n---\n"
                self.assertEqual(parse_frontmatter(text).blocked_by, expected)

    def test_rejects_malformed(self) -> None:
        for text in [
            "no frontmatter\n",
            "---\n- a list\n---\n",
            '---\ntitle: "T"\n---\n',
            "---\nid: task-1\n---\n",
            "---\nid: task-1\ntitle:\n---\n",
            '---\nid: task-1\ntitle: "unterminated\n---\n',
            "---\nid: task-1\ntitle: T\nblocked_by: task-2\n---\n",
            # A block list must not silently read as "no blockers".
            "---\nid: task-1\ntitle: T\nblocked_by:\n  - task-2\n---\n",
        ]:
            with self.subTest(text=text), self.assertRaises(TaskParseError):
                parse_frontmatter(text)


class PureHelpersTest(unittest.TestCase):
    def test_last_review_round_takes_the_last_heading(self) -> None:
        log = "### Round 1: REJECTED\n- F1\n### Round 2: APPROVED\n"
        self.assertEqual(
            last_review_round(_task_text("task-001", review_log=log)), (2, "APPROVED")
        )
        self.assertIsNone(last_review_round(_task_text("task-001")))

    def test_derive_status(self) -> None:
        for branch_exists, log, expected in [
            (False, "", "planned"),
            (True, "", "in progress"),
            (True, "### Round 1: REJECTED\n", "in progress, round 1 rejected"),
            (True, "### Round 1: REJECTED\n### Round 2: APPROVED\n", "awaiting /ship"),
        ]:
            with self.subTest(expected=expected):
                text = _task_text("task-001", review_log=log)
                self.assertEqual(derive_status(branch_exists, text), expected)

    def test_compute_next_id(self) -> None:
        cases: list[tuple[list[str], str]] = [
            ([], "task-001"),
            (["task-009", "task-010", "junk"], "task-011"),
            (["task-999"], "task-1000"),
        ]
        for ids, expected in cases:
            with self.subTest(ids=ids):
                self.assertEqual(compute_next_id(ids), expected)

    def test_layered_topological_order(self) -> None:
        graph: dict[str, list[str]] = {
            "task-3": ["task-1", "task-2"],
            "task-2": ["task-1", "task-0"],
            "task-1": [],
            "task-8": ["task-9"],
            "task-9": ["task-8"],
        }
        self.assertEqual(
            layered_topological_order(graph),
            ([["task-1"], ["task-2"], ["task-3"]], ["task-8", "task-9"]),
        )


class RepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "T")
        self._write("tasks/completed/task-001-done.md", _task_text("task-001"))
        self._write(
            "tasks/active/task-002-approved.md", _task_text("task-002", ["task-001"])
        )
        self._write(
            "tasks/active/task-003-planned.md", _task_text("task-003", ["task-002"])
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "init")
        self._git("checkout", "-q", "-b", "task-002")
        self._write(
            "tasks/active/task-002-approved.md",
            _task_text("task-002", ["task-001"], "### Round 1: APPROVED\n"),
        )
        self._write("tasks/active/task-005-elsewhere.md", _task_text("task-005"))
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "work")
        self._git("checkout", "-q", "main")

    def _git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def _write(self, rel: str, text: str) -> None:
        (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / rel).write_text(text, encoding="utf-8")

    def _main_output(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = main(list(argv), repo_root=self.repo)
        return status, out.getvalue()

    def test_build_backlog_reads_status_from_the_branch(self) -> None:
        entries, errors = build_backlog(self.repo)
        self.assertEqual(errors, [])
        self.assertEqual(
            [(e.id, e.status, e.unmet_blockers) for e in entries],
            [
                ("task-002", "awaiting /ship", ()),
                ("task-003", "planned", ("task-002",)),
            ],
        )

    def test_build_backlog_reports_unreadable_files(self) -> None:
        self._write("tasks/active/task-004-broken.md", "no frontmatter\n")
        entries, errors = build_backlog(self.repo)
        self.assertEqual(len(entries), 2)
        self.assertEqual(
            errors,
            ["tasks/active/task-004-broken.md: no leading --- frontmatter block"],
        )

    def test_next_id_counts_other_branches(self) -> None:
        self.assertEqual(self._main_output("--next-id"), (0, "task-006\n"))

    def test_main_renders_backlog(self) -> None:
        status, out = self._main_output()
        self.assertEqual(status, 0)
        self.assertTrue(out.startswith("Next id: task-006\n"))
        self.assertIn("- task-003 [planned; blocked by task-002]: Title task-003", out)


if __name__ == "__main__":
    unittest.main()
