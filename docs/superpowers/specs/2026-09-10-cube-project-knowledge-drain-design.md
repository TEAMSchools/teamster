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
"heavy at fine grain, fall back to `count_scores`" only ever helps the agent.

The procedure decides placement. Two other things hold it in place: the schema
test asserts one key phrase per moved fact keyed by member name, so a later edit
cannot silently drop one, and the eval is the empirical check — if the routing
is wrong, arm B does not beat arm A.

### Shared conventions

| Fact                                                                                                                                                      | Destination                                                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| select a source with `assessment_type`, not `is_internal_assessment`; vendors are `false`                                                                 | `is_internal_assessment`, `assessment_type` (assessments cube); C4 adds `assessment_family`                     |
| `response_type` values, null sources, default `overall`, not additive                                                                                     | `response_type` (scores cube); C1 removes the null case                                                         |
| `notSet` vs `equals "null"`                                                                                                                               | `load` docstring                                                                                                |
| `pct_proficient` is the cross-source headline; `is_mastery` underlies it; scale and percent measures are scope-bound                                      | present on the measures; add the `is_mastery` sentence                                                          |
| a cross-instrument gap is a calibration artifact                                                                                                          | view description                                                                                                |
| `count_scores` additive and reliable; `count_students` heavy at fine grain                                                                                | `count_students` description plus `load` docstring fallback sentence                                            |
| a dimension-only pull de-duplicates                                                                                                                       | `load` docstring                                                                                                |
| bands are Illuminate-only; a band number is meaningful only inside its band set; mastery bar and band count differ by set                                 | `performance_band_label_number`, `proficiency_level` (scores cube); the band-set table is deleted               |
| `academic_subject` is source-dependent; Illuminate has no `English Language Arts`, uses `Text Study` and course names; `discipline` is the course subject | `academic_subject` (assessments cube), `discipline` (courses cube)                                              |
| three grade fields; `grade_band` is a school attribute; `grade_level_tested` null for every vendor row                                                    | `grade_band` (locations cube), `grade_level_tested` (assessments cube), `grade_level` (school enrollments cube) |
| `enrollment_resolution = subject_section` for section rollups; lead-teacher fields                                                                        | present on `enrollment_resolution`; teacher sentence to view description                                        |
| `academic_year` derivation differs by source; `date_taken` nullable                                                                                       | present on the view and `date_taken`                                                                            |
| `administration_period` vocabulary differs by source; null for Illuminate                                                                                 | `administration_period` (administrations cube)                                                                  |
| there is no growth measure; scale scores compress at higher grades                                                                                        | view description; `scale_score`                                                                                 |
| `response_type_root_description` unreliable for FL standards                                                                                              | `response_type_root_description`                                                                                |
| the view is enrollment-scoped; totals do not reconcile to vendor or state reports; `Outside Round` loses the most                                         | view description                                                                                                |
| region and source coverage is uneven                                                                                                                      | view description, qualitative; specifics deleted                                                                |
| `is_foundations` is the only intervention signal; course enrollment, not services                                                                         | `is_foundations` (courses cube)                                                                                 |
| staff names are `Last, First`; resolve against `staff_directory` first                                                                                    | `full_name` on the lead-teacher cube                                                                            |
| open policy decisions                                                                                                                                     | stays; markdown                                                                                                 |

### Internal, Illuminate

| Fact                                                                                                             | Destination                                                           |
| ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `module_type` has more than three values; `TP`, `UA`, `ET`, `WPP` and historical types exist; expansions unknown | `module_type`; worded as an open list                                 |
| which module codes exist varies by subject, grade, and region                                                    | `module_code`                                                         |
| module codes are not chronological by name                                                                       | `module_code`                                                         |
| `module_code` is not a subject filter                                                                            | `module_code`                                                         |
| `pct_proficient_formative` covers `QA`, `MQQ`, `CRQ` only                                                        | `pct_proficient_formative`                                            |
| normalize standard codes before a rollup; count-weighted recompute                                               | C2 adds `response_type_code_canonical`; `response_type_code` says why |
| "times assessed" is distinct `source_assessment_id`                                                              | C3 adds `count_assessments`; `source_assessment_id` says why          |
| a CCSS code's grade can differ from `grade_level_tested`                                                         | `response_type_code`                                                  |

### Vendor diagnostics

| Fact                                                                           | Destination                       |
| ------------------------------------------------------------------------------ | --------------------------------- |
| i-Ready `proficiency_level` scale; `Early On Grade Level` counts as proficient | `proficiency_level`, `is_mastery` |
| DIBELS tiers; STAR levels                                                      | `proficiency_level`               |
| tier-movement rates are not comparable across instruments                      | `proficiency_level`               |
| `Outside Round` exists and is dropped by a named-round filter                  | `administration_period`           |
| "most recent diagnostic" is the latest named round, not max `date_taken`       | `administration_period`           |
| vendor `EOY` falls after spring state testing; `MOY` is the last leading round | `administration_period`           |
| multiple sittings inside one window; dedup to most recent per student          | view description                  |
| query this view, not the upstream i-Ready model                                | view description                  |
| coverage start years                                                           | deleted; derivable                |

### State

| Fact                                                                                    | Destination                           |
| --------------------------------------------------------------------------------------- | ------------------------------------- |
| NJSLA and NJGPA are computer-adaptive from spring 2026; no field distinguishes the form | `assessment_type`                     |
| a Fall NJGPA slice is the retake window                                                 | `administration_period`               |
| a missing current-year state result is a release lag                                    | view description                      |
| `lea_student_identifier` is the SIS number; `district_student_identifier` is Miami-only | those dimensions on the students cube |
| FL `is_mastery` is Level 3 and up; `PM1` to `PM3` windows                               | `is_mastery`, `administration_period` |

