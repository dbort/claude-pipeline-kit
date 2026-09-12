#!/usr/bin/env sh
# PreToolUse guard on Bash: keeps task work off `main`.
#
# "Never commit task work directly to main" is stated in CLAUDE.md,
# `.claude/docs/pipeline.md` § Git branching, and both the Implementer and
# Reviewer agent files, and until this hook existed it was enforced in none of
# them. Work reaches `main` only through `approve-task` merging a task branch.
#
# Two commits on `main` are legitimate and stay allowed:
#   - the merge commit `approve-task` Step 4 makes after `git merge
#     --no-commit` and a passing run of both verification tiers. Recognized by
#     MERGE_HEAD being present.
#   - the bookkeeping commit `dispatch-tasks` makes for the planning
#     auto-approval flip, before any task branch exists. Recognized by every
#     staged path living under `tasks/`.
#
# Anything else committed on `main` is blocked. Exit 2 hands the stderr text
# back to Claude as the reason.
#
# Limits worth knowing: the command text is split on & | ; and newlines rather
# than parsed by a shell, and a `git -C <dir> commit` targeting another
# checkout is judged against this one's branch. Both fail toward blocking a
# commit that would have been fine, never toward allowing one that wouldn't.
set -eu

INPUT=$(cat)

if command -v jq >/dev/null 2>&1; then
  CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
else
  CMD=$(printf '%s' "$INPUT" \
    | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    | head -n 1)
fi

[ -n "$CMD" ] || exit 0

# Is one segment of this command line a `git commit` invocation?
is_git_commit() {
  _seg=$1
  # The caller narrows IFS to newlines to split the command line into
  # segments; restore default word splitting to tokenize inside one.
  _oifs=$IFS
  unset IFS
  # Word-splitting the segment is the point here.
  # shellcheck disable=SC2086
  set -- $_seg
  IFS=$_oifs
  while [ $# -gt 0 ]; do
    case $1 in
      *=*) shift ;;
      *) break ;;
    esac
  done
  [ $# -gt 0 ] || return 1
  case $1 in
    git|*/git) shift ;;
    *) return 1 ;;
  esac
  while [ $# -gt 0 ]; do
    case $1 in
      -C|-c|--git-dir|--work-tree|--namespace|--exec-path)
        [ $# -ge 2 ] || return 1
        shift 2 ;;
      -*) shift ;;
      *) break ;;
    esac
  done
  [ "${1:-}" = commit ]
}

# `git commit -a` stages tracked modifications at commit time, so the staged
# set alone doesn't describe what would land.
has_all_flag() {
  _seg=$1
  _oifs=$IFS
  unset IFS
  # shellcheck disable=SC2086
  set -- $_seg
  IFS=$_oifs
  for tok in "$@"; do
    case $tok in
      --all|-a) return 0 ;;
      --*) ;;
      -*a*) return 0 ;;
    esac
  done
  return 1
}

COMMIT_SEG=""
ORIG_IFS=$IFS
IFS='
'
for seg in $(printf '%s' "$CMD" | tr '&|;\n' '\n\n\n\n'); do
  if is_git_commit "$seg"; then
    COMMIT_SEG=$seg
    break
  fi
done
IFS=$ORIG_IFS

[ -n "$COMMIT_SEG" ] || exit 0

BRANCH=$(git branch --show-current 2>/dev/null || true)
[ "$BRANCH" = "main" ] || exit 0

# approve-task's verified merge: `git merge --no-commit` left MERGE_HEAD behind.
MERGE_HEAD=$(git rev-parse --git-path MERGE_HEAD 2>/dev/null || echo .git/MERGE_HEAD)
[ ! -e "$MERGE_HEAD" ] || exit 0

PATHS=$(git diff --cached --name-only 2>/dev/null || true)
if has_all_flag "$COMMIT_SEG"; then
  PATHS=$(printf '%s\n%s\n' "$PATHS" "$(git diff --name-only 2>/dev/null || true)")
fi

OFFENDERS=$(printf '%s\n' "$PATHS" | sed '/^$/d' | grep -v '^tasks/' || true)
[ -n "$OFFENDERS" ] || exit 0

cat >&2 <<MSG
Blocked: this would commit task work directly to main.

Paths outside tasks/ in this commit:
$(printf '%s\n' "$OFFENDERS" | sed 's/^/  /' | head -n 20)

Work reaches main only through approve-task merging a task branch, after both
verification tiers pass on the merged result (.claude/docs/pipeline.md
§ Git branching). Check out the task's branch and commit there.

Two commits on main stay allowed and neither matches this one: the merge
commit approve-task makes with MERGE_HEAD present, and the planning-flip
bookkeeping commit that touches only tasks/.
MSG
exit 2
