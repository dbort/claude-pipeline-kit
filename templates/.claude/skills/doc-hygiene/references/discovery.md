# doc-hygiene: file discovery details

Background for `SKILL.md` § Step 1. Read this when a listing command
behaves unexpectedly or when changing what the sweep covers.

## Why each mode lists files the way it does

**`--diff` (uncommitted changes).** `git diff HEAD` covers staged and
unstaged changes together, so it doesn't matter whether the modifications
were `git add`ed yet, but it only lists files git already tracks: a new file
has no diff against HEAD until it's tracked. `git ls-files --others
--exclude-standard` fills that gap with every untracked, non-gitignored
file, which is exactly the set `git diff` misses.

A deleted file appears in the `git diff` half of the listing too, since it
has a diff against HEAD, but won't exist to read in Step 3. Drop any path
Step 3's agents can't read rather than erroring the whole sweep.

**`--diff=<ref>` (committed on this branch).** Triple-dot (`<ref>...HEAD`)
bounds the comparison at the merge-base, matching how the Reviewer already
compares a task branch to `main` (`.claude/docs/pipeline.md` § Phases). It
shows only what changed on the current branch, not unrelated changes
`<ref>` picked up in the meantime.

No `git ls-files --others` half is needed here: a task branch's work is
expected to already be fully committed by the time this mode runs
(post-review), so there's normally nothing untracked to add. If there is,
that usually means something wasn't committed, which is worth noticing
rather than silently sweeping in.

## Why the exclusions are unconditional

Both modes exclude these regardless of `$SCOPE`:

- **`tasks/**`** — pipeline data files with frontmatter the
  Planner/Implementer/Reviewer machinery parses. A prose pass here risks
  corrupting frontmatter or softening the intentionally instruction-dense
  `## Execution Plan` prose.
- **`.claude/**` and `CLAUDE.md`** — behavioral-contract files for agents,
  not human-facing docs. They rely on literal absolutes ("Never commit task
  work directly to main") that the style pass's "lazy extremes" rule would
  otherwise want to soften. This is why agent-contract docs live under
  `.claude/docs/` rather than `docs/` (see `CLAUDE.md`'s doc placement
  convention): `docs/` is human-facing and swept; `.claude/` never is.
