---
next_id: friction-001
---

# Friction log

Moments where developing or testing this repo forced a workaround: a
missing tool, data in the wrong shape, a doc that had to be
reverse-engineered. Log it in the same session, even when the workaround
succeeded. Defects in the project itself go in `bug-log.md` instead.

An entry qualifies only if its fix is something this repo could build or
write. An upstream tool's permanent behavior belongs in a comment at the
call site, a doc under `.claude/docs/`, or a Claude memory.

Format, oldest first:

- `friction-NNN` - **<what was needed>**: what happened; the workaround
  used. Simpler if: <the missing tool/data/doc>.

The id is `next_id` from the front matter; increment it in the same
commit. It only moves forward, even when entries are deleted. An entry
commits with the work on the branch where the issue was found and
reaches `main` in that work's merge, never on a branch of its own. An
issue already present on `main` commits on `main`. When `/ship`'s merge
gate finds an issue the shipping branch causes, the ship fails and the
entry commits on that branch. A commit that fixes the entry, or removes
the code it concerns, deletes it and records the papercut and its fix in
its message.

## Entries
