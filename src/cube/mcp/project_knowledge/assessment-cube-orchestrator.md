# Assessment Cube — Session Orchestrator

This file is the standing session protocol for Claude when working assessment
data in the Achievement Directors' shared Cube Project. Follow it at the start
of, and throughout, every session. It governs process — what to check before
answering, how to route a question, how to log a session — not data meaning;
settled Cube data-usage conventions live in a companion file,
`assessment-cube-reference.md`, described under Routing below.

## How to use this file

This file and `assessment-cube-reference.md` are both loaded as project
knowledge in the shared Project. Run the standing protocol below before
answering any substantive question, every session — do not skip or reorder steps
because a request looks urgent or simple. When a question turns on a data-usage
convention (a field meaning, a Cube quirk, a settled default), route to the
matching section of `assessment-cube-reference.md`. When it turns on a
convention that has not been ratified by instructional leadership, do not decide
it yourself — flag it per Flag, don't invent, and keep going.

## The standing protocol

Run these six steps, in order, at the start of every session. Step 1 is a hard
gate: do not answer a substantive participant query before it passes. Steps 3-6
apply to every query in the session, not only the first. Before step 1, capture
the participant's name (or initials) — ask if you do not have it, because the
session log's filename depends on it (see Session log below).

1. **Calibration first (hard gate).** Before answering any participant query —
   regardless of how urgent or complex the opening request is — check network
   ADA for the most recent week-end record
   (`student_attendance_view.avg_daily_attendance`, filtered
   `is_week_end_record = true`, most recent `dates_school_week_start_date`).
   Confirm connectivity and data currency, and sanity-check the value against a
   known figure. An end-of-year ADA drop-off is an expected seasonal pattern,
   and a zero-row / empty result in summer (no active school week) is likewise
   expected — neither is a connectivity failure or a defect.
2. **Force-refresh `meta` at session start.** The cached catalog can be stale; a
   stale catalog has already produced a confident-but-wrong "unanswerable" in a
   prior session. If a field or view you need appears to be missing, refresh
   `meta` before concluding it is unavailable.
3. **Filter `response_type` explicitly** on every assessment query. Never rely
   on the silent default blend — see `assessment-cube-reference.md` (Shared
   conventions) for the accepted values and the default.
4. **State confidence and flag every inference.** Give each answer a High /
   Medium / Low confidence rating, and explicitly list every interpretation or
   default you chose on the participant's behalf. Surface these for human
   confirmation before anyone uses the answer externally.
5. **PII gate.** Hold any request for an identified student roster (names or IDs
   paired with performance or IEP status) pending explicit permission and a
   stated legitimate need. Never write student identifiers into the session log
   or the chat transcript; an authorized identified deliverable goes only into
   its own output file, never into the persistent log.
6. **Flag, don't invent** when a query needs an undecided default. This is the
   same rule as the next section, applied per query — if a provisional choice is
   unavoidable to keep going, label it provisional and log it as an open
   decision.

## Flag, don't invent

The line between settled and undecided runs through individual topics, not just
between them:

- **Document what a field actually means and how the cube behaves**, when that
  is verifiable from data or field definitions. That is settled mechanics, and
  it belongs in `assessment-cube-reference.md`, not here.
- **Do not invent the organization's policy defaults.** Where a default is
  needed to answer a question but has not been ratified by instructional
  leadership, your job is to flag it as an inference and log it as an open
  decision — never to answer it as if it were settled.

The following are currently open. Do not state a value, threshold, or rule for
any of them — flag and log only, and route the decision to instructional
leadership:

- the minimum-n suppression threshold for small-group results
- intervention tier cut-scores
- whether a multi-instrument mastery question should pool instruments or report
  per instrument
- which subjects count as `math` for network reporting
- how `grade_level_tested` should be handled when it reflects a prior grade

Some individual fields also carry their own narrower open question (for example,
which count measure is the default for a count/share question) — those are
called out inline in `assessment-cube-reference.md`; flag them the same way when
you hit one.

## Routing

Given a question, first determine the assessment family, then open the matching
section of `assessment-cube-reference.md`:

- **Region hint.** NJ regions are Newark, Camden, and Paterson; the FL region is
  Miami.
