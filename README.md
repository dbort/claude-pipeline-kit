# Claude Task-Pipeline Kit

A drop-in multi-model task pipeline for Claude Code repos: Planner →
Implementer → Reviewer → human sign-off, with task files as the state
machine, per-task git branches, a rejection loop with a cap, human gates,
and a doc/comment hygiene sweep before anything merges.

Nothing in the kit assumes a language, framework, or container setup.
The repo supplies its own check commands through one editable section.

The kit lives in its own checkout and installs *into* other repos; the
kit directory itself never becomes part of a target repo.

## Install

From this kit's checkout, pointing at the repo that should receive the
pipeline:

```sh
./install.sh <task-prefix> <target-dir>
```

`<task-prefix>` is the target repo's task-id and branch prefix — `pb`
gives task ids like `pb-001` and branches named the same. Lowercase
letters/digits only. The script copies `templates/` into the target
root, rewrites the `{TASK_PREFIX}` placeholder everywhere, and creates
`tasks/{active,completed,abandoned}/`.

## Finishing setup in the target repo

The parts that can't be automated — they describe *your* repo — are
tracked by `PIPELINE-KIT-SETUP-TODO(step-id)` marker lines the installer
leaves in the copied files. Each marker says what to do; delete the
marker line once its step is done. Run `./pipeline-setup.sh` (installed
at the target root) anytime to list what remains:

- `verification-fast` / `verification-full` (`.claude/docs/pipeline.md`
  § Verification commands): the fast-check list (build/lint/test, cheap,
  no live infra) and the full-check list (slow or live-infra; may stay
  empty — deleting the marker records that as a decision).
- `project-conventions` (`CLAUDE.md`): the language/framework rules the
  Implementer and Reviewer enforce.
- `standing-obligations` (`CLAUDE.md`): acknowledge the section that
  accrues cross-cutting planning requirements over time.
- `sweep-pattern` (`.claude/skills/doc-hygiene/SKILL.md`): which file
  extensions the hygiene sweep covers.

The `new-task` and `dispatch-tasks` skills carry a setup gate: they run
`pipeline-setup.sh` first and stop while steps remain, so the pipeline
can't plan or dispatch tasks against placeholder configuration. Once
every marker is gone, a run of `pipeline-setup.sh` removes those gate
blocks from the skills, and tells you to review the diff, commit, and
delete the script itself. Its absence from a repo means setup finished.

Then start with `docs/agent-usage.md` (the human playbook) — first task
via the `new-task` skill.

## Pipeline architecture

The pipeline's rules live once, in `pipeline.md`; every other file links
to it. When you change pipeline behavior in a repo, change `pipeline.md`
first, then grep the other control files for one-line restatements.

## Requirements in the target repo

- Claude Code with subagents, skills, `/loop`, and the `Workflow` tool
  (`doc-hygiene` uses it; the rest of the kit works without it).
- git, with `main` as the default branch (or sed the kit if yours
  differs).
- Some lint/test entry point to list under Verification commands. E.g.,
  a single `./validate.sh` wrapping everything.
