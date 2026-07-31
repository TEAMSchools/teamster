---
name: nj-sleds-error-attribution
description: >-
  Use when an NJSLEDS Course Roster upload comes back with an error count but no
  error detail. Triggers: "NJSLEDS says 23 errors but won't tell me what they
  are", "which errors are in this upload", attributing or guessing upload
  errors, or any question about what a bare NJSLEDS error count represents. Also
  use when asked what the Staff or Student Course Roster handbook validates for
  a given field.
---

# NJSLEDS upload error attribution

## The situation this exists for

NJSLEDS has reduced its service level because of capacity constraints. It still
accepts and processes Course Roster uploads, but it only generates detailed
error information overnight, roughly midnight to 1am the following day. So an
upload returns a bare count — "23 errors" — with no indication of which records
failed or which rules they broke.

Waiting a day per iteration is not workable inside the submission window. This
skill closes that gap: it evaluates the handbook's documented validation rules
against the exact file that was uploaded and works out which rule, or
combination of rules, accounts for the reported count.

## Before you start

Ask for two things if they were not given:

1. **The exact file that was uploaded.** Not a regenerated one — a re-pull may
   differ from what the state saw, and then you are explaining the wrong
   artifact.
2. **The error count NJSLEDS reported**, and whether it was the staff or student
   submission.

You can run without a count to get a plain violation report, but the attribution
is the point.

## How to run it

Everything lives in `docs/superpowers/nj-sleds-roster/error-attribution/`. Run
from inside that directory so the sibling imports resolve.

```bash
cd docs/superpowers/nj-sleds-roster/error-attribution
uv run python attribute_errors.py /path/to/NJ_Student_Course_Submission.csv --errors 23
```

The submission type is inferred from the header. To drill into one rule and get
the local identifiers of its violating rows:

```bash
uv run python attribute_errors.py /path/to/file.csv --rule STU-CREDITSEARNED-RANGE
```

## How to read the output

The report has four parts, and the order matters:

1. **Handbook rule violations** — a count per rule, with the handbook page and
   the verbatim error text. This is the evidence base; everything else is
   inference on top of it.
2. **Attribution** — rule combinations summing exactly to the reported count.
   **Prefer single-rule explanations.** Several rules coincidentally summing to
   the same total is common and is not a diagnosis.
3. **Additional local findings** — KTAF expectations the handbook does not
   impose. The state never validates these, so they can never explain its count.
   Do not fold them into a hypothesis.
4. **Rules that cannot be checked locally** — an unexplained residual most
   likely lives here.

Two numbers are reported because a bare count is ambiguous: **error instances**
(one per violated field, so a row failing two rules contributes two) and **error
rows** (one per bad row). Which one the state means is not documented. Check
both against the target before concluding.

## The confirmation loop — this is what makes it converge

Do not treat the top hypothesis as settled. Confirm it in one cycle instead of
waiting for overnight detail:

1. Fix the top candidate at source in PowerSchool.
1. Re-pull and re-upload.
1. Check the count dropped by **exactly** that rule's violation count.

A match confirms the hypothesis. A partial drop means the rule was real but not
the whole story. No drop means it was the wrong guess — rule it out and move to
the next candidate. Over a few uploads this triangulates the whole error set.

Record what each cycle proved on
[issue #4659](https://github.com/TEAMSchools/teamster/issues/4659). Which rules
actually fired is the data that makes the next cycle faster, and it is lost if
nobody writes it down.

## Reading the rules directly

When asked what the handbook requires for a field rather than to attribute a
count, read the extracted rule text rather than the PDF:

- `handbook-rules-staff.md` — Staff Course Roster handbook v1.1, May 2026
- `handbook-rules-student.md` — Student Course Roster handbook v1.4, July 2026

Both are mechanically extracted from the handbooks and committed, so a fresh
clone needs no PDFs. The PDFs themselves live in gitignored scratch and will not
be present.

Quote the `error_text` verbatim when justifying a hypothesis. Paraphrasing loses
the citation, and the wording is what someone will check against the handbook.

## What this cannot do

Be straight about the limits rather than filling them with a guess:

- Rules needing an external input are marked not-checkable with the reason. The
  staff five-field combination error needs the state Staff Management export;
  SCED code validity needs the NCES code list; the dual-enrollment check needs
  the NJSLEDS OPE ID list.
- The tool cannot know which reading of the count the state used, or whether it
  stops at the first error per row.
- A combination summing to the target is a hypothesis, not a finding. Say so.

If the residual is unexplained, the honest answer is which uncheckable rules
could account for it — not a fabricated cause.

## PII

The upload files carry names, dates of birth, and state IDs. The report prints
only counts and rule ids. `--rule` prints local identifiers only, deliberately
omitting names, dates of birth, and state IDs, following the audit runbook's
worklist convention.

Keep all row-level output local. Only counts and rule ids may go to an issue, a
pull request, Slack, or any other external surface.

## Related

- `docs/superpowers/nj-sleds-roster/error-attribution/HANDOFF.md` — the task
  brief and setup steps.
- Issue [#4659](https://github.com/TEAMSchools/teamster/issues/4659) — this
  work, and where to record what each upload cycle proved.
- Issue [#4280](https://github.com/TEAMSchools/teamster/issues/4280) — the audit
  runbook and helper-query pack for the wider submission.
