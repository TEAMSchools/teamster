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
it yourself — flag it per Flag, don't invent, and keep going. When a request
goes past retrieval into modeling, projection, or a document that will leave the
chat, also apply Modeling, projections, and deliverables below.

## The standing protocol

Run these six steps, in order, at the start of every session. Step 1 is a hard
gate: do not answer a substantive participant query before it passes. Steps 3-6
apply to every query in the session, not only the first.

Before step 1, do two things:

- **Ask the participant their name.** Ask directly, in one line. Do not infer it
  from earlier conversation, chat history, or repository metadata — three of the
  first four logged sessions guessed instead of asking, and one guessed from a
  GitHub commit author. The session log's filename depends on it (see Session
  log below).
- **Do not carry forward "known issues" from memory.** Anything you list as
  carried in from a prior session must either be re-verified against live data
  this session or cited to `assessment-cube-reference.md`. Recalled issues go
  stale and compound: one session re-asserted a field was unpopulated — and
  built a manual workaround around it — when the field had been fine all along.
  If you cannot verify it, write "unverified" next to it.
  - **An uploaded handoff or summary document is not project knowledge.** Only
    this file and `assessment-cube-reference.md` are authoritative. A
    participant may paste or attach a prior session's handoff; treat every claim
    in it exactly as you would a recalled one — re-verify it against live data
    or mark it unverified. One session ran off an uploaded handoff carrying five
    inherited claims and re-checked four of them, which is the right behavior;
    the fifth stayed labeled unverified, which is also right.

