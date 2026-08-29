#!/usr/bin/env sh
# Installs the task-pipeline kit into a target repo: copies templates/
# into the target root, substitutes the {TASK_PREFIX} placeholder
# everywhere, and creates the tasks/ directories. The kit lives in its
# own checkout; run this against the repo that should receive the
# pipeline:
#
#   ./install.sh <task-prefix> <target-dir>
#
# <task-prefix> becomes the task-id and branch prefix (tasks "pb-001",
# branches "pb-001" for prefix "pb"). <target-dir> is the receiving
# repo's root.
#
# The copy includes pipeline-setup.sh, which tracks the remaining
# repo-specific setup steps; this script ends by running it to show
# them.
set -eu

usage() {
  echo "usage: $0 <task-prefix> <target-dir>" >&2
  echo "  task-prefix: lowercase letters/digits, starting with a letter (e.g. pb, task, wf)" >&2
  echo "  target-dir:  root of the repo to install the pipeline into" >&2
  exit 2
}

[ $# -eq 2 ] || usage
PREFIX=$1
TARGET=$2
KIT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TEMPLATES="$KIT_DIR/templates"

# The prefix lands in branch names, filenames, and glob patterns, so keep
# it to characters that are safe in all three. No trailing dash: the docs
# append "-XXX" themselves.
case $PREFIX in
  [a-z]|[a-z]*[a-z0-9]) ;;
  *) echo "error: invalid prefix '$PREFIX' (want: lowercase letters/digits, starting with a letter)" >&2; usage ;;
esac
case $PREFIX in
  *[!a-z0-9]*) echo "error: invalid prefix '$PREFIX' (only lowercase letters and digits)" >&2; usage ;;
esac

[ -d "$TEMPLATES" ] || { echo "error: $TEMPLATES not found" >&2; exit 1; }
[ -d "$TARGET" ] || { echo "error: target dir '$TARGET' not found" >&2; exit 1; }

# Refuse to install into the kit's own checkout — the usual mistake when
# the target argument was meant to point somewhere else.
TARGET_ABS=$(CDPATH= cd -- "$TARGET" && pwd)
if [ "$TARGET_ABS" = "$KIT_DIR" ] || [ -e "$TARGET/templates/.claude/docs/pipeline.md" ]; then
  echo "error: '$TARGET' looks like the pipeline-kit checkout itself; point target-dir at the repo that should receive the pipeline" >&2
  exit 1
fi

# Refuse to clobber an existing installation or an existing CLAUDE.md;
# merging is a manual job, not this script's.
for f in CLAUDE.md .claude/docs/pipeline.md; do
  if [ -e "$TARGET/$f" ]; then
    echo "error: $TARGET/$f already exists; refusing to overwrite. Merge by hand or remove it first." >&2
    exit 1
  fi
done

# Render every template file into the target, substituting the
# placeholder on the way — the kit's own templates stay pristine for
# reuse elsewhere. Redirection doesn't carry file modes, so restore the
# executable bit where the template has one (pipeline-setup.sh).
(cd "$TEMPLATES" && find . -type f) | while IFS= read -r rel; do
  rel=${rel#./}
  dest="$TARGET/$rel"
  mkdir -p "$(dirname -- "$dest")"
  sed "s/{TASK_PREFIX}/$PREFIX/g" "$TEMPLATES/$rel" > "$dest"
  [ ! -x "$TEMPLATES/$rel" ] || chmod +x "$dest"
done

for d in tasks/active tasks/completed tasks/abandoned; do
  mkdir -p "$TARGET/$d"
  touch "$TARGET/$d/.gitkeep"
done

echo "Installed pipeline kit into $TARGET with task prefix '$PREFIX-'."
echo "Remaining setup is tracked by marker lines in the installed files;"
echo "run ./pipeline-setup.sh in the target repo anytime to list them."
echo
# The checker exits nonzero while steps remain, which is the expected
# state right after an install — don't let that fail this script.
(cd "$TARGET" && ./pipeline-setup.sh) || true