- **Assessment hint.** `QA` / `MQQ` / `CRQ` implies the internal (Illuminate)
  family; i-Ready, DIBELS, or STAR each map to their own vendor-diagnostic
  section; NJSLA / NJGPA implies NJ state; FAST / EOC implies FL state. Select a
  source with `assessment_type`, not `is_internal_assessment` (see Shared
  conventions).
- **If the family is ambiguous, ask before querying** — do not guess and query
  anyway.

`assessment-cube-reference.md` has these sections; go to the one that matches:

1. **Shared conventions** — mechanics that apply across every assessment family:
   `response_type`, grain, performance bands, subject fields, enrollment
   resolution, teacher attribution, domain rollup.
2. **Internal — Illuminate** — `QA` / `MQQ` / `CRQ` module conventions.
3. **Vendor normed diagnostics — i-Ready** — grade-level placement scale.
4. **Vendor normed diagnostics — DIBELS** — benchmark tiers.
5. **Vendor normed diagnostics — STAR** — `Level 1`–`Level 5`.
6. **NJ state** — NJSLA, NJSLA-Science, and NJGPA conventions.
7. **FL state** — FAST, FL-Science, and EOC conventions.

Always check Shared conventions first, then the family-specific section — each
family section assumes the shared mechanics and only adds what differs.

## Session log — write it to a Markdown file

Keep the log in the conversation as you go (per the protocol: log every query as
it happens, never batch it to the end), and **also write it out as a
downloadable Markdown file — without being asked.** Never write a student name
or student ID into it: see the PII gate above and the guardrail line at the
bottom.

### Filename

```text
WG_LOG_<YYYY-MM-DD>_<HHMM>_<participant>.md
```

- `<YYYY-MM-DD>_<HHMM>` — session start, 24-hour clock. State in the header
  which timezone you used; if you only have a UTC clock, say UTC.
- `<participant>` — the participant's last name, lowercased (`walters`). Two
  participants: hyphenate (`walters-ramirez`); more than two: use the team name.
  No name given: use initials, then `unknown` as a last resort.
- Example: `WG_LOG_2026-07-24_1430_walters.md`
- **The filename is the log's identity — there is no session number to
  reconcile.** Several logs per day, including several from the same person, are
  expected; this keeps them from colliding and sorts them chronologically.

### When to write it

1. Write the file as soon as the first substantive query is logged, so the
   artifact exists even if the session ends abruptly.
2. Refresh it after each subsequent query and after any deliverable.
3. Write the final version at session end, with the handoff summary complete.

Reuse the same filename all session so each write replaces the previous one
instead of accumulating near-duplicates. If file creation is unavailable to you,
fall back to emitting the whole log as one fenced Markdown block for the
participant to save by hand — and say that is what you did.

### What goes in it

```text
SESSION LOG — Assessment Cube

HEADER
- Session start: (date, time, timezone)
- Log file: WG_LOG_YYYY-MM-DD_HHMM_<participant>.md
- Participant(s): (name, or initials if no name was given)
- Cubes/views in scope:
- Known issues carried in from prior sessions:
- Calibration result: [match / mismatch] — context:

PER-QUERY BLOCK (copy this block once for each question asked this session)
- Query number:
- User asked:
- Cube views/measures used:
- Response complexity: [simple / multi-step / exploratory]
- Confidence: [High / Medium / Low]
- Trip flag: [yes / no] — description:
- Inference flags: [list every interpretation or default assumed]
- Missing context:
- Out-of-scope: [yes / no] — note:
- Outcome:
- Notes:

SESSION PATTERNS
- Recurring question types:
- Recurring trips:
- Recurring inferences:
- Low-confidence responses:
- Out-of-scope questions:
- Questions that belong in a dashboard instead:
- Questions that should become a custom skill:

FIX BACKLOG
| # | Issue | Type (trip / inference-gap / data-quality / scope-boundary) | First seen | Priority | Status |
|---|-------|---------------------------------------------------------------|------------|----------|--------|
|   |       |                                                                 |            |          |        |

HANDOFF
- Prioritized trips:
- Prioritized inference gaps:
- Custom-skill candidates:
- Dashboard candidates:
- Low-confidence responses to review:
- Out-of-scope items:
- Open questions for the model owner:
- Recommended fixes:

GUARDRAIL
- Confirmed: no student name, student ID, or other PII was written anywhere
  in this log. [confirmed / not confirmed]
```
