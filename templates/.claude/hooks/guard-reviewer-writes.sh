#!/usr/bin/env sh
# PreToolUse guard for the Reviewer subagent.
#
# The Reviewer's contract is "your output is a verdict plus findings, not a
# patch" (`.claude/agents/reviewer.md`), but it needs Write/Edit to author
# `tasks/active/{TASK_PREFIX}-XXX-REVIEW.md`, update the task file's
# frontmatter, and append to the friction log. The `tools` field can't express
# "these paths only", so this hook does: it allows writes under `tasks/` and to
# the friction log, and blocks every other file the Reviewer tries to edit.
#
# Wired up by `hooks:` in `.claude/agents/reviewer.md`. Claude Code runs a
# project agent's frontmatter hooks only after the workspace trust dialog is
# accepted for this folder; until then the Reviewer still runs and this guard
# is silently skipped, so accept trust before relying on it.
#
# Input arrives as PreToolUse JSON on stdin. Exit 2 blocks the call and hands
# the stderr text back to the Reviewer as the reason.
set -eu

INPUT=$(cat)

if command -v jq >/dev/null 2>&1; then
  FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
else
  # Fallback for repos without jq. Paths containing escaped quotes would parse
  # wrong here, which is why jq is preferred when it's present.
  FILE=$(printf '%s' "$INPUT" \
    | sed -n 's/.*"\(file_path\|notebook_path\)"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\2/p' \
    | head -n 1)
fi

# No path to judge means no basis to block: let the permission system handle it.
[ -n "$FILE" ] || exit 0

# Tool input may carry an absolute path; compare against the repo-relative form.
REL=${FILE#"${CLAUDE_PROJECT_DIR:-}/"}
REL=${REL#./}

case $REL in
  tasks/*|.claude/docs/friction-log.md) exit 0 ;;
esac

cat >&2 <<MSG
Blocked: the Reviewer does not patch code. '$REL' is outside the paths this
role may write (tasks/**, .claude/docs/friction-log.md).

Record the problem as a blocking finding in
tasks/active/<task-id>-REVIEW.md with a file:line reference and let the
Implementer's next round fix it. A one-line fix you apply yourself and then
approve leaves no test and no trace.
MSG
exit 2
