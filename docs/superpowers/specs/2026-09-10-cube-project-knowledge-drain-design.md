# Drain the assessment project knowledge into Cube descriptions and MCP docstrings

Design for #5236. Brainstormed 2026-09-10; every warehouse figure re-measured
against prod on 2026-09-22 and dated where it moved. Re-measure again before
each implementation PR. No figure in this document goes into a YAML description.

**What the 2026-09-22 pass found.** C1's first half shipped upstream — there is
no null `response_type` left anywhere — and chasing the other half turned up a
live correctness bug on `pct_proficient` that is wider than C1 described. That
left this spec as [#5501](https://github.com/TEAMSchools/teamster/issues/5501);
C1 shrinks to a description change and folds into PR 1, and PR 3 becomes the
partitioning work alone. Two reference facts about `response_type` and one about
`administration_period` are now wrong and are corrected below. C2's figures
drifted without changing its argument. C3 and C4 are unchanged.

**Revision, 2026-09-23 — C1 is closed and `count_scores` no longer exists.**
[#5508](https://github.com/TEAMSchools/teamster/pull/5508) fixed the
`pct_proficient` denominator and, in doing so, found that the naming problem
underneath it could not be left alone: the public `count_scores` counted every
row, including the `not_taken` placeholders, so the corrected rate and the
public count no longer reconciled. It ships three nested counts in place of one
— `count_assigned` (every row), `count_taken` (`response_type != 'not_taken'`)
and `count_scored` (`is_mastery IS NOT NULL`) — plus a `pct_taken` participation
rate that is meaningful only for Illuminate. Consequences for this spec, applied
below: C1 is closed rather than shrunk, and PR 1 inherits nothing from it; the
`response_type` corrections this document called for are shipped; and every
forward-looking mention of `count_scores` is repointed, while C1's own findings
keep the name because they are a dated record of what was measured before the
change. PR 1 reads the shipped descriptions before rewriting any of them.

**Revision, 2026-09-25 — one table per member, and #5508 is still open.** The
four placement tables and the `ai_context` routing table are replaced by
per-member drafts: for each Cube member, the reference text it absorbs and the
drafted `description:` and `ai_context:` values. Drafting the values moved four
facts:

- The lead-teacher name advice goes to the view's `ai_context`, not
  `staff_lead_teacher.full_name`. That cube `extends: staff`, so the member is
  shared with `staff_directory`.
- "A CCSS code's grade can differ from `grade_level_tested`" goes to the view's
  `ai_context`. The query is correct and the reading is at risk, which is sieve
  step 4; the old map had it on `response_type_code`.
- The `count_students` fallback lives only in that member's `ai_context`. The
  `load` docstring keeps the two mechanics that hold for every view.
- #5508 writes its own instructions into `description:` ("filter it explicitly",
  "filter assessment_type to illuminate"). PR 1 moves them to `ai_context`.

#5508 has not merged as of this date. Every "shipped in #5508" below means "on
#5508's branch", and PR 1 cannot start until it merges. A new section says how
Cube and dbt descriptions relate.

## Decision

The Claude + Cube working group runs on two markdown files uploaded by hand to a
claude.ai Project: `src/cube/mcp/project_knowledge/assessment-cube-reference.md`
(data-usage conventions for `student_assessment_scores_view`) and
`assessment-cube-orchestrator.md` (session protocol). The reference holds about
50 facts about how the view behaves. They reach the model only inside that
Project. Claude Code, other connectors, and the org-level skill this work is
heading toward query the same Cube MCP without them.

Move each fact to the one channel every surface reads, chosen by how narrow the
fact is:

| Fact is about                         | Destination                                                     |
| ------------------------------------- | --------------------------------------------------------------- |
| what one measure or dimension _is_    | that member's `description:` in the cube YAML                   |
| how to _use_ one measure or dimension | that member's `meta.ai_context:` in the cube YAML               |
| the whole view                        | the view `description:` in `student_assessment_scores_view.yml` |
| how to use the whole view             | the view's `meta.ai_context:`                                   |
| any view (query mechanics)            | the `load` or `meta` docstring in `src/cube/mcp/server.py`      |
| session process or unratified policy  | stays in the markdown, shaped for the later skill               |

Four documented workarounds become model changes instead of prose. Each ships in
its own PR with the text version merged first as a fallback, then removed.

Rules that hold across every PR:

- One home per fact. The PR that lands a fact in Cube deletes it from the
  markdown in the same change.
- No point-in-time numbers in YAML. Score volumes, percentages, and year ranges
  go stale silently; the reference's own standard-code figures already have.
  Descriptions say "about a third" or "the majority", or say how to measure it.
- Coverage facts (which region has which source in which years) are derivable
  live. The view description says coverage is uneven and how to check it; the
  specifics are deleted, not moved.
- Load-bearing guidance goes in tool docstrings, never `instructions=` (#4473).
- A dimension added to `proficiency_rollup` must be functionally dependent on
  one already there, or the partition count is re-verified on a branch staging
  deployment before merge.

## Why the channels are the right ones

Cube views inherit each included member's `description:` from its cube, and the
`meta` tool returns those descriptions per view. The `load` docstring already
carries the academic-year crosswalk for exactly this reason: `instructions=` is
dropped by the claude.ai connector and truncated in Claude Code, while tool
descriptions reach the model on every surface. Serving the reference file as an
MCP tool or resource was rejected: the model has to choose to call it, resources
do not reliably surface through claude.ai connectors, and it duplicates the
skill.

### `meta.ai_context` is a real channel, verified

An earlier draft of this spec said `meta.*` keys other than `folders` do not
reach the model. That is true of **rendering** — Cube Cloud's UI draws only
`folders` — and false of the **payload**, which is the path that matters here.

Measured 2026-09-22 against Cube 1.7.43 on the local dev server, with a
throwaway `meta.ai_context` and a throwaway arbitrary key added to one view and
one cube measure, then reverted:

| Placement                           | In REST `/meta` | Via our `meta` tool          |
| ----------------------------------- | --------------- | ---------------------------- |
| `meta.ai_context` on the view       | yes             | yes                          |
| `meta.ai_context` on a cube measure | yes             | yes, inherited onto the view |
| an arbitrary `meta.<other>` key     | yes             | yes                          |

Three consequences:

- **Member-level `meta` on a cube is inherited by the view member**, alongside
  `aliasMember`. So `ai_context` uses this spec's existing placement pattern
  unchanged: edit the cube YAML member, the view picks it up. No new file and no
  new routing rule.
- **Our MCP server does no field filtering.** `meta` returns each cube dict
  verbatim (`src/cube/mcp/server.py`), which is why "not rendered by Cube Cloud"
  and Cube's own `ai_context` documentation are both correct — one is about
  display, ours is about passthrough.
- **`ai_context` is not privileged on our path.** It arrives as one more JSON
  key beside `description`. Cube Cloud's own AI agent treats it as agent-only;
  our server does not, and nothing in this spec makes it do so. The gain is
  separation — query guidance stops competing for room in a string that analysts
  read as a tooltip — not a channel the model weights more heavily.

Cube's constraints: views and members only, never cube level; 2,000 characters,
silently truncated past that.

### The authoring rule changes with it

`.claude/rules/cube-authoring.md` currently carries the belief this section
corrects:

> **`meta.folders` is the only Cube-rendered `meta.*` key.** Put guidance in
> `description:`, not `meta.usage` / `meta.synonyms` / etc. — those land in
> `/v1/meta` but Cube Cloud and the chat agent don't read them.

That rule predates Cube documenting `ai_context`, and leaving it would tell the
next author to undo this work. It ships in PR 1, alongside the descriptions it
governs — not as a follow-up, because the moment PR 1 merges the rule is wrong
about the code in the same commit.

The replacement says three things:

- `meta.folders` is the only key Cube Cloud **renders**. That part was right and
  stays.
- Every `meta.*` key reaches the model, because our MCP server returns each
  cube's `/meta` entry unchanged. `ai_context` is the one to use, because Cube
  documents it and Cube Cloud's own agent reads it; do not invent other keys.
- Which channel takes what: `description:` for what a member is, because
  analysts read it as a tooltip; `meta.ai_context:` for how to use it, capped at
  2,000 characters and silently truncated past that.

It also drops the `meta.usage` / `meta.synonyms` examples. Naming keys nobody
should use invites someone to use them, and neither appears anywhere in the
model.

### Cube descriptions and dbt descriptions are separate strings

A column of `fct_assessment_scores_enrollment_scoped` has two descriptions: the
dbt one in its properties YAML, and the Cube one on the cube member that reads
it. Nothing copies one into the other. The Cube YAML does not read the dbt
manifest, and kipptaf sets no `persist_docs`, so dbt text does not reach
BigQuery column descriptions either.

| Reads it                                              | dbt `description:` | Cube `description:` | Cube `meta.ai_context:` |
| ----------------------------------------------------- | ------------------ | ------------------- | ----------------------- |
| the model, through our Cube MCP `meta` tool           | no                 | yes                 | yes                     |
| an analyst in Cube Cloud                              | no                 | yes                 | no                      |
| an engineer in dbt docs or through the dbt MCP server | yes                | no                  | no                      |

The two have already drifted. On `response_type`, dbt lists `not_taken` and Cube
still says "overall, strand, standard. Null for state". On `response_type_code`,
dbt states which rows carry the code and Cube says only "Null for state". The
model reads the stale copy.

This spec edits the Cube strings only. `ai_context` has no dbt equivalent and
none is added. Whether PR 1 also corrects a dbt description it finds wrong is an
open question for review; copying Cube text into dbt wholesale is not proposed,
because two copies drift the way these two already have.

## Placement map

Every fact in the reference file, its destination, and what happens to the
markdown. "Present" means the shipped description already says it and the
markdown line is simply deleted.

### How each fact is placed

The tables below record ~50 decisions. This is the procedure that produced them,
written down so PR 1 does not re-adjudicate each one by taste, and so a fact
added later lands in the same place. It is a sieve, in the same shape as the
column procedure in `.claude/rules/ferpa-pii.md`: **work down the list, stop at
the first match.**

1. **Is it a point-in-time number?** Score volumes, percentages, year ranges,
   the performance-band cut-point table. Delete it, or restate it qualitatively.
   This runs first because it removes content regardless of which channel would
   otherwise take it.
2. **Is it derivable live?** Which region has which source in which years is a
   query. Delete the specifics; say that coverage is uneven and how to check.
3. **Does it hold for more than one view?** `notSet` versus `equals "null"`, and
   the de-duplicating dimension-only pull, are Cube mechanics. They go in the
   `load` or `meta` docstring.
4. **Is it about the answer rather than the query?** A cross-instrument gap
   being a calibration artifact, totals not reconciling to vendor reports, a
   missing current-year state result being a release lag. The query is correct
   and the reading is at risk. These go in the view's `ai_context`.
5. **Is it a definition?** What a value means, which values exist, what is null
   and when. That member's `description:`.
6. **Is it an instruction?** Do this, do not do that, use X instead. That
   member's `ai_context:`.
7. **Is it process or unratified policy?** Stays in the markdown.

Steps 5 and 6 are why most rows split rather than move. A bullet in the
reference file usually carries a definition and an instruction in one paragraph,
so it matches both and gets cut in two — the member keeps what it is and sheds
what to do about it.

**Tie-breaker when 5 and 6 both fit.** Ask who is harmed when the sentence is
missing. An analyst reading a tooltip who cannot tell what a value means →
`description:`. An agent building a query that will be wrong → `ai_context:`.
That resolves `count_students`: "exact distinct count" is the definition, while
"heavy at fine grain, fall back to a plain count" only ever helps the agent.

The procedure decides placement. Two other things hold it in place: the schema
test asserts one key phrase per moved fact keyed by member name, so a later edit
cannot silently drop one, and the eval is the empirical check — if the routing
is wrong, arm B does not beat arm A.

### Per-member drafts

One row per Cube member: the reference-file text that feeds it, and the drafted
value for each channel. Line numbers (`L23`) point into
`src/cube/mcp/project_knowledge/assessment-cube-reference.md` at this branch's
head. "Present" means the shipped text already says it and needs no change. PR 1
starts from these drafts; review may reword a value, but moving a sentence to
the other channel needs a sieve step that says why.

#### Scores cube (`student_assessment_scores`)

| Member                                   | Reference text                                                                                                                               | `description:`                                                                                                                                                                                                                                                                                                                               | `meta.ai_context:`                                                                                                                                                                                                                                                                                                                                                                    |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `response_type`                          | L23 "Values: `overall`, `standard`, `group`, `null` … Not additive across types. Default to `overall`"; L229                                 | Response-type breakdown. Never null; four values — overall (every source), group (Illuminate, i-Ready and DIBELS), standard and not_taken (Illuminate only). not_taken marks an assessment a student was assigned and never sat.                                                                                                             | Not additive across values. Filter it on every query; default to overall unless a standard or group breakdown is asked for.                                                                                                                                                                                                                                                           |
| `response_type_code`                     | L235 "Normalize standard codes before any standards-level rollup … never an average of the two reported percentages"                         | Breakdown identifier — the standard code on Illuminate standard rows, the domain on i-Ready group rows, the subtest on DIBELS group rows. Null on Illuminate group rows and on every overall and not_taken row. Some CCSS Math standards carry two spellings (8.EE.C.8.b and 8.EE.C.8b), and a small share of older rows have an empty code. | For a standards rollup, group on response_type_code_canonical once C2 ships; until then merge the two spellings and recompute pct_proficient from the counts, never by averaging the two percentages. For an Illuminate group-level cut, group on response_type_description — this code is null there, so keying on it drops every Illuminate group row and keeps i-Ready and DIBELS. |
| `response_type_description`              | none; from the 2026-09-23 measurement below                                                                                                  | Human-readable breakdown label. Populated on standard rows and every group row; null on overall and not_taken.                                                                                                                                                                                                                               | —                                                                                                                                                                                                                                                                                                                                                                                     |
| `response_type_root_description`         | L141 "the CCSS domain rollup — reliable for CCSS-aligned content, unreliable for FL state-aligned standards"; L440                           | CCSS domain the standard rolls up to. Populated on Illuminate standard rows only.                                                                                                                                                                                                                                                            | Unreliable for FL state-aligned standards. Null on every i-Ready, DIBELS, STAR and state row, so never group a cross-source query by it.                                                                                                                                                                                                                                              |
| `performance_band_label_number`          | L58 "Performance bands are Illuminate-only … It is not a 1–5 scale and not comparable across assessments"; L76–83; L231                      | Position of the score's band within its assessment's performance band set. Illuminate only; null for state and vendor rows. Band sets differ in cut points, in band count, and in which band starts mastery, so band 5 is not always the top.                                                                                                | Never compare or pool band numbers across assessments unless they share a band set. Within one set, prefer this number to proficiency_level text, which has many spellings per band.                                                                                                                                                                                                  |
| `proficiency_level`                      | L270 i-Ready scale; L351 DIBELS tiers; L373 STAR levels; L392 NJ; L433 FL; L344 "Tier-movement rates are not comparable to i-Ready's"        | Proficiency label; the vocabulary is per source. i-Ready: five placement levels, 3 or More Grade Levels Below through Mid or Above Grade Level. DIBELS: Well Below, Below, At and Above Benchmark. STAR: Level 1 to Level 5, null on a share of rows. State: the achievement level. Illuminate: the performance band label.                  | Tier-movement rates are not comparable across instruments — fewer, wider tiers mechanically raise the stayed-the-same rate. Compare each instrument with itself over time.                                                                                                                                                                                                            |
| `is_mastery`                             | L32 "the underlying per-score proficient flag"; L76 "The mastery bar ranges from 60% to 80% correct"; L291 Early On counts; L432 FL Level 3+ | Per-row proficient flag that pct_proficient is built from. The bar is per source — for i-Ready, Early On Grade Level and Mid or Above Grade Level; for FL, Level 3 and up; for Illuminate, set by each assessment's band set, so it is not one fixed standard across Illuminate.                                                             | i-Ready's bar counts Early On as proficient, looser than at-or-above grade level; for the stricter bar, filter proficiency_level directly. An Illuminate rate mixes assessments with different bars, so say which assessments it covers.                                                                                                                                              |
| `scale_score`                            | L308 "scale scores do not normalize across grade bands"                                                                                      | Scale score achieved. Null for Illuminate (percent-correct) rows. Scales differ by source, and within i-Ready the scale compresses at higher grades.                                                                                                                                                                                         | Report a scale-score change within one grade band, never pooled across ES and MS. i-Ready's growth norms are not in this view; do not label a computed delta with the vendor's growth-measure name.                                                                                                                                                                                   |
| `enrollment_resolution`                  | L115 "filter `enrollment_resolution = subject_section`"                                                                                      | How the section enrollment was resolved — subject_section or homeroom. (Shipped text, minus its instruction.)                                                                                                                                                                                                                                | Filter to subject_section for course- and section-level rollups.                                                                                                                                                                                                                                                                                                                      |
| `date_taken`                             | L120–128                                                                                                                                     | Present                                                                                                                                                                                                                                                                                                                                      | —                                                                                                                                                                                                                                                                                                                                                                                     |
| `count_students`                         | L48 "`count_students` … is heavier and historically fragile at fine (standard) grain"                                                        | Present                                                                                                                                                                                                                                                                                                                                      | Heavier than the plain counts, and has timed out at standard grain; count_taken is the reliable fallback there.                                                                                                                                                                                                                                                                       |
| `pct_proficient` and the counts          | L32, L48                                                                                                                                     | #5508's text, minus the instructions in the next column                                                                                                                                                                                                                                                                                      | #5508 writes these instructions into `description:`; PR 1 moves them. pct_proficient: pair it with count_scored, the n it rests on, and never multiply it by count_assigned. pct_taken: filter assessment_type to illuminate before reporting it. count_scored: report it alongside pct_proficient whenever the rate carries weight.                                                  |
| `avg_scale_score`, `avg_percent_correct` | L32 "scope-bound — meaningful only within one source/subject/grade"                                                                          | Present. The leading `Grain:` clause stays in `description:` under the #4476 convention: a pooled average misleads an analyst reading the tooltip as much as it misleads an agent.                                                                                                                                                           | —                                                                                                                                                                                                                                                                                                                                                                                     |
| `pct_proficient_formative`               | L222 "It filters `module_type IN ('QA', 'MQQ', 'CRQ')`, so it silently excludes `TP`, `UA`, `ET`, and `WPP`"                                 | Proficiency rate across the QA, MQQ and CRQ module types only; excludes TP, UA, ET and WPP. CRQ is also available alone as pct_proficient_crq.                                                                                                                                                                                               | Not "all internal checkpoints". For that, build the rollup from the intended module types and flag the pooling choice as an open decision.                                                                                                                                                                                                                                            |

#### Assessments cube (`student_assessments`)

| Member                   | Reference text                                                                                                      | `description:`                                                                                                                                                                                                                                                                                                              | `meta.ai_context:`                                                                                                                                                                                                                                                           |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `assessment_type`        | L14 value list; L20 "Treat this list as current, not closed"; L397 "NJSLA and NJGPA are computer-adaptive"          | Present value list, plus: From spring 2026, NJSLA and NJGPA are computer-adaptive, and no field separates adaptive from fixed-form scores. NJSLA Science did not change.                                                                                                                                                    | Flag any NJSLA or NJGPA comparison that crosses spring 2026 as possibly comparing two scales; never present that trend as settled.                                                                                                                                           |
| `is_internal_assessment` | L14 "`is_internal_assessment` is TRUE only for Illuminate … i-Ready, DIBELS, and STAR are FALSE"                    | TRUE for KIPP-authored Illuminate interims; FALSE for every other source — state, college, AP, and the i-Ready, DIBELS and STAR diagnostics KIPP administers itself.                                                                                                                                                        | Do not select a source with this flag; it groups vendor diagnostics with state tests. Filter assessment_type.                                                                                                                                                                |
| `module_type`            | L184 "there are seven, not three … What `TP`, `UA`, `ET`, and `WPP` stand for is an open question"                  | Module type for Illuminate assessments. An open list — QA, MQQ, CRQ, TP, UA, ET, WPP and older types; what TP, UA, ET and WPP stand for is not documented. Null for every other source.                                                                                                                                     | Do not expand TP, UA, ET or WPP.                                                                                                                                                                                                                                             |
| `module_code`            | L203 "varies by subject, grade, AND region"; L211 "not in chronological order by name"; L215 "not a subject filter" | Present                                                                                                                                                                                                                                                                                                                     | Not a subject filter: one code spans every subject in its round, so pair it with academic_subject. Which codes exist varies by subject, grade and region — check the exact slice before pooling across checkpoints. Names are not chronological; order by median date_taken. |
| `academic_subject`       | L85 "`academic_subject` values are source-dependent"; L89 "Illuminate has no `English Language Arts` value"; L99    | Subject tested. Values depend on the source: state and vendor use plain labels (English Language Arts, Mathematics); Illuminate uses course-level names and has no English Language Arts — its ELA equivalent is Text Study, alongside Writing, English 100–400, CCR and AP courses. Distinct from the course's discipline. | Check this member's values for the source before filtering; a wrong label returns zero rows with no error.                                                                                                                                                                   |
| `grade_level_tested`     | L102 "Three different grade fields"; L108 "null on all 302,907 i-Ready, DIBELS, and STAR rows"                      | Grade the assessment targets. Populated for Illuminate and state; null for every i-Ready, DIBELS, STAR and college row.                                                                                                                                                                                                     | For a vendor diagnostic, filter grade_level instead — this one returns zero rows with no error. Where both are populated they answer different questions; say which you used.                                                                                                |

#### Administrations cube (`student_assessment_administrations`)

| Member                  | Reference text                                                                                                                                                                         | `description:`                                                                                                                                                                                                                                                                                                                                                                                                                        | `meta.ai_context:`                                                                                                                                                                                                                                                                                                     |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `administration_period` | L129 "vocabulary differs by source"; L277 `Outside Round`; L285 "most recent diagnostic"; L297 "EOY is administered _after_ NJSLA"; L356; L378; L396; L409 Fall NJGPA; L437 FL windows | Window within the academic year; the vocabulary is per source. i-Ready and DIBELS: BOY, MOY, EOY, plus Outside Round for i-Ready sittings outside the three windows. STAR: Fall, Winter, Spring. NJGPA: Fall (the routine retake window) and Spring. NJSLA: Spring. FL: PM1 to PM3. College: the College Board round. Null for Illuminate and AP. Vendor EOY falls after spring state testing; MOY is the last named round before it. | Only meaningful with assessment_type scoped. A BOY/MOY/EOY filter drops Outside Round, so say which windows you used. "Most recent diagnostic" is the latest named round in the latest academic_year_label, not the max date_taken. An EOY-versus-state comparison in one year is concurrent, not predictive; use MOY. |
| `source_assessment_id`  | L247 "a distinct count of `source_assessment_id`"                                                                                                                                      | Present                                                                                                                                                                                                                                                                                                                                                                                                                               | "How many times was this assessed" is a distinct count of this, not a row count. A standard resting on one assessment is a thin base for a trend. C3 replaces this with count_assessments.                                                                                                                             |

#### Shared cubes

| Member                   | Reference text                                                            | `description:`                                                                                                                                     | `meta.ai_context:`                                                              |
| ------------------------ | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `locations.grade_band`   | L102 "`grade_band` is a school-level attribute … not a per-student grade" | Grade band the school serves (ES, MS, HS) — a school attribute, not a student's grade.                                                             | A grade_band filter is a school filter. For a student's grade, use grade_level. |
| `courses.discipline`     | L85 "`discipline` is the _course_ subject"                                | Present                                                                                                                                            | —                                                                               |
| `courses.is_foundations` | L159 "the only intervention signal on the view"                           | TRUE when the section is a Foundations (intervention) course, per the course-subject crosswalk. The only intervention signal on the student views. | Treat it as course enrollment, not a record of services delivered.              |
| `students` identifiers   | L421                                                                      | Present on `lea_student_identifier`, `district_student_identifier` and `state_student_identifier`                                                  | —                                                                               |
| `staff.full_name`        | L165 "Resolve staff names against `staff_directory` before filtering"     | Present                                                                                                                                            | — the advice goes to the view instead; see below                                |

`staff_lead_teacher` has no members of its own: it `extends: staff`. An
`ai_context` on `staff.full_name` would therefore also reach `staff_directory`,
where "resolve against `staff_directory` first" is circular. The fact goes to
the assessment view's `ai_context`.

#### The view (`student_assessment_scores_view`)

`description:` is present — it says what the view holds and which date each
source's year comes from. The `ai_context:` draft, about 1,200 characters
against the 2,000 cap:

> Enrollment-scoped: a score appears only if it resolves to a section
> enrollment, so totals will not reconcile to vendor or state reports, and
> i-Ready Outside Round sittings lose the most — treat those counts as a floor.
> Coverage is uneven by region, source and year, and a source's first year can
> be partial; check volume by region and year before calling a narrow result a
> failure or trending across a boundary. A gap between two instruments on the
> same students is a calibration difference until shown otherwise: report both
> rates side by side and flag it rather than presenting an achievement gap.
> There is no growth measure, so any growth figure is analyst-built — say so.
> Students can sit a vendor diagnostic more than once in a window; keep the most
> recent date_taken per student per window before any student-level count. A
> missing current-year state result is a release lag, not a defect. Query this
> view, not upstream vendor tables, which carry re-pull duplicates. A CCSS
> code's own grade can differ from grade_level_tested; that is spiral review,
> not an error. Lead-teacher names are stored Last, First; resolve a name
> against staff_directory before filtering, since a zero-row result is not proof
> the teacher has no students.

Sources: L39 and L257 (calibration), L136 (growth), L145 and L281 (enrollment
scope), L152, L358 and L381 (coverage), L317 (sittings), L329 (upstream), L414
(release lag), L252 (CCSS grade, sieve step 4), L165 (staff names).

#### Everything that does not land on a member

| Reference text                                                                                                   | Goes to                                         | Sieve step |
| ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | ---------- |
| L28 "filter with operator `notSet` … `equals "null"` matches the literal string"                                 | `load` docstring                                | 3          |
| L54 "A dimension-only pull silently de-duplicates"                                                               | `load` docstring                                | 3          |
| L118 "force-refresh `meta` if the lead-teacher fields appear to be missing"                                      | `meta` docstring                                | 3          |
| L66–74 band-set table; L187–201 module-type volumes                                                              | deleted                                         | 1          |
| L147 regional loss rates; L298 median test dates; L322 repeat-sitting rates; L400 window dates; L411 Fall counts | deleted; the qualitative claim stays in its row | 1          |
| L152 Paterson specifics; L304 i-Ready regions; L358 DIBELS start year; L381 STAR start year; L439 FL is Miami    | deleted; the view says coverage is uneven       | 2          |
| L269, L350, L372, L391, L431 "`response_type = null`"                                                            | deleted; wrong since 2026-09-22                 | —          |
| L95 "At K-2, `Text Study` is the _only_ ELA-equivalent subject present"                                          | stays; evidence for the open ELA decision       | 7          |
| L170 open decisions; L328 which sitting is authoritative; L407 adaptive cut-score reset                          | stays                                           | 7          |
| L333, L362, L384 provenance notes                                                                                | stays                                           | 7          |

### Stays in the markdown

The standing protocol, calibration gate, session log and Drive filing, PII
delivery rules, the open-decision list, and the modeling and deliverables rules.
The routing section shrinks to the assessment-family hints and a pointer to
`meta`, since the per-family sections it routes to no longer exist.

## YAML description changes

Each change is a correction or an addition, worded qualitatively. The ones that
correct shipped text:

- `module_type`: currently "e.g., QA, CR". Becomes an open list of the values in
  use — 28 distinct values on Illuminate as of 2026-09-22, and null for every
  other source — with a note that `pct_proficient_formative` covers only `QA`,
  `MQQ`, `CRQ`.
- `is_internal_assessment`: currently "FALSE for state and college". Adds the
  vendors and points at `assessment_type` for source selection.
- `grade_level_tested`: currently "Null for college-entrance". Adds that it is
  null for every vendor row and that `grade_level` is the field to use there.
- `administration_period`: currently omits vendor values. Adds `BOY`, `MOY`,
  `EOY` for i-Ready and DIBELS, `Outside Round` for i-Ready **only** (DIBELS has
  no such value — verified 2026-09-22), `Fall`, `Winter`, `Spring` for STAR,
  `PM1` to `PM3` for FL, `Fall` and `Spring` for NJGPA, `Spring` for NJSLA, and
  that the vocabulary is only meaningful with `assessment_type` scoped. It is
  null for every Illuminate row.
- `response_type`: currently "overall, strand, standard". Becomes `overall`,
  `standard`, `group`, `not_taken` — the null case is gone as of 2026-09-22, and
  `not_taken` marks an assigned-but-unsat Illuminate assessment. Says that
  `standard` is Illuminate-only but `group` is not: i-Ready and DIBELS populate
  it too. #5508 lands this one ahead of PR 1, alongside the #5501 denominator
  fix — check the shipped text before rewriting it.
- `response_type_code`, `response_type_description` and
  `response_type_root_description`: each currently says only "Null for state".
  True, and incomplete enough to mislead — each is null across a different and
  much larger slice. Measured 2026-09-23:

  | Member                           | Populated on                                    | Null on                                                       |
  | -------------------------------- | ----------------------------------------------- | ------------------------------------------------------------- |
  | `response_type_code`             | `standard`, plus `group` for i-Ready and DIBELS | every Illuminate `group` row, and all `overall` / `not_taken` |
  | `response_type_description`      | `standard` and every `group`                    | all `overall` / `not_taken`                                   |
  | `response_type_root_description` | Illuminate `standard` only                      | every i-Ready, DIBELS, STAR and state row                     |

  Each description states the slice it is populated on, in those terms. The
  load-bearing one is `response_type_code`: it is null on all 2,797,958
  Illuminate `group` rows while `response_type_description` is populated on
  them, so a standards-cluster cut keyed on the code silently drops every
  Illuminate group row and keeps the i-Ready and DIBELS ones. That asymmetry
  goes in `ai_context` on `response_type_code`, since it is advice about which
  member to group by rather than a definition.

- `performance_band_label_number`: currently "Null for state". Adds Illuminate
  only, and not comparable across band sets.
- `academic_subject`: currently lists "English Language Arts" as an example.
  Adds that values are source-dependent and Illuminate's ELA-equivalent is
  `Text Study`.
- The count measures and `pct_proficient`: **shipped in #5508, nothing left for
  PR 1.** `count_scores` was split into `count_assigned` (every row),
  `count_taken` (`response_type != 'not_taken'`) and `count_scored`
  (`is_mastery IS NOT NULL`), a `pct_taken` participation rate was added, and
  all four carry the descriptions this row called for. Read the shipped text
  before touching them.

A test in `tests/cube/test_cube_schema.py` loads the YAML and asserts one key
phrase per moved fact, keyed by member name, so a later edit cannot drop one
silently. Cube Cloud validates the model on the branch staging deployment before
merge.

## Server docstring changes

`load` gains two paragraphs after the academic-year crosswalk:

- Filter operators for NULL: `set` and `notSet`; `equals "null"` matches the
  literal string and returns zero rows.
- Grain: a query with no measure de-duplicates identical rows, so add a count or
  the primary key to see row counts. The `count_students` fallback is that
  member's `ai_context`, not this docstring.

`meta` gains one sentence: refresh before concluding a member is missing.

A test in `tests/cube/test_mcp_server.py` asserts the anchor phrases, the same
way the crosswalk is anchored today. Redeploy and connector refresh follow the
existing procedure in `src/cube/mcp/CLAUDE.md`.

## Model changes

Each is its own PR. The text fallback from PR 1 is removed in the same PR that
lands the model change.

### C1. Unscored placeholder rows

**Half of this shipped upstream between 10 and 22 September. Re-measured
2026-09-22; the finding below replaces the original.**

What changed. There is no longer a null `response_type` anywhere in the fact —
zero rows, every source. State and vendor now carry `'overall'`, which is
exactly what C1's first half proposed, so that part is done and needs no PR. The
unscored placeholder rows were not dropped, though. They were relabelled to a
new `response_type` value, `'not_taken'`.

| `response_type` | Rows      | Fully unscored |
| --------------- | --------- | -------------- |
| `standard`      | 7,992,496 | 0              |
| `group`         | 4,270,447 | 5,562          |
| `overall`       | 1,854,540 | 0              |
| `not_taken`     | 928,765   | 928,765        |

Finding. All 928,765 `not_taken` rows are Illuminate, and every one has a null
`is_mastery`, `percent_correct` and `scale_score` — a student was assigned an
assessment and no responses joined. `count_scores` still counts them, so an
Illuminate `pct_proficient` computed without a `response_type` filter still has
an inflated denominator. **The problem C1 exists to fix is intact; only its
shape changed.**

Three knock-on corrections, all of which land in PR 1 rather than here:

- The reference's `response_type` value list (`overall`, `standard`, `group`,
  `null`) is wrong. The values are `overall`, `standard`, `group`, `not_taken`.
- The reference's "every other source is `response_type = null`" is wrong, and
  so is "only Illuminate populates `standard` / `group`". Only `standard` is
  Illuminate-only. i-Ready contributes 1,208,458 `group` rows and DIBELS
  269,820.
- `notSet` versus `equals "null"` is still a real Cube trap and stays in the
  `load` docstring, but it no longer has anything to do with `response_type`.

Chosen — **the denominator fix left this spec. It is
[#5501](https://github.com/TEAMSchools/teamster/issues/5501).**

Chasing C1 down found a bigger problem than C1 describes. `pct_proficient`
divides `_sum_proficient` by `count_scores`, a bare row count, so every row with
a null `is_mastery` sits in the denominator and can never reach the numerator.
That is 936,836 rows, and `not_taken` is only 99.1% of them:

| `response_type` | Rows    | Sources          |
| --------------- | ------- | ---------------- |
| `not_taken`     | 928,765 | illuminate       |
| `group`         | 5,562   | dibels           |
| `overall`       | 2,509   | illuminate, star |

So the reported rate is wrong on three of the four sources — STAR by 16.34
points, Illuminate by 3.51, DIBELS by 0.81 — and **no `response_type` filter
fixes it**, because 2,509 of the bad rows are `overall`, the value the reference
tells people to default to. Dropping rows does not fix it either.

That is a live correctness bug on a published metric, not a documentation-drain
task, so it moved to its own issue with the worked fix attached. It is Cube-only
and needs no dbt change.

**C1 is closed by [#5508](https://github.com/TEAMSchools/teamster/pull/5508),
with nothing left for PR 1.** What remained after the denominator split out was
saying, on the count measures and `pct_proficient`, that a score row can carry
no proficiency verdict, and on `response_type`, what `not_taken` means. #5508
ships all of it, plus the three-way count split that the naming problem turned
out to require. PR 1 should read the shipped descriptions rather than write
these.

The rows themselves stay. `not_taken` is a deliberate, documented signal that a
student was assigned an assessment and never sat it, pinned by an
`accepted_values` test in `fct_assessment_scores_enrollment_scoped.yml`, and
nothing else in the warehouse carries it at this grain.

**Partition the fact in this same PR.**
`fct_assessment_scores_enrollment_scoped` carries `assessment_date_key` as a
DATE column and has no time partitioning, no range partitioning and no
clustering — verified 2026-09-22 against the prod table, 15,046,358 rows and
4.78 GiB. PR 3 rebuilds this table anyway, so a `partition_by` costs one rebuild
here instead of two later. Note the limit from
`.claude/rules/cube-authoring.md`: a date filter routed through the `dates` join
compiles to a predicate on `dim_dates` and prunes nothing, so partitioning pays
off only for queries that filter a fact-side time dimension. Decide the
partitioning column and whether the view needs a fact-side date member when PR 3
is planned.

Alternatives are recorded on #5501, which also carries why dropping rows and
filtering `response_type` were both rejected.

### C2. Canonical standard code

Finding. Re-measured 2026-09-22: `response_type = 'standard'` has 1,840 distinct
codes, and both the blunt strip of all non-alphanumerics and the narrow rule
`REGEXP_REPLACE(code, r'\.([a-z])$', r'\1')` collapse them to 1,785. (On 10
September the same pair of figures was 1,791 and 1,736; the gap of 55 merged
groups is unchanged.) Every one of the 55 merged groups is a pair differing only
by a dot before the trailing sub-standard letter, such as
`CCSS.Math.Content.8.EE.C.8.b` and `CCSS.Math.Content.8.EE.C.8b`. Descriptions
are identical apart from whitespace in 4 pairs. No group has 3 members and no
group mixes two standards. The root cause is upstream: Illuminate holds two
mirror copies of the CCSS Math standards document, category ids 39 to 61 with
the dot and 64 to 92 without, 110 standard ids for the 55 pairs, none hidden.
Numeric-only codes such as `6.2.1` exist, so the blunt strip carries a collision
risk the narrow rule does not.

Chosen. Add `response_type_code_canonical` to
`fct_assessment_scores_enrollment_scoped` with the narrow rule, raw code kept.
Expose it on the scores cube and the view, and add it to `proficiency_rollup`,
where it is functionally dependent on `response_type_code` and adds no rows.
Because `pct_proficient` is built from additive primitives, grouping on the
canonical code makes Cube do the count-weighted recompute the reference asks the
analyst to do by hand. The `response_type_code` description names the two
spellings and points at the canonical dimension.

**The rollup this depends on is barely serving.** Measured 2026-09-22 over the
prior 7 days, from `JOBS_BY_PROJECT` for the Cube Cloud service account:

| What                                            | Measured                   |
| ----------------------------------------------- | -------------------------- |
| `proficiency_rollup` partition builds           | 242 jobs, 396.9 GiB billed |
| Queries that read the fact directly (a miss)    | 264                        |
| Of those, referencing a member the rollup lacks | 166 (63%)                  |

The rollup carries 18 dimensions and 2 measures. Six members that real queries
group or filter on are absent: `location_name`, `proficiency_level`,
`is_mastery`, `assessment_type`, `scale_score`, `percent_correct`. A rollup
serves a query only when every referenced member is in it, so each of those 166
falls through to the 15.0M-row fact. The remaining 97 misses are not explained
by that probe and were not characterized; `count_students` is not the cause,
since no miss used a distinct count.

Two things follow for this spec, neither of which kills C2:

- **C2's stated benefit is currently theoretical.** "Cube does the
  count-weighted recompute" requires queries to reach the rollup. Adding
  `response_type_code_canonical` to it is still right — the dimension is correct
  regardless, and it costs no rows — but it does not buy the speedup the
  rationale claims until the rollup's member list covers what people ask.
- **PR 4's validation guards an underused structure.** "Pre-agg partition count
  unchanged on branch staging" is still worth checking, and still cheap. It is
  not evidence that anything got faster.

Widening the rollup's member list is a separate change, out of scope here.
Re-measure both figures before PR 4 is planned; this is a 7-day window on a
system whose usage is still growing.

Not chosen here. Fixing the rollup or the Illuminate intermediate would merge
the pairs for `rpt_tableau__ddi_dashboard`, `rpt_tableau__power_standards`,
`rpt_tableau__assessment_dashboard`, and `rpt_gsheets__deanslist_mod_audit` too.
Two of those join the raw code to
`stg_google_sheets__assessments__standard_domains`, whose spelling was not
checked. File as a separate issue.

Alternatives. Cube-only dimension expression with the same rule: no rebuild,
grey against the transformation-lives-in-dbt rule. Text only: correct the rule
in the description and drop the hand recompute instruction.

Side finding for the same PR's description text: 2,260 standard-level rows from
2020 to 2023 carry an empty-string code. Not merged by either rule; noted on
`response_type_code` as "a small share of older rows have an empty code".

### C3. Assessment count

Finding. "How many times was this standard assessed" is a distinct count of
`source_assessment_id`, not a row count. Re-measured 2026-09-22 and unchanged:
per standard per year the distinct assessment count has quartiles 1, 1, 2, 3 and
a maximum of 52, across 6,729 standard-years, and 43.4% of standard-years rest
on one assessment. Distinct `assessment_administration_key` differs in 84.6% of
standard-years because that key includes region and administered date, so it
counts sittings.

Chosen. Add `count_assessments` to the scores cube: `count_distinct` on
`{student_assessment_administrations.source_assessment_id}`, public, exposed on
the view. Description states it counts distinct assessments, not sittings or
scored responses, and that a standard resting on one assessment is a thin base.
Cube only; no dbt change.

Alternative. Text only on `count_taken` and `source_assessment_id`.

### C4. Source family

Finding. `is_internal_assessment` is true only for `illuminate`. `iready`,
`dibels`, `star`, and every `state_*` type are false. `college` and `ap` carry
no rows on the view today.

Chosen. Add `assessment_family` to `dim_assessments`: `internal` for
`illuminate`, `vendor` for `iready`, `dibels`, `star`, `state` for `state_*`,
`college` and `ap` for the rest. Expose it on the assessments cube and the view,
add it to the `Assessment` folder. Not added to the rollup.

Alternatives. Cube-only `CASE` on `assessment_type`: no rebuild, same grey area
as C2's alternative. Text only: fix `is_internal_assessment` and list values by
family on `assessment_type`.

## Eval extension

`src/cube/mcp/eval` today measures one thing, the academic-year crosswalk, with
a hand-written `META_STUB`. This adds a second family without disturbing it.

- `prompts.yaml` gains family 4, assessment traps, each with the trap it must
  avoid: an i-Ready question by grade (must filter `grade_level`, not
  `grade_level_tested`); a "state scores only" question (must not use
  `equals "null"`); a "QA3 math" question (must pair `module_code` with a
  subject filter); a "vendor diagnostics" question (must not select on
  `is_internal_assessment`); an "all internal checkpoints" question (must not
  use `pct_proficient_formative` alone or must say what it excludes); a
  standards rollup question (must group on the canonical code once C2 lands); a
  "most recent diagnostic" question (must scope to a named round); a Paterson
  i-Ready question (must report coverage, not zero as a failure).
- `scorer.py` checks the captured `load` query for each trap, not the answer
  text, and reports a trap rate per arm with Wilson intervals as today.
- `arms.py` gains a loader that builds a `META_STUB` from the YAML under
  `src/cube/model/` for the assessment view, so arm B measures the working tree.
  Arm A reads `eval/fixtures/meta_pre_drain.json`, generated once from
  `origin/main` before PR 1 and committed. Both arms use the real `server.py`
  docstrings; arm A substitutes the pre-drain `load` paragraphs by anchor, the
  same mechanism the crosswalk arm uses.
- The runner stays hermetic per `eval/README.md`.

The eval runs after PR 2 and again after PR 6. Arm B must beat arm A on the trap
rate for the family, or the description text is revised before the markdown
deletion in that PR merges.

### Why family 4 stops at eight

Eight traps against ~50 facts looks like a sample. It is closer to the whole
set. A trap is a predicate over a captured query, so a fact can only become one
when the query alone proves the violation. The facts split three ways:

- **Malformed query — checkable.** `is_internal_assessment` used to select a
  source; `equals "null"` where `notSet` was meant; `module_code` with no
  subject filter; `avg_scale_score` with no `assessment_type` filter; a band
  number grouped with no band-set scope. These are family 4.
- **Correct query, misread answer — never checkable.** The calibration-artifact
  rule, totals not reconciling to vendor or state reports, a missing
  current-year state result being a release lag, uneven coverage, scale scores
  compressing at higher grades. Nothing in the query is wrong, so no predicate
  over query shape can fire. This is a permanent limit, not pending work — and
  it is why step 4 of the placement procedure routes these to prose.
- **Definitions — nothing to violate.** Value lists, FL's Level 3 mastery bar,
  `module_type`'s open list.

So the eval measures the checkable third and the descriptions carry the rest.
Adding traps past eight costs a written prompt and two arms of model-in-the-loop
runtime each, against a gate that already blocks PR 2 and PR 6; the predicate
was never the expensive part.

### Pointing the trap checks at production, deferred

`scorer.py` inspects the captured `load` query, not the answer text, so the same
predicate would run against a real logged query. That is deliberately **not** in
scope here, and the reason is narrower than "the recording spec does not exist
yet."

Measured 2026-09-22: every Cube query reaches BigQuery under one service
account, and the only job label is `cube_request_id`, a UUID — 369 jobs on the
assessment fact over 7 days, 227 distinct ids, no surface, user or application
field. An agent's query and a Superset dashboard refresh are indistinguishable,
so a trap **rate** computed from `JOBS_BY_PROJECT` would put every human
dashboard load in the denominator. Compiled SQL is also all that survives, not
the Cube query JSON, and the question that prompted it is nowhere.

What that leaves available today is the crude form: regex the compiled SQL for a
member reference and count. It answers whether a shape occurs in production, not
how often an agent falls into a trap. The C2 rollup measurement above used
exactly this technique, and its limits are the same.

The real dependency is therefore **attribution and question text**, which the
separate MCP-interaction recording spec provides — question, `query_json`,
`members_referenced`, outcome, `server_sha`. Once that lands, each trap becomes
a standing monitor instead of a pre-merge gate, which matters because the
success criterion above proves the descriptions work on eight written prompts,
not on what people actually ask or on whether they still work in November.

The only obligation this spec takes on is keeping the trap predicates importable
rather than inlined in the scorer's main loop.

## Project-knowledge trim

- Each PR deletes the facts it moved from `assessment-cube-reference.md`. After
  PR 6 the file holds only the section headers, the open-decision pointers, and
  a line under each family saying the field facts live in `meta`.
- `assessment-cube-orchestrator.md` loses the routing entries that point at
  deleted sections. Step 3 of the protocol changes from "filter `response_type`
  explicitly" to "confirm `response_type` from `meta`" once C1 lands.
- `README.md` in that folder gains a step: after each PR merges, re-upload the
  changed file to the Project. Its update loop says a field fact goes to the
  Cube YAML, a query mechanic goes to `server.py`, and only protocol or policy
  goes to these files.

## PR sequence and validation

| PR  | Scope                                                                                             | Validation                                                                                                                                                 |
| --- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | YAML descriptions, `ai_context` values, the `cube-authoring.md` rule, reference trim, schema test | `uv run pytest tests/cube/`; Cube Cloud branch staging validates the model                                                                                 |
| 2   | `load` and `meta` docstrings, eval family 4, pre-drain fixture                                    | `uv run pytest tests/cube/`; eval run, arm B beats arm A                                                                                                   |
| 3   | `partition_by` on `fct_assessment_scores_enrollment_scoped`                                       | `uv run dbt build --select fct_assessment_scores_enrollment_scoped+`; row counts before and after; dry-run bytes on a date-filtered query before and after |
| 4   | C2: canonical standard code                                                                       | dbt build; pre-agg partition count unchanged on branch staging                                                                                             |
| 5   | C3: `count_assessments`                                                                           | `uv run pytest tests/cube/`; branch staging query returns quartile-shaped counts                                                                           |
| 6   | C4: `assessment_family`                                                                           | `uv run dbt build --select dim_assessments+`; eval rerun                                                                                                   |

Each PR body carries the markdown lines it deleted, so a reviewer can see the
fact and its new wording side by side.

## Out of scope

- The upstream standards crosswalk (C2, not chosen). Separate issue.
- The org-level claude.ai skill. The trimmed markdown is shaped for it; the
  skill itself is later work.
- `pct_proficient_formative` semantics. Whether to widen it or add a
  module-coded rollup is a pooling decision on the open-policy list.
- Any change to `int_assessments__response_rollup` or the reports that read it.