### What moves to `ai_context`

The tables above are unchanged. This one routes a subset of their facts to the
second channel, applying one rule: **`description:` says what a member is;
`ai_context:` says how to use it.** Most rows split rather than move — the
member keeps its definition and sheds the advice.

| Member                           | `description:` keeps                              | `ai_context:` takes                                                                                                                                                                                                                                                                                                                           |
| -------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `count_students`                 | distinct students per student-year                | heavy at fine grain; `count_scores` is the reliable fallback                                                                                                                                                                                                                                                                                  |
| `performance_band_label_number`  | numeric ordering within the band scale            | never compare a band number across band sets                                                                                                                                                                                                                                                                                                  |
| `module_code`                    | the code identifying the assessment variant       | not a subject filter; not chronological by name; varies by subject, grade and region                                                                                                                                                                                                                                                          |
| `is_internal_assessment`         | true for Illuminate, false for state and vendor   | do not select a source with this; use `assessment_type`                                                                                                                                                                                                                                                                                       |
| `response_type`                  | the value list                                    | not additive across types                                                                                                                                                                                                                                                                                                                     |
| `response_type_code`             | the code and its two spellings                    | normalize before a standards rollup; group on the canonical dimension                                                                                                                                                                                                                                                                         |
| `response_type_root_description` | description of the root response type             | unreliable for FL standards                                                                                                                                                                                                                                                                                                                   |
| `grade_level_tested`             | the grade the assessment targets; null for vendor | for a vendor cut use `grade_level`, not this                                                                                                                                                                                                                                                                                                  |
| `proficiency_level`              | the per-source band vocabularies                  | tier-movement rates are not comparable across instruments                                                                                                                                                                                                                                                                                     |
| `administration_period`          | the per-source vocabulary                         | only meaningful with `assessment_type` scoped; "most recent diagnostic" is the latest named round, not max `date_taken`; `Outside Round` drops out of a named-round filter                                                                                                                                                                    |
| `source_assessment_id`           | the Illuminate assessment id                      | "times assessed" is a distinct count of this                                                                                                                                                                                                                                                                                                  |
| `enrollment_resolution`          | subject_section or homeroom                       | filter to `subject_section` for course and section rollups                                                                                                                                                                                                                                                                                    |
| `scale_score`                    | the scale score; null for internal rows           | compresses at higher grades; not comparable across sources                                                                                                                                                                                                                                                                                    |
| `staff_lead_teacher.full_name`   | `Last, First` format                              | resolve a name against `staff_directory` first                                                                                                                                                                                                                                                                                                |
| the view                         | what the view holds                               | enrollment-scoped, so totals do not reconcile to vendor or state reports; coverage is uneven by region and source; a cross-instrument gap is a calibration artifact; there is no growth measure; dedup multiple sittings in one window; query this view, not the upstream i-Ready model; a missing current-year state result is a release lag |

Facts that do **not** move, and why: anything a reader needs in order to read a
value correctly stays in `description:`. The per-source band vocabularies,
`module_type`'s open value list, `academic_subject`'s source dependence, the
identifier definitions, FL's Level 3 mastery bar, and the computer-adaptive note
on NJSLA and NJGPA are all definitions, not advice.

Query mechanics that apply to any view stay in the `load` docstring, unchanged:
`notSet` versus `equals "null"`, and the de-duplicating dimension-only pull.

Two constraints on writing these. Each `ai_context` value is capped at 2,000
characters and truncated silently past that, so the view's entry is the one at
risk — keep it to the traps, not a second view description. And the same
no-point-in-time-numbers rule that governs `description:` governs this channel.

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
  it too.
- `performance_band_label_number`: currently "Null for state". Adds Illuminate
  only, and not comparable across band sets.
- `academic_subject`: currently lists "English Language Arts" as an example.
  Adds that values are source-dependent and Illuminate's ELA-equivalent is
  `Text Study`.
- `count_scores` and `pct_proficient`: until C1 lands, say that Illuminate
  carries unscored `not_taken` rows that sit in the denominator when
  `response_type` is not filtered, and name the filter that excludes them.

A test in `tests/cube/test_cube_schema.py` loads the YAML and asserts one key
phrase per moved fact, keyed by member name, so a later edit cannot drop one
silently. Cube Cloud validates the model on the branch staging deployment before
merge.

## Server docstring changes

`load` gains two paragraphs after the academic-year crosswalk:

- Filter operators for NULL: `set` and `notSet`; `equals "null"` matches the
  literal string and returns zero rows.
- Grain and counts: a query with no measure de-duplicates identical rows, so add
  a count or the primary key to see row counts; `count_students` is a distinct
  count and can time out at fine grain, where `count_scores` is the reliable
  fallback.

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

**C1 shrinks to a description change and folds into PR 1.** What remains here is
saying, on `count_scores` and `pct_proficient`, that a score row can carry no
proficiency verdict, and on `response_type`, what `not_taken` means. Those
sentences are needed whether or not #5501 has landed; they get reworded once it
does.

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
`source_assessment_id`, not `count_scores`. Re-measured 2026-09-22 and
unchanged: per standard per year the distinct assessment count has quartiles 1,
1, 2, 3 and a maximum of 52, across 6,729 standard-years, and 43.4% of
standard-years rest on one assessment. Distinct `assessment_administration_key`
differs in 84.6% of standard-years because that key includes region and
administered date, so it counts sittings.

Chosen. Add `count_assessments` to the scores cube: `count_distinct` on
`{student_assessment_administrations.source_assessment_id}`, public, exposed on
the view. Description states it counts distinct assessments, not sittings or
scored responses, and that a standard resting on one assessment is a thin base.
Cube only; no dbt change.

Alternative. Text only on `count_scores` and `source_assessment_id`.

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
