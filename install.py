#!/usr/bin/env python3
"""install: copy the pipeline template into an empty repository and commit it.

The root commit holds the unmodified template, so a project's customizations
stay one reviewable diff and later kit changes have a clean baseline to port
onto.
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent
TEMPLATE = KIT_ROOT / "template"
LICENSE = "LICENSE"
VERSION_STAMP = Path(".claude") / "pipeline-kit-version"


class InstallError(Exception):
    """The target cannot take the template; the message is for the user."""


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _git(cwd: Path, *args: str) -> str | None:
    """Stripped stdout of a git command, or None if it exits nonzero."""
    result = _run_git(cwd, *args)
    return result.stdout.strip() if result.returncode == 0 else None


def _git_or_raise(cwd: Path, *args: str) -> None:
    result = _run_git(cwd, *args)
    if result.returncode != 0:
        raise InstallError(f"git {args[0]} failed: {result.stderr.strip()}")


def _nearest_existing_dir(path: Path) -> Path:
    while not path.exists():
        path = path.parent
    return path


def check_target_is_empty(target: Path) -> None:
    """Raises `InstallError` unless `target` is missing, empty, or an unborn repo.

    An unborn repo has a `.git` and nothing else: no commits and no staged
    files. A missing or empty directory inside another repo's work tree is
    refused because the install would nest a repository there.
    """
    if target.exists() and not target.is_dir():
        raise InstallError(f"{target} exists and is not a directory")
    entries = sorted(p.name for p in target.iterdir()) if target.exists() else []
    extras = [name for name in entries if name != ".git"]
    if extras:
        raise InstallError(f"{target} is not empty: {', '.join(extras)}")
    if ".git" in entries:
        if _git(target, "rev-parse", "--verify", "--quiet", "HEAD") is not None:
            raise InstallError(f"{target} already has commits")
        if _git(target, "ls-files"):
            raise InstallError(f"{target} has staged files")
    elif _git(_nearest_existing_dir(target), "rev-parse", "--show-toplevel"):
        raise InstallError(f"{target} is inside another git repository")


def git_identity_name(target: Path) -> str:
    """The configured `user.name`; raises `InstallError` if name or email is unset.

    The installer's commit needs both, and the license takes the name.
    """
    start = _nearest_existing_dir(target)
    name = _git(start, "config", "user.name")
    email = _git(start, "config", "user.email")
    if not name or not email:
        raise InstallError(
            "git user.name and user.email must be set, for example with "
            "`git config --global user.name 'Your Name'`"
        )
    return name


def kit_version() -> str:
    """The kit's commit, suffixed `-dirty` if modified; `unknown` outside git."""
    sha = _git(KIT_ROOT, "rev-parse", "HEAD")
    if sha is None:
        return "unknown"
    return f"{sha}-dirty" if _git(KIT_ROOT, "status", "--porcelain") else sha


def render_license(template_text: str, holder: str, year: int) -> str:
    """`template_text` with its year and copyright holder placeholders filled in."""
    return template_text.replace("{{YEAR}}", str(year)).replace(
        "{{COPYRIGHT_HOLDER}}", holder
    )


def install(target: Path) -> str:
    """Copies the template into `target` as its root commit on `main`.

    Returns the stamped kit version. Raises `InstallError`, before changing
    anything, if `target` is not empty or git has no identity configured.
    """
    check_target_is_empty(target)
    holder = git_identity_name(target)
    version = kit_version()

    target.mkdir(parents=True, exist_ok=True)
    _git_or_raise(target, "init", "--quiet")
    # An unborn repo may already exist on another default branch, where
    # `git init -b` would keep that name; the pipeline requires `main`.
    _git_or_raise(target, "symbolic-ref", "HEAD", "refs/heads/main")

    shutil.copytree(
        TEMPLATE,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"),
    )
    license_path = target / LICENSE
    license_path.write_text(
        render_license(
            license_path.read_text(encoding="utf-8"),
            holder,
            datetime.date.today().year,
        ),
        encoding="utf-8",
    )
    (target / VERSION_STAMP).write_text(f"{version}\n", encoding="utf-8")

    _git_or_raise(target, "add", "--all")
    _git_or_raise(
        target, "commit", "--quiet", "-m", f"Install claude-pipeline-kit {version}"
    )
    return version


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target", type=Path, help="a missing or empty directory, or an unborn repo"
    )
    args = parser.parse_args(argv)
    target: Path = args.target.resolve()
    try:
        version = install(target)
    except InstallError as exc:
        print(f"install: {exc}", file=sys.stderr)
        return 1
    print(f"Installed claude-pipeline-kit {version} into {target}.")
    print("Next: start Claude Code in that directory and run /init-pipeline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
