#!/usr/bin/env sh
# Reports which pipeline-kit setup steps are still pending in this repo.
# The installer left a marker line at every spot needing repo-specific
# input; each marker says what to do, and whoever completes the step
# deletes that line. Run this script from anywhere to list what remains;
# it exits nonzero while any marker is left, so the pipeline skills can
# gate on it.
#
# Once no markers remain, a run of this script removes the setup-gate
# blocks from the pipeline skills (so they stop re-checking a finished
# setup) and reports that the script itself can be deleted. It never
# commits; review and commit its edits yourself.
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# Both patterns are split mid-word so this script's own source can never
# match its own scan.
TODO_PAT='PIPELINE-KIT-SETUP-''TODO('
GATE_PAT='PIPELINE-KIT-SETUP-''GATE'
SELF=$(basename -- "$0")

hits=$(grep -rnF --exclude-dir=.git --exclude="$SELF" -- "$TODO_PAT" . 2>/dev/null || true)

if [ -n "$hits" ]; then
  count=$(printf '%s\n' "$hits" | wc -l | tr -d ' ')
  echo "Pipeline setup incomplete: $count step marker(s) remain."
  echo "Each marker line below says what to do; delete the marker line once its step is done, then re-run this script."
  echo
  printf '%s\n' "$hits" | sed 's|^\./||'
  exit 1
fi

# No markers left: strip the setup-gate blocks out of the skills.
gated=$(grep -rlF --exclude-dir=.git --exclude="$SELF" -- "${GATE_PAT}-BEGIN" . 2>/dev/null || true)
if [ -n "$gated" ]; then
  for f in $gated; do
    # sed -i is not portable between GNU and BSD; a .bak suffix works on both.
    sed -i.bak "/${GATE_PAT}-BEGIN/,/${GATE_PAT}-END/d" "$f"
    rm -f "$f.bak"
    echo "Removed the setup gate from ${f#./}."
  done
  echo
fi
echo "Pipeline setup complete: no step markers remain."
echo "Review the diff, commit, and delete this script ($SELF)."