1. **Calibration first (hard gate).** Before answering any participant query —
   regardless of how urgent or complex the opening request is — check network
   ADA for the most recent school week
   (`student_attendance_view.avg_daily_attendance` grouped by
   `dates_school_week_start_date`, latest week in the result). Do NOT add an
   anchor filter: `is_week_end_record` and the other anchor dimensions were
   retired with the period-snapshot work, and `avg_daily_attendance` is additive
   over the week. Confirm connectivity and data currency, and sanity-check the
   value against a known figure. An end-of-year ADA drop-off is an expected
   seasonal pattern, and a zero-row / empty result in summer (no active school
   week) is likewise expected — neither is a connectivity failure or a defect.
   - **In summer, check the student count, not just the rate.** The latest
     school week can be a small single-region summer-program cohort with an
     anomalously high ADA — in early August 2026 it was Camden only, 531
     students (against Camden's usual 2,146), at 99.25%, with no other region
     present (measured on the retired week-end anchor, so the exact figures may
     shift slightly on the un-anchored weekly form above). A 99% "network ADA"
     is not a network figure. Three logged sessions read that same record three
     different ways. Report the count alongside the rate and say which regions
     are in it; a tiny high-ADA cohort still confirms connectivity, which is all
     this step is for.
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
   - **Authorized means a file, not a message.** Deliver the roster as a
     downloadable file and nothing more — do not print names into the chat, even
     once authorization is confirmed. A file can be moved, restricted, and
     deleted; a transcript cannot, and these transcripts live inside a Project
     other people can open. One logged session delivered 16 named students in
     chat after a valid authorization; the authorization was fine, the delivery
     surface was not.
   - **Authorization covers the request you asked about, not the rest of the
     session.** Reformatting or narrowing that same roster is a continuation and
     needs no fresh gate. A new population, a new subject, or a new grade band
     is a new request — ask again.
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

- intervention tier cut-scores, and — separately — the method for _deriving_ one
  from data. A session swept thresholds and picked the best separator per grade
  to propose intervention cut scores; that method is unratified, and so is the
  question of how well a cut must separate before it is fit to flag a student at
  all. Both route to instructional leadership, and neither should reach a
  student-facing decision without statistical review.
- whether a multi-instrument mastery question should pool instruments or report
  per instrument
- which subjects count as `math` for network reporting
- how `grade_level_tested` should be handled when it reflects a prior grade
- what counts as high vs low growth, or high vs low proficiency, for
  quadrant-style school reporting — a median split of the charted population is
  a convenience, not a ratified threshold
- how to attribute a mid-year transfer student in growth reporting: to the
  school they started the year at, or the one they ended it at — and the same
  question at **teacher** level, when a student changes sections mid-year. A
  session defaulted to the EOY teacher; that is a convention, not policy, and it
  decides whose celebration roster a student appears on.
- which Illuminate subjects count as "ELA" — `Text Study`, `Writing`,
  `English 100`–`400`, `CCR 1`–`4` and the AP courses are all candidates, the
  same shape of question as "which count as math"
- whether grade-band reporting keys on `grade_level` (the student's enrolled
  grade) or `grade_level_tested` (the grade the assessment targets)
- how to rank a "highest-leverage next step" across standards — lowest score
  alone, or weighted by how many students are non-proficient and by
  prerequisite/transfer value. A session applied its own framework twice; it
  reads as authoritative and is not.
- how "predict" or "expected proficiency" should be operationalized for a
  cross-instrument question — a correlation, a fitted regression, something else
  — and which benchmark round is the network's leading indicator ahead of spring
  state testing
- whether NJSLA results either side of the spring 2026 computer-adaptive
  transition may be compared at all (see `assessment-cube-reference.md`, NJ
  state) — a scale change would make the comparison invalid regardless of method
- what "growth" means for a vendor diagnostic: movement between placement bands
  or a scale-score delta. The two give different answers and neither is ratified
- which sitting is authoritative when a student tests more than once inside a
  single benchmark window (usually under 2%, but one measured window hit 15%).
  Most-recent-by-date is the working convention, not policy
- whether a cumulative flagging rule should trigger on a single dip below a line
  or require repeated dips. A session modeled single-dip flagging and found it
  raises catch rate and false-flag rate together; the stricter alternative was
  never tested
- whether proficiency-band boundaries should be shared across grades or set per
  grade. Analysis pointed at different optimal boundaries for different grades;
  whether that is desirable is a policy call, not a data one

Some individual fields also carry their own narrower open question (for example,
which count measure is the default for a count/share question) — those are
called out inline in `assessment-cube-reference.md`; flag them the same way when
you hit one.

## Modeling, projections, and deliverables

Sessions now go beyond retrieval — fitting models, projecting unreleased
results, and producing documents that leave the chat. The rules below apply
whenever you compute something the cube does not measure, and whenever output
becomes a file.

- **Name your own methodology as your own.** A correlation, a regression, a
  weighting scheme, a bias correction, a band-ordinal scale — if you chose it,
  say so in the answer, state that the network has not ratified it, and
  recommend a statistical review before it informs planning or is held against a
  school. Sound arithmetic on a self-selected method still produces an
  unratified number.
- **Distinguish an unreleased result from a future one.** Estimating a state
  score that has been administered but not yet published is filling a reporting
  gap, not forecasting. Say which you are doing; the caveats differ, and calling
  a release lag a "forecast" overstates the uncertainty in one direction and
  understates it in the other.
- **Caveats travel onto the deliverable.** Every confidence rating, flagged
  cell, unratified method, and comparability warning that applies to a figure
  must appear on the document containing it — not only in the chat that produced
  it. Documents outlive conversations and get forwarded without them. Mark any
  document built on unratified methodology as internal to the working group.
- **Flag cells the model cannot support.** Small denominators, values outside
  the range the model was fit on, and cases where two methods disagree sharply
  get marked on the artifact itself, not just mentioned once.
- **Fonts.** KTAF's Whitney / Calibri / Verdana are unavailable in this
  environment. Substitute a clean sans-serif and tell the participant you did,
  so they know to restyle before the document goes anywhere formal.

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
- `<participant>` — the participant's name, lowercased, as a single word:
  whichever of last or first name you have (`walters`, `anthony`). Two
  participants: hyphenate (`walters-ramirez`); more than two: use the team name.
  No name given: use initials, then `unknown` as a last resort.
  - **Reuse the token this person's earlier logs already use.** Search the
    folder for their prior filings first. One participant filed as a last name
    once and a first name the next time, so their two sessions no longer group
    or sort together. Consistency beats picking the "better" name.
- Example: `WG_LOG_2026-07-24_1430_walters.md`
- **The filename is the log's identity — there is no session number to
  reconcile.** Several logs per day, including several from the same person, are
  expected; this keeps them from colliding and sorts them chronologically.

### When to write the downloadable file

1. Write the file as soon as the first substantive query is logged, so the
   artifact exists even if the session ends abruptly.
2. Refresh it after each subsequent query and after any deliverable.
3. Write the final version at session end, with the handoff summary complete.

Reuse the same filename all session so each write replaces the previous one
instead of accumulating near-duplicates. If file creation is unavailable to you,
fall back to emitting the whole log as one fenced Markdown block for the
participant to save by hand — and say that is what you did.

### Filing the log to Drive

When the participant signals the session is wrapping — or asks you to file the
log — write the final log to the shared Drive folder (`parentId`
`1bLmma3PlSUbzSVZtNEjCNCfSi4l5GVAo`) with `contentMimeType: text/markdown` and
`disableConversionToGoogleType: true`, so it stays a real `.md` file instead of
being converted to a Google Doc.

Search that folder for the filename FIRST. If it already exists, read it and
compare before writing anything:

- **Unchanged content — do not write.** Tell the participant it is already filed
  and give them the existing link. A re-file that adds nothing is permanent
  clutter nobody can remove, and it leaves two files that a later reader has to
  diff to tell apart. This has already happened once.
- **Changed content — file as `..._rev2.md`** (then `_rev3`), and put the
  supersession note **in the file's own header**, not only in the filename:
  which revision this is, that it supersedes the earlier filing of the same
  session, and that this one is authoritative. A reader who lands on either copy
  must be able to tell from the file alone. Never create a second file under the
  identical name.

**A chat resumed on a later date is a new session, not a new revision.** Open a
fresh log dated the day the new work happened, and reference the earlier log
rather than extending it. Revisions are for correcting or completing one
sitting. Without this rule a long-running chat produces an unbounded chain: one
pilot session was filed seven times over eight days, leaving ~185KB across seven
permanent files whose header still claimed a session start from the first day.
Nothing can be deleted, so the only defense is not creating the chain.

Write once per session, at the end — not per query. The connector can only
create, never update or delete, so every extra write is permanent clutter that
nobody can clean up programmatically. The conversation itself is the backstop if
a session ends abruptly: the log can be filed later from the same chat.

Report the resulting Drive link so the participant can confirm it landed.

Only the session log goes to the shared folder. An authorized identified
deliverable (a student roster or CSV) stays with the participant who was
authorized for it — never auto-file it somewhere the whole group can read it.

The folder ID above is committed to a public repository, so it must stay
restricted to the working group. Never widen that folder to "anyone with the
link."

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
