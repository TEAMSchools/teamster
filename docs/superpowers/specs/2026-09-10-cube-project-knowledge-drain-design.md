# Drain the assessment project knowledge into Cube descriptions and MCP docstrings

Design for #5236. Brainstormed 2026-09-10. Warehouse figures measured in prod
BigQuery the same day; re-measure before each PR. No figure in this document
goes into a YAML description.

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

| Fact is about                        | Destination                                                     |
| ------------------------------------ | --------------------------------------------------------------- |
| one measure or dimension             | that member's `description:` in the cube YAML                   |
| the whole view                       | the view `description:` in `student_assessment_scores_view.yml` |
| any view (query mechanics)           | the `load` or `meta` docstring in `src/cube/mcp/server.py`      |
| session process or unratified policy | stays in the markdown, shaped for the later skill               |

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
descriptions reach the model on every surface. `meta.usage` and other `meta.*`
keys are not rendered by Cube Cloud or the connector; only `meta.folders` is.
Serving the reference file as an MCP tool or resource was rejected: the model
has to choose to call it, resources do not reliably surface through claude.ai
connectors, and it duplicates the skill.

## Placement map

Every fact in the reference file, its destination, and what happens to the
markdown. "Present" means the shipped description already says it and the
markdown line is simply deleted.

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

### Stays in the markdown

The standing protocol, calibration gate, session log and Drive filing, PII
delivery rules, the open-decision list, and the modeling and deliverables rules.
The routing section shrinks to the assessment-family hints and a pointer to
`meta`, since the per-family sections it routes to no longer exist.

## YAML description changes

Each change is a correction or an addition, worded qualitatively. The ones that
correct shipped text:

- `module_type`: currently "e.g., QA, CR". Becomes an open list of the values in
  use with a note that `pct_proficient_formative` covers only `QA`, `MQQ`,
  `CRQ`.
- `is_internal_assessment`: currently "FALSE for state and college". Adds the
  vendors and points at `assessment_type` for source selection.
- `grade_level_tested`: currently "Null for college-entrance". Adds that it is
  null for every vendor row and that `grade_level` is the field to use there.
- `administration_period`: currently omits vendor values. Adds `BOY`, `MOY`,
  `EOY`, `Outside Round` for i-Ready and DIBELS, `Fall`, `Winter`, `Spring` for
  STAR, `PM1` to `PM3` for FL, and that the vocabulary is only meaningful with
  `assessment_type` scoped.
- `response_type`: currently "overall, strand, standard". Becomes `overall`,
  `standard`, `group`, plus the null case until C1 lands.
- `performance_band_label_number`: currently "Null for state". Adds Illuminate
  only, and not comparable across band sets.
- `academic_subject`: currently lists "English Language Arts" as an example.
  Adds that values are source-dependent and Illuminate's ELA-equivalent is
  `Text Study`.
- `count_scores` and `pct_proficient`: until C1 lands, say that Illuminate
  carries unscored placeholder rows that sit in the denominator when
  `response_type` is not filtered.

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

### C1. `response_type` null rows and unscored placeholders

Finding. The reference says only non-Illuminate rows have a null
`response_type`. The fact has 940,115 Illuminate rows with null `response_type`,
null `response_type_code`, null `is_mastery`, null `percent_correct`, and all
but 15 with a null test date. They come from the `left join` of
`int_assessments__scaffold` to `int_illuminate__agg_student_responses` in
`int_assessments__response_rollup`: a student was assigned an assessment and no
responses were joined. About 7% of Illuminate rows. `count_scores` counts them,
so an Illuminate `pct_proficient` without a `response_type` filter has an
inflated denominator. The fact's only SQL consumer is the Cube scores cube; the
bridge and dimension files mention it in descriptions only.

Chosen. In `fct_assessment_scores_enrollment_scoped`: set `response_type` to
`'overall'` on the state and vendor branches, and drop rows where
`response_type`, `is_mastery`, `percent_correct`, and `scale_score` are all
null. After this, `equals "overall"` works for every source and the null case
disappears from the view. Update `count_scores`, `pct_proficient`, and
`response_type` descriptions to drop the placeholder note. Record row counts
before and after in the PR: total, per `assessment_type`, and the Illuminate
`overall` count, which must not change.

Check before the PR: `int_assessments__scaffold` consumers other than the
rollup, to confirm nothing expects assigned-but-unscored rows to reach this
fact.

Alternatives. Cube-only: a `scored` segment, or filter the proficiency
primitives on `is_mastery IS NOT NULL`. No rebuild, but it changes measure
semantics without a schema change. Text only: describe the null, the operator,
and the denominator effect.

### C2. Canonical standard code

Finding. `response_type = 'standard'` has 1,791 distinct codes. Stripping all
non-alphanumerics and the narrow rule
`REGEXP_REPLACE(code, r'\.([a-z])$', r'\1')` both collapse them to 1,736. Every
one of the 55 merged groups is a pair differing only by a dot before the
trailing sub-standard letter, such as `CCSS.Math.Content.8.EE.C.8.b` and
`CCSS.Math.Content.8.EE.C.8b`. Descriptions are identical apart from whitespace
in 4 pairs. No group has 3 members and no group mixes two standards. The root
cause is upstream: Illuminate holds two mirror copies of the CCSS Math standards
document, category ids 39 to 61 with the dot and 64 to 92 without, 110 standard
ids for the 55 pairs, none hidden. Numeric-only codes such as `6.2.1` exist, so
the blunt strip carries a collision risk the narrow rule does not.

Chosen. Add `response_type_code_canonical` to
`fct_assessment_scores_enrollment_scoped` with the narrow rule, raw code kept.
Expose it on the scores cube and the view, and add it to `proficiency_rollup`,
where it is functionally dependent on `response_type_code` and adds no rows.
Because `pct_proficient` is built from additive primitives, grouping on the
canonical code makes Cube do the count-weighted recompute the reference asks the
analyst to do by hand. The `response_type_code` description names the two
spellings and points at the canonical dimension.

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
`source_assessment_id`, not `count_scores`. Per standard per year the distinct
assessment count has quartiles 1, 1, 2, 3 and a maximum of 52; 43% of
standard-years rest on one assessment. Distinct `assessment_administration_key`
differs in 84% of standard-years because that key includes region and
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

| PR  | Scope                                                          | Validation                                                                                        |
| --- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 1   | YAML descriptions, reference trim, schema test                 | `uv run pytest tests/cube/`; Cube Cloud branch staging validates the model                        |
| 2   | `load` and `meta` docstrings, eval family 4, pre-drain fixture | `uv run pytest tests/cube/`; eval run, arm B beats arm A                                          |
| 3   | C1: `response_type` and placeholder rows                       | `uv run dbt build --select fct_assessment_scores_enrollment_scoped+`; row counts before and after |
| 4   | C2: canonical standard code                                    | dbt build; pre-agg partition count unchanged on branch staging                                    |
| 5   | C3: `count_assessments`                                        | `uv run pytest tests/cube/`; branch staging query returns quartile-shaped counts                  |
| 6   | C4: `assessment_family`                                        | `uv run dbt build --select dim_assessments+`; eval rerun                                          |

Each PR body carries the markdown lines it deleted, so a reviewer can see the
fact and its new wording side by side.

## Out of scope

- The upstream standards crosswalk (C2, not chosen). Separate issue.
- The org-level claude.ai skill. The trimmed markdown is shaped for it; the
  skill itself is later work.
- `pct_proficient_formative` semantics. Whether to widen it or add a
  module-coded rollup is a pooling decision on the open-policy list.
- Any change to `int_assessments__response_rollup` or the reports that read it.
