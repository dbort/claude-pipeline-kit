// doc-hygiene pipeline, executed via the Workflow tool.
//
// This file is a template, not a runnable script. Before calling Workflow,
// replace the two placeholders near the bottom:
//
//   GROUPS_PLACEHOLDER   -> literal JS array of Step 2's file groups, e.g.
//                           [["src/a.py", "src/b.py"], ["docs/c.md"]]
//   DIFF_BASE_PLACEHOLDER -> null for a full-tree sweep, "HEAD" for plain
//                           --diff, or the ref string (e.g. "main") for
//                           --diff=<ref>
//
// Pass the substituted text as Workflow's `script` parameter. Don't pass
// `args`: the groups and base are embedded as literals.
//
// The rule text in the three prompt builders below is the authoritative
// ruleset for this repo's comment and doc style. CLAUDE.md's "Writing style
// by destination" section carries a distilled subset so agents generate
// cleaner text up front; keep the two in sync when editing either. The
// style-pass rules are adapted from the stop-slop skill (MIT License,
// Copyright (c) 2025 Hardik Pandya) - see ../NOTICE-stop-slop-LICENSE.md.

export const meta = {
  name: 'doc-hygiene',
  description: 'Content-audit then style-pass comments and docs, then verify nothing factual was lost',
  phases: [
    { title: 'Content Audit' },
    { title: 'Style Pass' },
    { title: 'Verify' },
  ],
}

// diffCmd is the exact git command an agent should run against a single
// file to see this pass's target scope: uncommitted changes (diffBase ===
// "HEAD") or everything committed since diverging from a ref (diffBase is
// any other non-null string). null (full-tree mode) never reaches this --
// callers only build diffScopeInstruction when diffBase is truthy.
function diffCmd(diffBase) {
  return diffBase === 'HEAD' ? 'git diff HEAD -- <file>' : `git diff ${diffBase}...HEAD -- <file>`
}

function diffScopeInstruction(diffBase) {
  return `This is a DIFF-SCOPED pass, not a full-file sweep: before editing each file, run `+'`'+diffCmd(diffBase)+'`'+` yourself to see exactly which lines are new or changed. Read the whole file for context, but constrain your EDITS to those changed lines, plus any pre-existing comment nearby that the diff has made stale or newly inaccurate. Do not perform a general hygiene sweep of unrelated, unchanged content elsewhere in the file, even if you notice something else worth fixing there — leave it and don't mention it in your report, that's out of scope for this pass.`
}

function contentAuditPrompt(files, diffBase) {
  return `You are auditing code comments and/or markdown docs for CONTENT-level issues. Edit files directly with the Edit tool where changes are needed. Only touch comments and markdown prose — never executable code, config-file directives, command syntax, or markdown structure (headings, links, code fences) beyond what these rules require.
${diffBase ? '\n' + diffScopeInstruction(diffBase) + '\n' : ''}
RULES:
1. Delete "what" content: remove any comment/sentence that merely restates the code or fact right next to it. Keep only content explaining non-obvious business logic, a technical tradeoff, or *why* something exists.
2. Prune stale historical artifacts and reader-memory framing: the code should read as though it has always been in its current state, and as though the reader has no memory of how it used to work. Delete mentions of earlier code versions, previous refactors, unchosen alternatives, or dead task-id namedrops ("this replaces {TASK_PREFIX}-XXX's old thing"), AND rewrite looser temporal-contrast phrasing that leans on the reader remembering prior behavior even without naming it explicitly — "works exactly as before," "no longer requires," "used to," "now supports" used as a before/after contrast rather than a plain statement of the current rule. State the current behavior directly, as if it were the only behavior that ever existed. Two exceptions, both about *why*, not *what changed*: keep it if a senior engineer would reasonably ask "why didn't we do X instead?", or if it guards against reintroducing a known bug/regression. A "(see {TASK_PREFIX}-XXX)" or "(see docs/FOO.md)" pointer to CURRENT, still-true context is fine to keep, and is encouraged specifically when it explains why otherwise-unusual logic is present; only cut comparisons to superseded code or behavior, not pointers that clarify present-day design.
3. Doc-comment convention: a function/type/module doc comment's summary line should lead with the identifier's name (where the language's convention does so) and add real information beyond repeating it. Keep parameter/return descriptions to one direct line. Move implementation-detail rationale out of function-level doc comments into a concise inline comment on the code block it actually explains (applies to test code too).
4. Strip LLM/marketing slop: throat-clearing openers ("Here is...", "In this function, we will...", "This module acts as a robust solution..."), fluff words (seamlessly, robust, leverage, comprehensive, scalable, meticulously, crucial, paradigm, delve, dynamic), and passive/indirect voice standing in for a direct statement.
5. Surgical editing: leave clean, already-direct content untouched. Do NOT refactor executable code, config structure, or build-file instructions. If a comment appears to describe behavior the code doesn't actually have, don't fix the code, just flag it in your report.
6. Field/member docs on the declaration: when the language convention allows it, document each struct/class field on its own declaration, not batched into the type-level comment. A type-level comment should describe the type as a whole; per-field meaning belongs directly on that field.

FILES TO AUDIT (read each fully, then edit as needed):
${files.map(f => `- ${f}`).join('\n')}

Report: list of edits made (file:line, brief description), and any flagged discrepancies where a comment's claim doesn't match the code. Concise, bullet points only.`
}

