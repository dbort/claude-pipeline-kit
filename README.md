# claude-pipeline-kit

A plan, implement, review pipeline for [Claude Code](https://claude.com/claude-code),
packaged to start new coding projects in any language or mix of languages.

Each unit of work is a task file. You approve its plan, an agent implements
it on a branch, a separate reviewer agent that did not write the code must
approve it, and you sign off before a verified merge into `main`:

| Command | What happens |
|---|---|
| `/new-task` | Claude interviews you and commits a plan to `tasks/active/task-XXX-<slug>.md`. |
| `/work task-XXX` | Your approval of the plan. Claude implements on branch `task-XXX` and loops with the reviewer until it approves. |
| `/ship task-XXX` | Your sign-off. Claude sweeps comments and docs, then merges into `main` only if the merged result passes the checks. |

## Quick start

You need `git`, `python3` (3.10 or later), and Claude Code, and git needs
`user.name` and `user.email` set.

```sh
python3 install.py ~/my-project
cd ~/my-project
claude
```

Then run `/init-pipeline`. It asks what the project is, what it is built
with, and what the merge gate must cover, plans `task-001`, and deletes
itself. Run `/work task-001` to scaffold the project and create its real
merge gate.

The target must be a missing or empty directory, or a `git init` with no
commits. The installer refuses anything else.

## What a project receives

- `CLAUDE.md`: the project's agent instructions, including its writing rules
  and the requirements every task plan must meet.
- `.claude/skills/`: `new-task`, `work`, `ship`, `doc-hygiene`, `grill-me`,
  and the one-shot `init-pipeline`.
- `.claude/agents/`: `reviewer` and `hygiene`.
- `.claude/docs/pipeline.md`: the pipeline's rules, plus friction and bug
  logs and GitHub Actions hardening rules for projects that add workflows.
- `tools/check`: the merge gate, which starts as a failing stub for
  `task-001` to replace. Its contract is in `pipeline.md` § Checks.
- `tools/task_status.py`: the backlog in dependency order and the next free
  task id.
- `LICENSE`: MIT, under the `user.name` from your git config. Replace it if
  your project needs another license.

Python is required only for `tools/task_status.py`, which uses the standard
library alone. The project's own code can be in anything.

## Picking up kit changes

A project owns its copy, and nothing updates it automatically. The kit
commit it came from is in `.claude/pipeline-kit-version`, so you can see what
changed since and port what you want:

```sh
git -C path/to/claude-pipeline-kit diff "$(cat .claude/pipeline-kit-version)" HEAD -- template/
```

## Developing the kit

`template/` is the payload, and it stays free of any language, project, or
person. The kit does not run its own pipeline: its install refuses non-empty
targets, and a second copy of the payload would have to be kept in step.

```sh
python3 -m unittest discover -s tests
```

## Credits

- The `grill-me` skill comes from
  <https://www.aihero.dev/my-grill-me-skill-has-gone-viral>.
- The writing rules are adapted in part from
  [stop-slop](https://github.com/hardikpandya/stop-slop) by Hardik Pandya
  under the MIT License. See
  `template/.claude/skills/doc-hygiene/NOTICE-stop-slop-LICENSE.md`.

## License

MIT. See [LICENSE](LICENSE).
