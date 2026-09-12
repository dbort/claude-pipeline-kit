---
name: doc-hygiene
description: Sweep code comments and markdown docs for content rot and AI-writing-style tells, then verify no technical fact was lost. Use before committing prose or comment changes, and on a task branch after review approves it.
argument-hint: "[--diff[=<ref>]] [path]"
allowed-tools: Bash(git ls-files *), Bash(git diff *), Bash(git log *)
---

# Skill: Doc & Comment Hygiene

## Purpose
Sweep the repo's code comments and markdown docs for two distinct problems and fix both:
1. **Content rot** — stale references, comments that just restate the code next to them, LLM throat-clearing/marketing fluff.
2. **AI-writing-style tells** — filler adverbs, em-dashes, passive voice, formulaic contrast/negative-listing/rhetorical-setup structures.

Every target file gets both passes, in that order (content first, since fixing style around content that's about to be deleted is wasted work), followed by a verification pass that checks no genuine technical fact was lost along the way, and a final sanity check running the repo's fast checks. It never commits — it ends with a summary; committing is a separate, explicit ask.

## Bundled files
- `scripts/hygiene-workflow.js` — the Workflow pipeline, and the authoritative rule text for all three passes. `CLAUDE.md` § Writing style by destination carries a distilled subset so agents generate cleaner text up front; keep the two in sync when editing either.
- `references/discovery.md` — why each Step 1 listing command is shaped the way it is, and why the exclusions are unconditional. Read it when a listing behaves unexpectedly or when changing sweep coverage.
- `NOTICE-stop-slop-LICENSE.md` — license and attribution for the style rules, adapted from the **stop-slop** skill (MIT License, Copyright (c) 2025 Hardik Pandya, <https://github.com/hardikpandya/stop-slop>).

---

## Invocation
`/doc-hygiene [--diff[=<ref>]] [path]`

- No argument: whole repo, every tracked file swept in full.
- `[path]`: a file or directory to scope the sweep to (e.g. `/doc-hygiene src/telemetry` or `/doc-hygiene docs/`), full files within that scope.
- `--diff`: scope to files with *uncommitted* changes (`git diff HEAD`) instead of every tracked file, AND constrain edits within each file to the changed lines (plus any pre-existing comment the diff made stale) rather than sweeping the whole file. Use this after making code changes, before committing, so the hygiene pass reviews what actually changed instead of re-litigating unrelated, already-settled content elsewhere in the same file.
- `--diff=<ref>`: same file-discovery/edit-scoping behavior as `--diff`, but scoped to everything **committed** on the current branch since it diverged from `<ref>` (`git diff <ref>...HEAD`), not uncommitted changes. Use this on a task branch whose work is already committed — e.g. right after a Reviewer approves a `{TASK_PREFIX}-XXX` branch, before it merges to `main`: `/doc-hygiene --diff=main`.

Combine either diff form with `[path]` to further narrow which changed files count (e.g. `/doc-hygiene --diff=main src/telemetry`).

---

## Execution Protocol

### Step 1: Discover target files

The sweep pattern selects the comment-bearing source and doc files this
repo cares about. It is a per-repo customization point:

```sh
# PIPELINE-KIT-SETUP-TODO(sweep-pattern): extend the pattern below with this repo's languages/config formats (e.g. '(\.md|\.sh|\.py|\.ts|\.tsx)$|(^|/)Dockerfile$'), then delete this marker line.
SWEEP_PATTERN='(\.md|\.sh)$'
```

Run the command matching the invocation form, substituting `$SCOPE` with the
invocation's path argument or `.` if none was given, and setting
`SWEEP_PATTERN` from the definition above in the same Bash call.

Full-tree mode (default):
```sh
git ls-files -- "$SCOPE" \
  | grep -E "$SWEEP_PATTERN" \
  | grep -vE '^tasks/|^\.claude/' \
  | grep -vx 'CLAUDE.md'
```

`--diff` mode (uncommitted changes):
```sh
{ git diff HEAD --name-only -- "$SCOPE"; git ls-files --others --exclude-standard -- "$SCOPE"; } | sort -u \
  | grep -E "$SWEEP_PATTERN" \
  | grep -vE '^tasks/|^\.claude/' \
  | grep -vx 'CLAUDE.md'
```

`--diff=<ref>` mode (everything committed on this branch since it diverged from `<ref>`):
```sh
git diff "<ref>"...HEAD --name-only -- "$SCOPE" \
  | grep -E "$SWEEP_PATTERN" \
  | grep -vE '^tasks/|^\.claude/' \
  | grep -vx 'CLAUDE.md'
```

Both modes exclude `tasks/**`, `.claude/**`, and `CLAUDE.md` regardless of
`$SCOPE`: they are machine-parsed pipeline data and agent-contract files, not
human-facing prose. `references/discovery.md` gives the reasoning for that
and for each listing command's shape.

If the resulting list is empty, report that and stop.

### Step 2: Group the files
Split the sorted file list into groups of roughly 6-9 files each. Prefer at least 2 groups when there are more than ~9 files total, to get real parallelism; don't fragment a small scope (e.g. a 3-file scope is one group, not three).

### Step 3: Run the pipeline
Read `${CLAUDE_SKILL_DIR}/scripts/hygiene-workflow.js`. It is a template: replace `GROUPS_PLACEHOLDER` with a literal JS array of your Step 2 groups (an array of arrays of file paths, e.g. `[["a.py", "b.py"], ["c.md"]]`), and `DIFF_BASE_PLACEHOLDER` with one of `null` (full-tree mode, no `--diff` at all), `"HEAD"` (plain `--diff`, uncommitted changes), or the literal ref string (e.g. `"main"`) if `--diff=<ref>` was passed.

Call the `Workflow` tool with the substituted text via the `script` parameter; don't pass `args` at all, since the groups and base are now embedded as literals.

The `Workflow` tool is unavailable inside a subagent, so run this skill from the main conversation rather than forking it.

### Step 4: Read the verify reports
Read every group's `verifyReport`. If any file is flagged, look at it yourself (`git diff -- <file>`) and decide: revert the specific hunk that lost real content, or accept it if the flag turns out to be a false positive. Don't skip this — a flagged verify report is exactly the case this pipeline stage exists to catch.

### Step 5: Final sanity check
Run the fast checks (`.claude/docs/pipeline.md` § Verification commands), in order, stopping at the first failure.

If the repo has cheap config-validation commands relevant to files this sweep touched (e.g. a compose/manifest `config --quiet` style check) that the fast tier doesn't already cover, run those too — pure validation only, nothing that starts services. An unavailable validator means the check is skipped and noted, not a failure.

**If any check fails: stop and report to the human. Do not auto-fix, do not run formatters or lint auto-fixers to paper over it.** A comment-only pass shouldn't be able to break the build or formatting; if it did, a subagent touched more than a comment, and that deserves a look before anything proceeds.

### Step 6: Summarize
Report what changed, grouped by file, at whatever level of detail the user asked for. **Do not commit.** End here — committing is a separate, explicit request the user makes afterward.