function stylePassPrompt(files, contentAuditReport, diffBase) {
  return `You are applying a "stop-slop" writing-STYLE pass to comments and/or markdown prose ONLY (not code, not config directives, not command syntax) in the files below. A content-level audit already ran on these files (report below) — don't redo that pass, only fix AI-writing-pattern style: adverbs, dashes, passive voice, formulaic structures. Edit files directly with the Edit tool.
${diffBase ? '\n' + diffScopeInstruction(diffBase) + ' The prior content-audit pass was itself diff-scoped, so its report below already reflects that.\n' : ''}
Prior content-audit report for context (don't redo it, just don't contradict it):
${contentAuditReport}

RULES (style only):
1. Kill filler adverbs/hedges: really, just, literally, genuinely, honestly, simply, actually, deeply, truly, fundamentally, inherently, inevitably, interestingly, importantly, crucially, purely, specifically (as intensifier), precisely (as intensifier), meaningfully, categorically, entirely, silently (unless describing real observable behavior — keep those), automatically (when redundant), retroactively, intentionally, unconditionally (when redundant). Judgment call: if the word conveys real technical/scope meaning (e.g. "only opens and pings" — "only" is load-bearing scope info), keep it. If it's empty emphasis, cut it and rephrase to read naturally without it.
2. Remove ALL em-dashes (—) and ASCII "--" used as a dash-style aside/parenthetical (e.g. "does X -- because Y"). Replace with a comma, period, colon, or semicolon depending on the relationship between the clauses. Do NOT touch "--" that's part of an actual CLI flag (--build-tags, --wait, --apply, etc.) — that's code syntax, not punctuation.
3. Avoid formulaic AI structures: binary contrasts ("not X, it's Y" -> state Y directly), negative listing (listing what something is NOT before saying what it IS -> just state it), rhetorical setups ("Here's what/why...", "Think about it:" -> cut the throat-clearing), false agency (inanimate things doing human verbs, e.g. "the decision emerges" -> name the actual actor, or the specific mechanism if there's genuinely no human actor -- "the loop stops itself" describing real automation is fine, that's accurate), and passive voice standing in for a nameable actor (rewrite active where it reads more directly, but don't force it if passive is the more natural technical phrasing).
4. Lazy extremes ("every", "always", "never") used as vague sweeping claims -> be specific. BUT when a comment states a genuine technical invariant, rule, or design decision, that's precise and correct -- leave it.
5. No "here's the thing", "it's worth noting", "at the end of the day", "when it comes to", "the reality is" throat-clearing.
6. Heavy or nested parentheticals: a `(...)` that crams in more than one independent fact, or that itself contains another `(...)`, is a readability problem even though it's grammatically fine. Unpack it: split into separate sentences, join with a comma/colon, or (for a list of comparable items) use an actual list. A short, single-fact aside in parens is fine; a paragraph's worth of detail stuffed into one parenthetical is not.

CRITICAL: preserve every technical fact, code reference, and rationale. You are changing STYLE, not content. If a comment already reads clean and direct, leave it untouched.

FILES:
${files.map(f => `- ${f}`).join('\n')}

Report: list of edits made (file:line, brief before -> after). Concise, bullet points only.`
}

function verifyPrompt(files, contentAuditReport, styleReport, diffBase) {
  return `You are the verification step of a two-pass documentation cleanup. Two prior agents edited comments/prose in the files below: first a content audit (removed stale references, restated-the-obvious text, fluff), then a style pass (removed filler adverbs, dashes, passive voice, formulaic structures)${diffBase ? ', both scoped to only the lines changed in each file\'s target-scope diff plus any pre-existing comment those changes made stale' : ''}. Your job: confirm no genuine technical fact, code reference, rationale, or caveat was lost or altered, only reworded${diffBase ? ', and confirm neither prior pass strayed into unrelated unchanged content outside the diff' : ''}.

Prior reports for context:
--- Content audit ---
${contentAuditReport}
--- Style pass ---
${styleReport}

For each file, run \`git diff -- <file>\` (bare, no ref -- this shows only this pipeline's own uncommitted edits made just now, regardless of which mode discovered the file) to see exactly what changed since this pipeline started, and read the current content. Check specifically:
- Did any edit change what a comment CLAIMS about the code's behavior, not just how it's phrased?
- Was a genuinely load-bearing "why" explanation (a non-obvious rationale, tradeoff, or gotcha) deleted rather than reworded?
- Does any comment now describe behavior the code doesn't actually have (spot-check the riskiest-looking claims against the real code)?${diffBase ? '\n- Did either prior pass edit a line outside the original diff\'s changed regions (beyond a stale-comment fix directly caused by the diff)? That would be scope creep for a diff-scoped pass.' : ''}

FILES:
${files.map(f => `- ${f}`).join('\n')}

Report: PASS or FLAGGED per file. For anything flagged, give file:line, what changed, and why it looks like a content loss (or scope creep) rather than a legitimate fix (quote the before/after). Concise.`
}

const groups = GROUPS_PLACEHOLDER
const diffBase = DIFF_BASE_PLACEHOLDER

const results = await pipeline(
  groups,
  group => agent(contentAuditPrompt(group, diffBase), { phase: 'Content Audit', label: `audit:${group[0]}` })
    .then(auditReport => ({ auditReport })),
  (r, group) => agent(stylePassPrompt(group, r.auditReport, diffBase), { phase: 'Style Pass', label: `style:${group[0]}` })
    .then(styleReport => ({ ...r, styleReport })),
  (r, group) => agent(verifyPrompt(group, r.auditReport, r.styleReport, diffBase), { phase: 'Verify', label: `verify:${group[0]}` })
    .then(verifyReport => ({ ...r, verifyReport }))
)

return results
