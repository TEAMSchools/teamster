# Spec — Assessment Cube Direction Files for the Achievement-Director Project

- **Date:** 2026-07-24
- **Issue:** [#4534](https://github.com/TEAMSchools/teamster/issues/4534)
- **Status:** Implemented — see `src/cube/mcp/project_knowledge/`
- **Author:** Anthony Walters (with Claude)

## 1. Purpose and context

A pilot group of regional achievement directors (the teaching-and-learning
subject-matter experts) works internal and state assessment data in a shared
claude.ai Project connected to the Cube semantic layer via the Cube MCP
connector. The Cube YAML tells Claude what the fields are; it does not tell
Claude the institutional conventions and behavioral quirks needed to use them
correctly. This spec defines a small set of version-controlled Markdown
"direction files" that fill that gap and are synced into the shared Project as
project knowledge.

The content is distilled from four working-group session logs in
`.claude/scratch/20260724 assessment markdown/` (2026-07-20, 07-23, and two on
07-24). Those logs already follow a consistent observation schema, so most of
the extraction is mechanical.

### Confirmed environment facts (do not re-litigate)

- Claude Skills and MCP connectors are **compatible** on claude.ai; they are not
  mutually exclusive.
- The Cube connector **works in the shared Project** in this environment. Each
  user authenticates to Cube individually (OAuth via WorkOS to Google
  Workspace), and Cube enforces row-level access policies per user, so a shared
  Project exposes live data without leaking beyond each user's permissions.
- Project knowledge files below the context limit are loaded **whole** (no
  per-file token savings); above the limit, claude.ai auto-enables retrieval,
  where well-named, well-separated files help retrieval precision. A Skill is
  the tool that gives true on-demand loading, if that ever becomes the priority.

## 2. What we are building

Two Markdown files (the deliberately-chosen two-file shape; split further only
on a real trigger — see Section 8):

1. **Orchestrator** — the standing session protocol, routing to the right
   assessment section, and the session-log template.
2. **Assessment reference** — settled Cube data-usage conventions, with sections
   for shared conventions, internal (Illuminate) assessments, NJ state
   assessments, FL state assessments, and three vendor normed diagnostics
   (i-Ready, DIBELS, STAR) as their own reference sections.

## 3. Governing principle: settled-in, open-out, flag-don't-invent

The line between "settled" and "undecided" runs through individual topics, not
just between them. The files encode this rule:

- **Document what the fields actually mean and how the cube behaves** (settled
  mechanics, verifiable from data or field definitions).
- **Do not invent the organization's policy defaults.** Where a default is
  needed but not ratified, the protocol's job is to flag it as an inference and
  log it as an open decision — never to answer it.

Worked examples of the cut:

- `response_type` is not additive and defaults to `overall`: settled, goes in.
- `count_scores` is additive/resilient and `count_students` is distinct and
  fragile at standard grain: settled, goes in. **Which one is the default** for
  a count/share question: undecided, flagged not answered.
- `discipline` is the course crosswalk and `academic_subject` is the tested
  subject: settled, goes in. **Which subjects count as "math" for us**:
  undecided, flagged not answered.

## 4. Ownership split (three buckets)

Every recurring item in the logs belongs to exactly one owner. Only bucket 2 is
direction-file content.

1. **Upstream Cube-model defects — fixed in `src/cube/`, not documented as
   workarounds.** Examples: `assessment_type` description showing
   `state_fl`/`state_nj` instead of the real enum values; `academic_year` null
   on state rows; the `academic_year_label` field the description recommends but
   does not expose; standard-code punctuation duplicates (`7.EE.B.4.a` vs
   `7.EE.B.4a`); `proficiency_level`'s inconsistent label set; no schema-version
   / last-updated signal. Tracked as separate `src/cube/` issues.
2. **Institutional conventions that need a human decision, then documentation.**
   Minimum-n suppression threshold, intervention tier cut-scores,
   pool-vs-per-instrument for multi-instrument mastery, which subjects count as
   "math", canonical NJ student number, `grade_level_tested` prior-grade
   behavior. These are **left out of the files** until instructional leadership
   ratifies them (see Section 7); the protocol flags and logs them meanwhile.
3. **Session protocol and hygiene — the orchestrator's content.** Calibration
   first, force-refresh `meta`, explicit `response_type`, confidence and
   inference flagging, the PII gate.

## 5. File 1 — Orchestrator

### 5.1 Standing protocol

A hard, ordered checklist the model runs at the start of and throughout every
session:

1. **Calibration first (hard gate).** Before any participant query — regardless
   of how urgent or complex the opening request is — run a calibration check:
   network ADA for the most recent week-end record
   (`student_attendance_view.avg_daily_attendance`, `is_week_end_record=true`,
   most recent `dates_school_week_start_date`), confirm connectivity and data
   currency, and sanity-check against a known value. Note that an end-of-year
   ADA drop-off is an expected seasonal artifact, not a data problem.
2. **Force-refresh `meta` at session start.** The cached catalog can be stale; a
   stale catalog produced a confident-but-wrong "unanswerable" in one session.
   If a needed field appears missing, refresh before concluding it is
   unavailable.
3. **Filter `response_type` explicitly** on every assessment query; never rely
   on the silent default blend.
4. **State confidence and flag every inference.** Give a High/Medium/Low
   confidence and explicitly list every interpretation or default chosen.
   Surface these for human confirmation before any external use.
5. **PII gate.** Any request for an identified student roster (names or IDs plus
   performance or IEP status) is held pending explicit permission and a
   legitimate need. Never write student identifiers to the log or chat;
   authorized identified deliverables go only to the output file, never the
   persistent log.
6. **Flag-don't-invent** for undecided defaults (Section 3): if a provisional
   choice is unavoidable to proceed, label it provisional and log it as an open
   decision.

### 5.2 Routing

Given a question, determine the assessment family and consult the matching
section of the assessment reference:

- Region hint: NJ regions are Newark, Camden, Paterson; FL region is Miami.
- Assessment hint: QA / MQQ / CRQ implies internal (Illuminate); NJSLA / NJGPA
  implies NJ state; FAST / EOC implies FL state.
- If the family is ambiguous, ask before querying.

### 5.3 Session-log template

The generalized form of the schema the four logs already share, so each
director's session produces a consistent, self-documenting log:

- **Header:** date, session number, participants, cubes in scope, known issues
  carried in, calibration result (match/mismatch with context).
- **Per-query block:** user asked; Cube views/measures used; response
  complexity; confidence; trip flag (+ description); inference flags (+ list);
  missing context; out-of-scope; outcome; notes.
- **Session patterns:** recurring question types; recurring trips; recurring
  inferences; low-confidence responses; out-of-scope; questions that belong in
  dashboards; questions that should be custom skills.
- **Fix backlog table:** number; issue; type (`trip` | `inference-gap` |
  `data-quality` | `scope-boundary`); first seen; priority; status.
- **Handoff:** prioritized trips; prioritized inference gaps; custom-skill
  candidates; dashboard candidates; low-confidence responses to review;
  out-of-scope; open questions for the model owner; recommended fixes.
- **Guardrail note:** confirm no PII was written to the log.

## 6. File 2 — Assessment reference

Scope expanded after initial drafting to also cover the three vendor normed
diagnostics used across regions — i-Ready, DIBELS, and STAR — each as its own
reference section alongside internal (Illuminate), NJ state, and FL state
(§6.2–6.4). The reference file carries these sections; conventions specific to
each vendor tool follow the same settled-mechanics-only rule as the rest of
Section 6.

### 6.1 Shared conventions (settled mechanics)

- **`response_type`** values are `overall`, `standard`, `group`, `null`
  (singular `standard`/`group`, not the older `standards`/`groups`). Not
  additive across types. Default to `overall` unless a standard- or group-level
  breakdown is explicitly requested.
- **Grain.** `count_scores` is additive and resilient (100% success across the
  logged sessions). `count_students` is a distinct count and is heavy and
  fragile at standard grain (timeouts and an intermittent location-US 400 on the
  `dim_student_enrollments` dependency); prefer `count_scores` as the fallback
  at fine grain. (Which measure is the _default_ for count/share questions is an
  open decision — flag it.)
- **Performance bands.** Use the numeric `performance_band_label_number`, never
  the label text. Band 1 = "Far Below" / band 2 = "Below" is confirmed against
  the live label set (see Section 9), because `proficiency_level` label strings
  are inconsistent (a bucket-1 defect).
- **Subject fields.** `discipline` is the course/section subject crosswalk
  (value `Math`); `academic_subject` is the tested subject (value `Mathematics`,
  full word). They answer different questions.
- **Enrollment resolution.** Filter `enrollment_resolution = subject_section`
  for course/section-level rollups; `homeroom` rows also exist.
- **Teacher attribution.** Lead-teacher fields are in the schema as of
  2026-07-24 (`staff_lead_teacher_full_name`, `lead_teacher_staff_key`, aliased
  onto the assessment view from `student_section_enrollments`). Requires the
  `student_section_enrollments_view` to be present — force-refresh `meta` if it
  is not.
- **Domain rollup.** `response_type_root_description` is the CCSS domain rollup;
  it is reliable for CCSS-aligned content and **unreliable for FL
  state-aligned** standards.

### 6.2 Internal (Illuminate)

- Module types `QA` / `MQQ` / `CRQ` (`module_type`); `module_code` such as
  `QA3`. The internal `assessment_type` enum value is `illuminate`, confirmed
  against the live connector (see Section 9).
- Pooling QA/MQQ/CRQ mixes instruments of differing difficulty (CRQ was ~60% of
  one region's MS math records) — pooling vs per-instrument is an open decision.
- `response_type_root_description` (CCSS domain rollup) is reliable here.
- **Sanity-check watch-out:** internal "overall" mastery cut-scores may read
  much lower than state proficiency for the same students — the two scales are
  not directly comparable, so a wide gap is often a calibration artifact. Flag
  large internal-vs-state gaps for team review rather than treating them as
  findings; the internal mastery threshold is trusted from the field
  description, not independently verified.

### 6.3 NJ state

- `assessment_type` enum: `state_nj_njsla`, `state_nj_njsla_science`,
  `state_nj_njgpa`.
- `academic_year` is unreliable/null for some state slices — filter school year
  via a `date_taken` window until the crosswalk exists.
- Student identifier: for NJ the district ID is null; only
  `lea_student_identifier` is populated. `lea_student_identifier` (the KIPP SIS
  number) is the canonical NJ student identifier, confirmed — see Section 9.
- `response_type_root_description` (CCSS) is reliable for NJ.

### 6.4 FL state

- `assessment_type` enum: `state_fl_fast`, `state_fl_science`, `state_fl_eoc`.
- FAST windows are PM1 / PM2 / PM3 (`administration_period`); PM3 is typically
  spring.
- `academic_year` is **100% null for `state_fl_fast`** — the standard year
  filter does not work. Map the school year from the `date_taken` calendar year
  (e.g., PM3 in calendar 2026 = the 2025-26 school year).
- `is_mastery = True` matches Level 3+ for FAST (verified).
- "Florida region" resolves to `state = FL` / `region_name = Miami` (empirically
  all FL rows are Miami; flag, as no documented semantic link exists).
- `response_type_root_description` is **unreliable** for FL state-aligned
  standards — do not use it for FL domain rollups.

## 7. Explicitly out of scope

- **Undecided policy defaults** (minimum-n, tier cut-scores,
  pool-vs-per-instrument, subject scope, `grade_level_tested` prior-grade
  behavior). Not stated as rules; only referenced as "flag and log." Route to
  instructional leadership for ratification; ratified values get added later.
- **Upstream Cube-model fixes** (bucket 1). Separate `src/cube/` issues, not
  direction-file content.
- **claude.ai admin enablement** (custom-skill upload, code execution) and any
  future migration from project knowledge to a Skill. Noted, not built here.

## 8. Distribution and version-control loop

- Files live version-controlled in this repo at
  `src/cube/mcp/project_knowledge/` (decided by the data engineer — see Section
  9), and are synced into the shared claude.ai Project as project knowledge.
  This is **not** the MkDocs docs site (`docs/`) — the files are not rendered
  pages and there is no `mkdocs.yml` nav wiring for them.
- **Update loop:** a session log surfaces a trip, an inference gap, or an open
  decision, which becomes either a PR to a direction file (settled mechanics) or
  an issue against the Cube model (bucket-1 defects) or an item for leadership
  (bucket-2 policy). Ratified decisions flow back into the files.
- **When to split beyond two files:** only when (a) total project knowledge
  grows large enough that retrieval auto-activates and section
  cross-contamination hurts, or (b) the three assessment sections start changing
  independently often enough that a single file's diffs get noisy. Splitting a
  section into its own file later is a mechanical move.

## 9. Open questions and dependencies to resolve before publishing

1. **Exact repo home** for the two files: resolved. They live in a new
   directory, `src/cube/mcp/project_knowledge/`, decided by the data engineer —
   not the MkDocs docs site.
2. **Confirm the internal `assessment_type` enum value** for Illuminate:
   resolved. The internal value is `illuminate`. The granular state values
   (`state_nj_njsla`, `state_fl_fast`, `state_nj_njgpa`,
   `state_nj_njsla_science`, `state_fl_science`, `state_fl_eoc`) are the
   **real** `assessment_type` values, verified against the live connector. The
   schema's field description — which lists coarse `state_nj` / `state_fl` /
   `college` / `ap` — is stale; this is itself a bucket-1 defect to file (see
   item 5).
3. **Verify the performance-band number-to-abbreviation crosswalk** against the
   live label set before publishing (guards against the `proficiency_level`
   label defect): resolved and confirmed. Band 1 = "Far Below", band 2 =
   "Below". The rule is to use the integer `performance_band_label_number`,
   never the label text.
4. **Confirm the canonical NJ student identifier** (LEA is populated; district
   is null): resolved. `lea_student_identifier` is the canonical NJ identifier
   (the KIPP SIS number); `district_student_identifier` is null for NJ.
5. **File the bucket-1 `src/cube/` issues** (including the stale
   `assessment_type` description found in item 2) and **route the bucket-2
   policy decisions** to instructional leadership (parallel tracks, not blockers
   for drafting the files).

## 10. Success criteria

- Two files exist, version-controlled, matching Sections 5 and 6.
- Every statement in the assessment reference is a settled mechanic or a true
  field meaning; no undecided policy default appears as a rule.
- The orchestrator's protocol and log template reproduce the discipline the four
  source logs already demonstrate.
- A director can open the shared Project, ask an assessment question, and have
  Claude follow the protocol, route to the right section, apply the settled
  conventions, flag inferences, honor the PII gate, and produce a consistent
  session log.
