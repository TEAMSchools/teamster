# Drain the assessment project knowledge into Cube descriptions and MCP docstrings

Design for #5236, built in #5495. Every warehouse figure in this document is
dated. Re-measure each one before building on it. No figure in this document
goes into a YAML description.

## Problem

The Claude + Cube working group runs on 2 markdown files that someone uploads by
hand to a claude.ai Project:

- `src/cube/mcp/project_knowledge/assessment-cube-reference.md`: data-usage
  conventions for `student_assessment_scores_view`, about 50 facts about how the
  view behaves.
- `src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md`: the session
  protocol.

Those facts reach the model only inside that Project. Claude Code, other
connectors, and the planned org-level skill query the same Cube MCP without
them.

## Starting point

What `main` carries as of 2026-09-28, so this design does not redo it:

- **Counts and rates.** 3 nested counts: `count_assigned` (every row),
  `count_taken` (`response_type != 'not_taken'`) and `count_scored`
  (`is_mastery IS NOT NULL`). `pct_proficient` divides by `count_scored`.
  `pct_taken` is the participation rate, and it means something only for
  Illuminate. All of these carry descriptions.
- **`response_type`.** Never null. Its description lists the 4 values:
  `overall`, `standard`, `group`, `not_taken`.
- **Instructions inside definitions.** Those new descriptions include
  instructions ("filter it explicitly", "Filter assessment_type to illuminate",
  "Pair it with count_scored"). This design moves each instruction to
  `ai_context`.
- **No `ai_context` anywhere** in `src/cube/model/`.
- **The `load` docstring** lists `set` / `notSet` among the filter operators. It
  does not say that `equals "null"` matches the literal string.
- **`.claude/rules/cube-authoring.md`** says `meta.*` keys other than `folders`
  do not reach the model. That is wrong for our MCP path; see below.

## Decision

Move each fact to the one channel every surface reads. The narrowness of the
fact picks the channel:

| Fact is about                         | Destination                                                     |
| ------------------------------------- | --------------------------------------------------------------- |
| what one measure or dimension _is_    | that member's `description:` in the cube YAML                   |
| how to _use_ one measure or dimension | that member's `meta.ai_context:` in the cube YAML               |
| the whole view                        | the view `description:` in `student_assessment_scores_view.yml` |
| how to use the whole view             | the view's `meta.ai_context:`                                   |
| any view (query mechanics)            | the `load` or `meta` docstring in `src/cube/mcp/server.py`      |
| session process or unratified policy  | stays in the markdown, shaped for the later skill               |

Rules for the PR:

- **One home per fact.** The change that lands a fact in Cube deletes it from
  the markdown in the same commit.
- **No point-in-time numbers in YAML.** Score volumes, percentages and year
  ranges go stale silently. Descriptions say "about a third" or "the majority",
  or say how to measure it.
- **Coverage specifics are deleted, not moved.** Which region has which source
  in which years is a live query. The view says coverage is uneven and how to
  check it.
- **Load-bearing guidance goes in tool docstrings, never `instructions=`**
  (#4473).

1 model change ships with the text: the `count_assessments` measure. 3 others
became their own issues; see _Model changes_.

## Why these channels

Cube views inherit each included member's `description:` from its cube, and the
`meta` tool returns those descriptions per view. The `load` docstring already
carries the academic-year crosswalk for the same reason: the claude.ai connector
drops `instructions=` and Claude Code truncates it, while tool descriptions
reach the model on every surface.

Rejected: serving the reference file as an MCP tool or resource. The model has
to choose to call it, resources do not reliably surface through claude.ai
connectors, and it duplicates the planned skill.

### `meta.ai_context` reaches the model

Cube Cloud's UI renders only `meta.folders`. The `/meta` payload carries every
`meta` key, and the payload is what our MCP server returns.

Measured 2026-09-22 against Cube 1.7.43 on the local dev server. A throwaway
`meta.ai_context` and a throwaway arbitrary key went on 1 view and 1 cube
measure, then were reverted:

| Placement                           | In REST `/meta` | Via our `meta` tool          |
| ----------------------------------- | --------------- | ---------------------------- |
| `meta.ai_context` on the view       | yes             | yes                          |
| `meta.ai_context` on a cube measure | yes             | yes, inherited onto the view |
| an arbitrary `meta.<other>` key     | yes             | yes                          |

3 consequences:

- **The view member inherits member-level `meta` from the cube.** So
  `ai_context` goes on the cube YAML member and the view picks it up. No new
  file and no new routing rule.
- **Our MCP server does no field filtering.** `meta` returns each cube dict
  verbatim (`src/cube/mcp/server.py`).
- **`ai_context` gets no special weight on our path.** It arrives as one more
  JSON key beside `description`. Open-source Cube does nothing with it either;
  only Cube Cloud's hosted agent reads it (see _Step 0_). The gain is
  separation: `description:` holds what is true of the data and stays equal to
  its dbt twin, while Cube-specific usage lives in `ai_context:`.

Cube's constraints: `ai_context` goes on views and members only, never at cube
level. The cap is 2,000 characters: Cube's docs say a longer value "is silently
truncated before it reaches the agent", meaning Cube's own agent. Whether the
`/meta` payload our server reads is truncated too is untested; the length guard
below makes the answer irrelevant.

3 guards follow from those constraints:

- **Length.** The schema test asserts that every `ai_context` in
  `src/cube/model/` is 2,000 characters or less, so a value that grows past the
  cap fails the test instead of being cut off.
- **Response size.** The `meta` docstring already says the full catalog nears a
  response-size budget, and every `ai_context` adds to it. The `dates` values
  also repeat on every view that includes `dates`. Step 0 records the size of
  the full-catalog and assessment-view `meta` responses before and after.
- **Cube Cloud.** The measurement above ran on a local server. Step 0 confirms
  the key on the branch staging deployment before the rest of the values are
  written.

### The authoring rule changes in the same PR

`.claude/rules/cube-authoring.md` currently says:

> **`meta.folders` is the only Cube-rendered `meta.*` key.** Put guidance in
> `description:`, not `meta.usage` / `meta.synonyms` / etc. — those land in
> `/v1/meta` but Cube Cloud and the chat agent don't read them.

Left alone, that rule tells the next author to undo this work. The replacement
says 3 things:

- `meta.folders` is the only key Cube Cloud **renders**.
- Every `meta.*` key reaches the model, because our MCP server returns each
  cube's `/meta` entry unchanged. Use `ai_context`, because Cube documents it
  and Cube Cloud's own agent reads it. Do not invent other keys.
- `description:` says what a member is: text that holds against the raw dbt
  column, kept equal to its dbt twin. `meta.ai_context:` says how to use the
  member in Cube, within 2,000 characters.

It drops the `meta.usage` / `meta.synonyms` examples. Neither key appears
anywhere in the model, and naming them invites someone to use them. `usage`
would duplicate `ai_context`, and only our server would read either key; Cube's
own agent reads `ai_context` alone. Synonyms and acronyms go inside
`ai_context`, which is where Cube's docs put them.

The rule file also gains 2 conventions from this spec. Future authors never read
this spec, but the rule loads on every Cube file they open:

- **The dbt twin rule** from _Cube and dbt descriptions are separate strings_,
  so an author whose edit fails the equality test knows why.
- **The placement procedure** from _Placement procedure_, in about 10 lines: the
  7 steps and the tie-breaker.

### Cube and dbt descriptions are separate strings

A column of `fct_assessment_scores_enrollment_scoped` has 2 descriptions: the
dbt one in its properties YAML, and the Cube one on the cube member that reads
it. Nothing copies one into the other. The Cube YAML does not read the dbt
manifest, and kipptaf sets no `persist_docs`.

| Reads it                                              | dbt `description:` | Cube `description:` | Cube `meta.ai_context:` |
| ----------------------------------------------------- | ------------------ | ------------------- | ----------------------- |
| the model, through our Cube MCP `meta` tool           | no                 | yes                 | yes                     |
| an analyst in Cube Cloud                              | no                 | yes                 | no                      |
| an engineer in dbt docs or through the dbt MCP server | yes                | no                  | no                      |

The 2 have already drifted. On `response_type_code`, dbt states which rows carry
the code and Cube says only "Null for state". The model reads the stale copy.

The rule: when the PR changes the `description:` of a Cube member that reads one
column directly (`sql: <column>`), it sets that column's dbt `description:` to
the same text. Measures, view text and `ai_context` have no dbt column, so they
are Cube-only. A schema test asserts each pair is equal, so a later edit to one
side fails the test instead of drifting.

## Placement procedure

The per-member drafts below record about 50 decisions. This procedure produced
them. It is written down so the PR does not re-decide each one by taste, and so
a fact added later lands in the same place. **Work down the list and stop at the
first match.**

1. **Is it a point-in-time number?** Score volumes, percentages, year ranges.
   Delete it, or restate it qualitatively. This step runs first because it
   removes content whatever channel would take it. Configuration is not a
   point-in-time number even though it can change: a band set's cut points say
   what the data means, not how much of it there is. Configuration that no
   member carries needs a model change, and stays in the markdown, corrected,
   until that change ships.
2. **Is it process or unratified policy?** It stays in the markdown. Cube text
   may say that a decision is open, but never states a default for it. This step
   runs before the instruction step because an unratified default is usually
   worded as an instruction ("keep the most recent sitting"), and would
   otherwise land in Cube as if it were settled.
3. **Is it derivable live?** Which region has which source in which years is a
   query. Delete the specifics; say that coverage is uneven and how to check.
4. **Does it hold for more than one view?** `notSet` versus `equals "null"`, and
   the de-duplicating dimension-only pull, are Cube mechanics. They go in the
   `load` or `meta` docstring.
5. **Is it about the answer, and not tied to one member?** Examples: a
   cross-instrument gap is a calibration artifact; totals do not reconcile to
   vendor reports; a missing current-year state result is a release lag. The
   query is correct and the reading is at risk. These go in the view's
   `ai_context`. Answer-level guidance about one member, such as "tier-movement
   rates are not comparable across instruments" on `proficiency_level`, goes to
   that member's `ai_context` under step 7.
6. **Is it a definition?** What a value means, which values exist, what is null
   and when. That member's `description:`.
7. **Is it an instruction?** Do this, do not do that, use X instead. That
   member's `ai_context:`.

Most rows split rather than move, because of steps 6 and 7. A bullet in the
reference file usually carries a definition and an instruction together. So it
matches both and gets cut in 2: the member keeps what it is and sheds what to do
about it.

**Tie-breaker when steps 6 and 7 both fit.** Ask whether the sentence would be
true and useful against the raw dbt column. If it would, it goes in
`description:`, which is twinned with dbt, even when it reads like a warning
("not comparable across assessments"). If it depends on Cube (members, measures,
the view) or tells the agent what to do, it goes in `ai_context:`. For
`count_students`, "distinct students per student-year" is the definition, while
"heavy at fine grain, fall back to count_taken" only makes sense in Cube.

The analysts-and-tooltips rationale for the split no longer applies: KTAF is not
buying Cube Cloud seats for analysts, and agents are the audience. The split
stays because it keeps the dbt twin rule a plain equality: `description:` holds
what is true of the data, and `ai_context:` holds how to use it in Cube.

2 things hold the placement in place. The schema test asserts one key phrase per
moved fact, keyed by member name, so a later edit cannot silently drop one. The
eval is the empirical check: if the routing is wrong, arm B does not beat arm A.

## Per-member drafts

One row per Cube member: the reference-file text that feeds it, and the drafted
value for each channel. The source column names the reference file's section and
the bolded lead phrase of the bullet, which survive edits better than line
numbers. "Present" means the shipped text already says it. Review may reword a
value, but moving a sentence to the other channel needs a sieve step that says
why.

Every draft follows 2 wording conventions:

- **Name the population a member covers, not what it excludes.** "Illuminate
  only; null for every other source" stays true when a source is added; "null
  for state and vendor rows" does not.
- **Never write a bare "vendor".** Illuminate is a vendor platform too. Write
  "vendor diagnostic (i-Ready, DIBELS, STAR)" on first use in a string, or name
  the sources.

Measured 2026-09-28, behind the `performance_band_label_number` draft: on
Illuminate, the band number is set on every row and null everywhere else. Within
one assessment, a band number carries exactly one `proficiency_level` label on
`overall` rows, but a few bands carry 2 or more spellings on `standard` and
`group` rows, and most assessments label the same band number differently on
`standard`/`group` rows than on `overall` rows. That suggests standard-level
scores use a different band scale; the labels were measured, not the cut points.

Measured 2026-09-28, behind the `proficiency_level` and count drafts: DIBELS
carries a fifth value, `Tested Out`, on `group` (subtest) rows only, and
`is_mastery` is null on every one of them. They are nearly all of the DIBELS
rows with no proficiency verdict, so `pct_proficient` leaves them out. The
shipped `count_taken` and `count_scored` descriptions attribute those rows to
"the DIBELS K-2 phonics subtests have no benchmark level set upstream"; the PR
corrects that wording. Whether a student who tested out of a subtest should
count as proficient is a policy question. It goes on the reference file's
open-decisions list, and Cube text says only that it is open.

Re-measure before building, beyond the dated figures:

- Whether Illuminate `group` rows carry whitespace variants of the same
  `response_type_description`. The variants were measured on `standard` rows
  only, and the `response_type_code` draft tells the agent to group Illuminate
  `group` rows by this label.

### Scores cube (`student_assessment_scores`)

| Member                                   | Reference text                                                                                                             | `description:`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `meta.ai_context:`                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `response_type`                          | Shared, "`response_type` — always filter it explicitly"; Illuminate, "`response_type`"                                     | The shipped value list, minus its instruction: never null; overall (every source), group (Illuminate, i-Ready and DIBELS), standard and not_taken (Illuminate only). not_taken marks an assessment a student was assigned and never sat. Not additive across values.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Filter it on every query; default to overall unless a standard or group breakdown is asked for.                                                                                                                                                                                                                                                                                                                                                                     |
| `response_type_code`                     | Illuminate, "Normalize standard codes before any standards-level rollup"                                                   | Breakdown identifier — the standard code on Illuminate standard rows, the domain on i-Ready group rows, the subtest on DIBELS group rows. Null on Illuminate group rows and on every overall and not_taken row. Some CCSS Math standards carry 2 spellings (8.EE.C.8.b and 8.EE.C.8b), and a small share of older rows have an empty code (an empty string, not null).                                                                                                                                                                                                                                                                                                                                                                                            | For a standards rollup, merge the 2 spellings first: remove a dot only when it sits right before a trailing lowercase letter. Then recompute the rate from the merged counts (pct_proficient × count_scored, summed, over summed count_scored); never average the 2 reported rates. For an Illuminate group-level cut, group on response_type_description — this code is null there, so keying on it drops every Illuminate group row and keeps i-Ready and DIBELS. |
| `response_type_description`              | Illuminate, "Normalize standard codes" (the `y = mx + b` variants)                                                         | Human-readable breakdown label. Populated on standard rows and every group row; null on overall and not_taken. A few standards carry whitespace variants of the same label.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `response_type_root_description`         | Shared, "Domain rollup"; Illuminate, "`response_type_root_description` … is reliable here"; FL, last bullet                | CCSS domain the standard rolls up to. Populated on Illuminate standard rows only. Unreliable for Illuminate content aligned to Florida's own standards, whose codes do not fit the CCSS hierarchy.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `performance_band_label_number`          | Shared, "Performance bands are Illuminate-only"; Illuminate, "Bands"                                                       | Position of the score's band within the performance band set it was scored against. Illuminate only; null for every other source. Band sets differ in cut points, in band count, and in which band starts mastery, so band 5 is not always the top. Not comparable across assessments, or across response types within one assessment: standard and group rows can carry different band labels than the assessment's overall rows.                                                                                                                                                                                                                                                                                                                                | Compare band numbers within one assessment and one response_type. There, prefer this number to proficiency_level text for grouping and ordering; on standard and group rows a few bands carry more than one label spelling.                                                                                                                                                                                                                                         |
| `proficiency_level`                      | i-Ready, "Proficiency"; DIBELS, "Proficiency" and "Tier-movement rates are not comparable"; STAR, NJ and FL, "Proficiency" | Proficiency label; the vocabulary is per source. i-Ready: 3 or More Grade Levels Below, 2 Grade Levels Below, 1 Grade Level Below, Early On Grade Level, Mid or Above Grade Level. DIBELS: Well Below Benchmark, Below Benchmark, At Benchmark, Above Benchmark, and Tested Out on some subtest (group) rows. STAR and FL state: Level 1 to Level 5; STAR is null on a share of rows. NJSLA and NJSLA Science: Did Not Yet Meet Expectations, Partially Met Expectations, Approached Expectations, Met Expectations, Exceeded Expectations. NJGPA: Graduation Ready, Not Yet Graduation Ready. Illuminate: the performance band label. Tier-movement rates are not comparable across instruments: fewer, wider tiers mechanically raise the stayed-the-same rate. | On Illuminate standard and group rows, a band can carry more than one label spelling; group by performance_band_label_number there.                                                                                                                                                                                                                                                                                                                                 |
| `is_mastery`                             | Shared, "Headline metric"; Shared, "Performance bands" (the mastery bar); i-Ready, "Proficiency cutoff"; FL, "Proficiency" | Per-row proficient flag that pct_proficient is built from. The bar is per source: i-Ready, Early On Grade Level and Mid or Above Grade Level — Early On is a looser bar than at or above grade level; DIBELS, At and Above Benchmark; STAR and FL, Level 3 and up; NJSLA, Met and Exceeded Expectations; NJGPA, Graduation Ready; Illuminate, set by each assessment's band set, so an Illuminate rate mixes different bars. Null where the source gives no verdict: Illuminate not_taken rows, DIBELS Tested Out subtests, and STAR rows with no level.                                                                                                                                                                                                          | For i-Ready at or above grade level, filter proficiency_level to Mid or Above Grade Level instead. When reporting an Illuminate rate, say which assessments it covers.                                                                                                                                                                                                                                                                                              |
| `scale_score`                            | i-Ready, "Growth is not in the model, and scale scores do not normalize across grade bands"                                | Scale score achieved. Every source except Illuminate, which reports percent_correct instead. Scales differ by source and are not comparable across sources or subjects; within i-Ready the scale also compresses at higher grades, so a change in score is not comparable between elementary and middle grades.                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Report a scale-score change separately for elementary and middle grades, and as a point difference, not a percent of the BOY score. Do not label a computed change with i-Ready's growth-measure names; those norms are not in this view.                                                                                                                                                                                                                           |
| `enrollment_resolution`                  | Shared, "Section/teacher rollups"                                                                                          | How the section enrollment was resolved: subject_section or homeroom.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Filter to subject_section for course- and section-level rollups.                                                                                                                                                                                                                                                                                                                                                                                                    |
| `date_taken`                             | Shared, "Time"                                                                                                             | Date the assessment was taken (completion date). Every source; null or wrong on a small share of Illuminate rows.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | A standalone date, not joined to the calendar. For year and calendar rollups use dates_date_day and academic_year, which read the administration date for Illuminate and college and the test date for state tests and vendor diagnostics (i-Ready, DIBELS, STAR).                                                                                                                                                                                                  |
| `count_students`                         | Shared, "Grain"                                                                                                            | Distinct students (per student-year) with a score in the filtered slice. The shipped note about switching to count_distinct_approx moves to a YAML comment.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Heavier than the plain counts, and has timed out at standard grain; use count_taken there.                                                                                                                                                                                                                                                                                                                                                                          |
| `pct_proficient` and the 3 counts        | Shared, "Headline metric" and "Three nested counts"                                                                        | The shipped text, minus the instructions in the next column                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Moved from the shipped `description:`. pct_proficient: pair it with count_scored, the n it rests on, and never multiply it by count_assigned. pct_taken: filter assessment_type to illuminate before reporting it. count_scored: report it alongside pct_proficient whenever the rate carries weight.                                                                                                                                                               |
| `count_assessments` (new)                | Illuminate, "How many times was this standard assessed"                                                                    | Distinct Illuminate assessments in the filtered set — not sittings, not scored responses. Illuminate only: every other source has no source_assessment_id, so it reads 0 there.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Use this for "how many times was this assessed". A standard resting on one assessment is a thin base for a trend; say so rather than trending it.                                                                                                                                                                                                                                                                                                                   |
| `avg_scale_score`, `avg_percent_correct` | Shared, "Headline metric" ("scope-bound")                                                                                  | Present. The leading `Grain:` clause stays in `description:` under the #4476 convention: a pooled average misleads an analyst reading the tooltip as much as it misleads an agent.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `pct_proficient_formative`               | Illuminate, "Measures — `pct_proficient_formative` does not cover all formative work"                                      | Proficiency rate across the QA, MQQ and CRQ module types only; excludes TP, UA, ET and WPP. CRQ is also available alone as pct_proficient_crq.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Not "all internal checkpoints". For that, build the rollup from the intended module types and flag the pooling choice as an open decision.                                                                                                                                                                                                                                                                                                                          |

### Assessments cube (`student_assessments`)

| Member                   | Reference text                                                                                                                            | `description:`                                                                                                                                                                                                                                                                                                              | `meta.ai_context:`                                                                                                                                                                                                                                                           |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `assessment_type`        | Shared, "Pick the source with `assessment_type`" (value list, "Treat this list as current, not closed"); NJ, "Spring 2026 onward"         | Present value list, plus: From spring 2026, NJSLA and NJGPA are computer-adaptive, and no field separates adaptive from fixed-form scores. NJSLA Science did not change.                                                                                                                                                    | Flag any NJSLA or NJGPA comparison that crosses spring 2026 as possibly comparing 2 scales; never present that trend as settled.                                                                                                                                             |
| `is_internal_assessment` | Shared, "Pick the source with `assessment_type`, not `is_internal_assessment`"                                                            | TRUE for KIPP-authored Illuminate interims; FALSE for every other source — state, college, AP, and the i-Ready, DIBELS and STAR diagnostics KIPP administers itself.                                                                                                                                                        | Do not select a source with this flag; it groups vendor diagnostics with state tests. Filter assessment_type.                                                                                                                                                                |
| `module_type`            | Illuminate, "Module types: there are seven, not three"                                                                                    | Module type for Illuminate assessments. An open list — QA, MQQ, CRQ, TP, UA, ET, WPP and older types; what TP, UA, ET and WPP stand for is not documented. Null for every other source.                                                                                                                                     | Do not expand TP, UA, ET or WPP.                                                                                                                                                                                                                                             |
| `module_code`            | Illuminate, "Which module codes exist varies by subject, grade, AND region", "not in chronological order by name", "not a subject filter" | Present                                                                                                                                                                                                                                                                                                                     | Not a subject filter: one code spans every subject in its round, so pair it with academic_subject. Which codes exist varies by subject, grade and region — check the exact slice before pooling across checkpoints. Names are not chronological; order by median date_taken. |
| `academic_subject`       | Shared, "Two different subject fields, and `academic_subject` values are source-dependent"                                                | Subject tested. Values depend on the source: state and vendor use plain labels (English Language Arts, Mathematics); Illuminate uses course-level names and has no English Language Arts — its ELA equivalent is Text Study, alongside Writing, English 100–400, CCR and AP courses. Distinct from the course's discipline. | Check this member's values for the source before filtering; a wrong label returns zero rows with no error.                                                                                                                                                                   |
| `grade_level_tested`     | Shared, "Three different grade fields"; the i-Ready, DIBELS and STAR "Grade field" bullets                                                | Grade the assessment targets. Populated for Illuminate and state; null for every i-Ready, DIBELS, STAR and college row.                                                                                                                                                                                                     | For a vendor diagnostic, filter grade_level instead — this one returns zero rows with no error. Where both are populated they answer different questions; say which you used.                                                                                                |

### Administrations cube (`student_assessment_administrations`)

| Member                  | Reference text                                                                                                                                                                                                                                                           | `description:`                                                                                                                                                                                                                                                                                                                                                                                                                    | `meta.ai_context:`                                                                                                                                                                                                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `administration_period` | Shared, "`administration_period` is populated for every source except Illuminate"; i-Ready, "Administrations", "Resolving 'the most recent diagnostic'", "EOY is administered _after_ NJSLA"; each source's "Administrations" or "Time" bullet; NJ, "A Fall NJGPA slice" | Window within the academic year; the vocabulary is per source. i-Ready and DIBELS: BOY, MOY, EOY, plus Outside Round for i-Ready sittings outside the 3 windows. STAR: Fall, Winter, Spring. NJGPA: Fall (the routine retake window) and Spring. NJSLA: Spring. FL: PM1 to PM3. College: the College Board round. Null for Illuminate and AP. Vendor EOY falls after spring state testing; MOY is the last named round before it. | Only meaningful with assessment_type scoped. A BOY/MOY/EOY filter drops Outside Round, so say which windows you used. "Most recent diagnostic" is the latest named round in the latest academic_year_label, not the max date_taken. An EOY-versus-state comparison in one year is concurrent, not predictive; use MOY. |
| `source_assessment_id`  | Illuminate, "How many times was this standard assessed"                                                                                                                                                                                                                  | Present                                                                                                                                                                                                                                                                                                                                                                                                                           | "How many times was this assessed" is a distinct count of this, not a row count; count_assessments is that count.                                                                                                                                                                                                      |

### Shared cubes

| Member                   | Reference text                                          | `description:`                                                                                                                                     | `meta.ai_context:`                                                              |
| ------------------------ | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `locations.grade_band`   | Shared, "Three different grade fields"                  | Grade band the school serves (ES, MS, HS) — a school attribute, not a student's grade.                                                             | A grade_band filter is a school filter. For a student's grade, use grade_level. |
| `courses.discipline`     | Shared, "Two different subject fields"                  | Present                                                                                                                                            | —                                                                               |
| `courses.is_foundations` | Shared, "`is_foundations` marks intervention courses"   | TRUE when the section is a Foundations (intervention) course, per the course-subject crosswalk. The only intervention signal on the student views. | Treat it as course enrollment, not a record of services delivered.              |
| `students` identifiers   | NJ, "Student identifier"                                | Present on `lea_student_identifier`, `district_student_identifier` and `state_student_identifier`                                                  | —                                                                               |
| `staff.full_name`        | Shared, "Resolve staff names against `staff_directory`" | Present                                                                                                                                            | — the advice goes to the view instead; see below                                |

`staff_lead_teacher` has no members of its own: it `extends: staff`. An
`ai_context` on `staff.full_name` would therefore also reach `staff_directory`,
where "resolve against `staff_directory` first" is circular. The fact goes to
the assessment view's `ai_context`.

### The view (`student_assessment_scores_view`)

`description:` is present. It says what the view holds and which date each
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
> Students can sit a vendor diagnostic more than once in a window; de-duplicate
> repeat sittings before any student-level count, and since which sitting counts
> is an open decision, say which you kept. A missing current-year state result
> is a release lag, not a defect. Query this view, not upstream vendor tables,
> which carry re-pull duplicates. A CCSS code's own grade can differ from
> grade_level_tested; that is spiral review, not an error. Lead-teacher names
> are stored Last, First; resolve a name against staff_directory before
> filtering, since a zero-row result is not proof the teacher has no students.

Sources in the reference file:

- Shared: "A cross-instrument gap is a calibration artifact", "There is no
  growth measure", "The view is enrollment-scoped", "Region coverage is uneven",
  "Resolve staff names".
- Illuminate: "Sanity-check watch-out" (calibration), "A CCSS code's own grade
  can differ" (sieve step 5).
- i-Ready: "`Outside Round` is also the least complete round", "`is_replacement`
  is Illuminate-only by design" (repeat sittings), "Query this view, not the
  upstream i-Ready model".
- DIBELS and STAR: "Coverage starts in 2023-24".
- NJ: "A missing current-year NJSLA is a release lag".

### Everything that does not land on a member

| Reference text                                                                                                                                                                                                                          | Goes to                                                                  | Sieve step |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ---------- |
| Shared, "Filter a genuinely nullable field with `set` / `notSet`, never `equals "null"`"                                                                                                                                                | `load` docstring                                                         | 4          |
| Shared, "A dimension-only pull silently de-duplicates"                                                                                                                                                                                  | `load` docstring                                                         | 4          |
| Shared, "Section/teacher rollups" ("force-refresh `meta` if the lead-teacher fields appear to be missing")                                                                                                                              | `meta` docstring                                                         | 4          |
| Shared, "Performance bands" — the band-set table                                                                                                                                                                                        | stays, corrected and without volumes, until #5573 ships band-set members | 1          |
| Point-in-time figures: Text Study's score volume; the Outside Round and Newark loss shares; QA3's subject count; the median test dates; the repeat-sitting rate; the Fall NJGPA counts; STAR's yearly volume; the adaptive window dates | deleted; the qualitative claim stays in its row                          | 1          |
| Coverage specifics: Paterson's sources and years; i-Ready's regions; DIBELS and STAR start years; the Newark 2025-26 module-code example; FL is Miami                                                                                   | deleted; the view says coverage is uneven                                | 3          |
| Shared, "Two different subject fields" — "At K-2, `Text Study` is the _only_ ELA-equivalent subject present"                                                                                                                            | stays; evidence for the open ELA decision                                | 2          |
| Shared, "Open decisions"; i-Ready, which sitting is authoritative; NJ, whether NJDOE reset the adaptive cut scores                                                                                                                      | stays                                                                    | 2          |
| The i-Ready, DIBELS and STAR provenance notes ("Documented from the live schema …")                                                                                                                                                     | stays                                                                    | 2          |

### Stays in the markdown

The standing protocol, calibration gate, session log and Drive filing, PII
delivery rules, the open-decision list, and the modeling and deliverables rules.
The routing section shrinks to the assessment-family hints and a pointer to
`meta`, since the per-source sections it routes to no longer exist.

## YAML description changes

Each change is a correction or an addition, worded qualitatively. Current text
checked against `main` on 2026-09-28.

- `module_type`: currently "e.g., QA, CR". Becomes an open list of the values in
  use, null for every other source, with a note that `pct_proficient_formative`
  covers only `QA`, `MQQ`, `CRQ`.
- `is_internal_assessment`: currently "FALSE for state and college". Adds the
  vendors and points at `assessment_type` for source selection.
- `grade_level_tested`: currently "Null for college-entrance assessments". Adds
  that it is null for every vendor row and that `grade_level` is the field to
  use there.
- `administration_period`: currently omits vendor values. Adds `BOY`, `MOY`,
  `EOY` for i-Ready and DIBELS, `Outside Round` for i-Ready **only** (DIBELS has
  no such value, verified 2026-09-22), `Fall`, `Winter`, `Spring` for STAR,
  `PM1` to `PM3` for FL, `Fall` and `Spring` for NJGPA, and `Spring` for NJSLA.
  Says the vocabulary is only meaningful with `assessment_type` scoped. Null for
  every Illuminate row.
- `response_type_code`, `response_type_description` and
  `response_type_root_description`: each currently says only "Null for state".
  True, and incomplete enough to mislead: each is null across a different and
  much larger slice. Measured 2026-09-23:

  | Member                           | Populated on                                    | Null on                                                       |
  | -------------------------------- | ----------------------------------------------- | ------------------------------------------------------------- |
  | `response_type_code`             | `standard`, plus `group` for i-Ready and DIBELS | every Illuminate `group` row, and all `overall` / `not_taken` |
  | `response_type_description`      | `standard` and every `group`                    | all `overall` / `not_taken`                                   |
  | `response_type_root_description` | Illuminate `standard` only                      | every i-Ready, DIBELS, STAR and state row                     |

  Each description states the slice it is populated on, in those terms. The
  load-bearing one is `response_type_code`: it is null on all 2,797,958
  Illuminate `group` rows while `response_type_description` is populated on
  them. So a standards-cluster cut keyed on the code silently drops every
  Illuminate group row and keeps the i-Ready and DIBELS ones. That asymmetry is
  advice about which member to group by, so it goes in `ai_context`.

- `performance_band_label_number`: currently "Null for state assessments". Adds
  Illuminate only, and not comparable across assessments.
- `academic_subject`: currently lists "English Language Arts" as an example.
  Adds that values are source-dependent and Illuminate's ELA equivalent is
  `Text Study`.
- `response_type`, the 3 counts, `pct_taken` and `pct_proficient`: the shipped
  definitions stay. Only their instructions move to `ai_context`.

A test in `tests/cube/test_cube_schema.py` loads the YAML and asserts one key
phrase per moved fact, keyed by member name, so a later edit cannot drop one
silently. Cube Cloud validates the model on the branch staging deployment before
merge.

## Server changes

### Docstrings

`load` extends 2 existing paragraphs and its PII paragraph:

- **Filter operators.** After the `set`/`notSet` list, add: `equals "null"`
  matches the literal string and returns zero rows; use `notSet`.
- **Grain.** Add: a query with no measure de-duplicates identical rows, so add a
  count or the primary key to see row counts. The `count_students` fallback is
  that member's `ai_context`, not this docstring.
- **Access scope.** Add: student views return only the schools the user can
  access. Before describing a result as network-wide, check which regions or
  schools it covers. The row-level filter is silent, so a school- or
  region-scoped user asking a network question gets real, non-empty numbers for
  their own slice, and nothing else in the response says so.

`meta` gains one sentence: refresh before concluding a member is missing.

### An empty-result note on `load`

When `load` returns 0 rows, the server adds a note to the response. Draft
wording: "0 rows. The data may not exist for this slice, or your access may not
include it. Check which regions and schools come back before concluding the data
does not exist."

Why a server note rather than more text: text only makes the check more likely.
The note fires every time, at the moment of risk. It also covers every trap in
this spec whose symptom is zero rows with no error: a wrong `academic_subject`
label, `grade_level_tested` on a vendor diagnostic, `equals "null"`, and a
region that does not carry the source.

Limits:

- It cannot catch a partial result, such as a network-wide answer that silently
  covers 3 regions. The view's `ai_context` and the access-scope sentence carry
  that case.
- The wording stays neutral, because some zero-row answers are real.
- Before building, check whether Cube's `/load` response says when row-level
  access removed rows. If it does, the note names the cause instead of offering
  both.
- The eval cannot test the access case: its `META_STUB` carries no access rules.

`load` returns Cube's response unchanged today (`src/cube/mcp/server.py`), so
the note is one check on the length of `data`.

### Tests and deploy

A test in `tests/cube/test_mcp_server.py` asserts the docstring anchor phrases,
the same way the crosswalk is anchored today, and that the note appears on an
empty `data` array and not on a non-empty one. Redeploy and connector refresh
follow the existing procedure in `src/cube/mcp/CLAUDE.md`.

## Model changes

### In this PR: `count_assessments`

Finding. "How many times was this standard assessed" is a distinct count of
`source_assessment_id`, not a row count. Measured 2026-09-22: per standard per
year, the distinct assessment count has quartiles 1, 1, 2, 3 and a maximum of
52, across 6,729 standard-years. 43.4% of standard-years rest on one assessment.
Distinct `assessment_administration_key` differs in 84.6% of standard-years,
because that key includes region and administered date, so it counts sittings.

Chosen. Add `count_assessments` to the scores cube: `count_distinct` on
`{student_assessment_administrations.source_assessment_id}`, public, exposed on
the view. `source_assessment_id` is null outside Illuminate, so the description
says the count covers Illuminate only. It is not added to `proficiency_rollup`,
so this PR does not touch the rollup. Cube only; no dbt change.

Alternative. Text only, on `count_taken` and `source_assessment_id`.

### Moved to their own issues

| Change                                                                          | Issue | Why it left this PR                                                                                  |
| ------------------------------------------------------------------------------- | ----- | ---------------------------------------------------------------------------------------------------- |
| Band-set columns on `dim_assessments` (set name, band count, mastery band, cut) | #5573 | A dbt model change with open naming and unit questions; it ships on its own.                         |
| `assessment_family` on `dim_assessments` (`internal`, `vendor`, `state`, …)     | #5574 | A dbt model change; the text on `is_internal_assessment` covers the trap in the meantime.            |
| `response_type_code_canonical` on the fact, added to `proficiency_rollup`       | #5575 | Rebuilds the 15M-row fact and edits the rollup block that #5557 is reworking, so it waits for #5557. |

Each issue carries its finding, its design and its validation. The drafts above
use the text-only fallback for each one, and each issue says which text to
repoint when it ships.

## Eval extension

`src/cube/mcp/eval` today measures one thing, the academic-year crosswalk, with
a hand-written `META_STUB`. This adds a second family without disturbing it.

- `prompts.yaml` gains family 4, assessment traps. Each prompt names the trap it
  must avoid:
  - an i-Ready question by grade: must filter `grade_level`, not
    `grade_level_tested`
  - a "state scores only" question: must not use `equals "null"`
  - a "QA3 math" question: must pair `module_code` with a subject filter
  - a "vendor diagnostics" question: must not select on `is_internal_assessment`
  - an "all internal checkpoints" question: must not use
    `pct_proficient_formative` alone, or must say what it excludes
  - a "most recent diagnostic" question: must scope to a named round
  - a Paterson i-Ready question: must report coverage, not zero as a failure
- `scorer.py` checks the captured `load` query for each trap, not the answer
  text, and reports a trap rate per arm with Wilson intervals as today.
- `arms.py` gains a loader that builds a `META_STUB` from the YAML under
  `src/cube/model/` for the assessment view, so arm B measures the working tree.
  Arm A reads `eval/fixtures/meta_pre_drain.json`, generated once from
  `origin/main` before the PR's first description change and committed. Both
  arms use the real `server.py` docstrings; arm A substitutes the pre-drain
  `load` paragraphs by anchor, the same mechanism the crosswalk arm uses.
- The runner stays hermetic per `eval/README.md`.

The eval runs once the descriptions, docstrings and `count_assessments` are all
on the branch. Arm B must beat arm A on the trap rate for the family, or the
description text is revised before the PR merges.

A standards-rollup trap (must group on the canonical code) needs the member from
#5575, so that issue adds it.

### Step 0: does the field matter?

Open-source Cube does nothing with `ai_context`. In `cube-js/cube` the key
appears only in documentation, which names Cube Cloud's hosted agent as its
reader, and our MCP server returns it as one more JSON key beside `description`.
An agent treats `ai_context` specially only if a prompt tells it to. The one
third-party Cube MCP server that mentions the key works that way. So the
question is not whether `ai_context` reaches the model, but whether putting
guidance there, with or without a pointer, changes behavior compared with the
same text in `description:`.

The first design compared no text against text in `ai_context`, which cannot
separate the field from the extra text. It is replaced by 4 placement arms in
`src/cube/mcp/eval/arms.py`, run on the crosswalk prompts (families 1 to 3):

| Arm          | Guidance lives in                                    | Isolates                     |
| ------------ | ---------------------------------------------------- | ---------------------------- |
| `F0_none`    | nowhere; plain definitions only                      | floor: is there headroom?    |
| `F1_desc`    | appended to the year members' `description`          | description-only             |
| `F2_ctx`     | the same members' `meta.ai_context`                  | does the field alone matter? |
| `F3_ctx_ptr` | `ai_context`, plus a `meta` docstring line to use it | does a pointer matter?       |

Every arm uses the `load` docstring without its crosswalk paragraph, and the
guidance is that paragraph lifted verbatim, so the words are identical across
arms. Run 2026-09-29 on Haiku only, 3 reps, 288 conversations. Haiku is the
weaker model, so it is where placement is most likely to matter; a Sonnet run
was stopped after 35 conversations to save Agent SDK credit.

Decision rules, written before the results. The primary metric is the wrong-year
rate on the determinate prompts (families 1 and 2), with Wilson 95% intervals;
the family 3 disambiguation rate is secondary.

Amended 2026-09-29, while the run was in progress and before any result was
read: the user chose the `description:`/`ai_context:` split on simplicity
grounds, because it keeps the dbt twin test a plain equality. The run no longer
picks the design. It guards against `ai_context` doing worse than `description:`
and decides whether the `meta` docstring needs the pointer.

1. **No headroom.** If `F0_none` is near zero and inside `F1_desc`'s interval,
   the run cannot tell placements apart. Keep the split, without the pointer.
2. **No difference.** If `F2_ctx` and `F3_ctx_ptr` fall inside `F1_desc`'s
   interval, keep the split without the pointer.
3. **The pointer helps.** If `F3_ctx_ptr` beats `F2_ctx` with non-overlapping
   intervals, add the pointer to the `meta` docstring.
4. **`ai_context` hurts.** If `F2_ctx` and `F3_ctx_ptr` are both worse than
   `F1_desc` with non-overlapping intervals, reopen the split: usage text moves
   to `description:` and the twin test changes to a prefix match.

A null or negative result is kept and written down, not rerun until it passes.

**Result, 2026-09-29 (Haiku, 288 conversations, 60 determinate per arm).** Rule
2 fires: keep the split, without the pointer.

| Arm          | Wrong year (95% interval) | Correct | No query |
| ------------ | ------------------------- | ------- | -------- |
| `F0_none`    | 28.3% [19–41]             | 71.7%   | 0%       |
| `F1_desc`    | 0.0% [0–6]                | 100%    | 0%       |
| `F2_ctx`     | 1.7% [0–9]                | 96.7%   | 1.7%     |
| `F3_ctx_ptr` | 0.0% [0–6]                | 96.7%   | 3.3%     |

- There is headroom: with no guidance, Haiku gets the year wrong 28% of the
  time. Guidance in any of the 3 placements takes that to about zero, and the 3
  intervals overlap.
- `F2_ctx`'s one wrong answer is the family 2 trap: it filtered `2026-2027` for
  an SY26 question.
- Every arm surfaced its interpretation on all family 3 (ambiguous) prompts.
- 9 conversations hit the 12-turn limit, all on "by school" prompts, spread
  across the 4 arms (4 in `F3_ctx_ptr`). The stub returns no school breakdown,
  so the model retries; this is a harness artifact, not a placement effect.
- A Sonnet run was stopped after 35 conversations. Those records are not part of
  this result.

Raw records: `src/cube/mcp/eval/out/placement_2026-09-29_haiku.jsonl`
(gitignored, local only).

Still to do before any `ai_context` ships: confirm the key on the branch staging
deployment, and record the size of the full-catalog and
`student_assessment_scores_view` `meta` responses before and after.

### Why family 4 is small

7 traps against about 50 facts looks like a sample. It is closer to the whole
set. A trap is a predicate over a captured query, so a fact can become one only
when the query alone proves the violation. The facts split 3 ways:

- **Malformed query: checkable.** For example, `is_internal_assessment` used to
  select a source, `equals "null"` where `notSet` was meant, or `module_code`
  with no subject filter. Family 4 draws from these.
- **Correct query, misread answer: never checkable.** The calibration-artifact
  rule, totals not reconciling to vendor or state reports, a missing
  current-year state result being a release lag, uneven coverage, scale scores
  compressing at higher grades. Nothing in the query is wrong, so no predicate
  over query shape can fire. This limit is permanent, and it is why step 5 of
  the placement procedure routes these facts to prose.
- **Definitions: nothing to violate.** Value lists, FL's Level 3 mastery bar,
  `module_type`'s open list.

So the eval measures the checkable third and the descriptions carry the rest.
Each extra trap costs a written prompt and 2 arms of model-in-the-loop runtime,
against a gate that already blocks the PR.

### Pointing the trap checks at production, deferred

`scorer.py` inspects the captured `load` query, not the answer text, so the same
predicate could run against a real logged query. That is deliberately **not** in
scope here.

Measured 2026-09-22: every Cube query reaches BigQuery under one service
account, and the only job label is `cube_request_id`, a UUID. That was 369 jobs
on the assessment fact over 7 days, 227 distinct ids, with no surface, user or
application field. An agent's query and a dashboard refresh look the same, so a
trap **rate** computed from `JOBS_BY_PROJECT` would put every human dashboard
load in the denominator. Only compiled SQL survives, not the Cube query JSON,
and the question that prompted it is nowhere.

What is available today is the crude form: regex the compiled SQL for a member
reference and count. It answers whether a shape occurs in production, not how
often an agent falls into a trap. #5557's rollup measurement uses the same
technique, with the same limits.

The real dependency is **attribution and question text**, which the separate
MCP-interaction recording spec provides: question, `query_json`,
`members_referenced`, outcome, `server_sha`. Once that lands, each trap becomes
a standing monitor instead of a pre-merge gate. That matters because the eval
proves the descriptions work on 7 written prompts, not on what people actually
ask or on whether they still work in November.

The only obligation this spec takes on is keeping the trap predicates importable
rather than inlined in the scorer's main loop.

Once those monitors exist, each checkable fact has a definition of done: its
trap stops firing. That holds only for the malformed-query third. A correct
query that is misread leaves nothing to detect, so those facts stay
documentation.

## Project-knowledge trim

- The PR deletes every fact it moved from `assessment-cube-reference.md`.
  Afterward the file holds the section headers, the open-decision pointers, a
  line under each source saying the field facts live in `meta`, and the
  corrected band-set table until #5573 removes it.
- `assessment-cube-orchestrator.md` loses the routing entries that point at
  deleted sections. Step 3 of the protocol changes from "filter `response_type`
  explicitly" to "confirm `response_type` from `meta`".
- `README.md` in that folder gains a step: after the PR merges, re-upload the
  changed files to the Project. Its update loop says a field fact goes to the
  Cube YAML, a query mechanic goes to `server.py`, and only protocol or policy
  goes to these files.

## PR and validation

#5495 carries all of it, this spec included, and closes #5236.

| Change                                                    | Validation                                                                      |
| --------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Step 0: `ai_context` on the `dates` academic-year members | crosswalk eval families 1 to 3, arm C against arm B; result recorded either way |
| Descriptions and their dbt twins, `ai_context`, the rule  | `uv run pytest tests/cube/`; Cube Cloud branch staging validates the model      |
| `load` and `meta` docstrings, empty-result note           | `uv run pytest tests/cube/`                                                     |
| `count_assessments`                                       | branch staging query returns quartile-shaped counts                             |
| Reference and orchestrator trim                           | every deleted fact has a home in the diff; the PR body lists them               |
| All of it                                                 | eval run; arm B beats arm A                                                     |

The PR body carries the markdown lines it deleted, so a reviewer can see each
fact beside its new wording.

## Out of scope

- Band-set columns: #5573.
- `assessment_family`: #5574.
- The canonical standard code: #5575. Fixing the upstream standards crosswalk
  instead is a separate issue, noted there.
- Partitioning `fct_assessment_scores_enrollment_scoped`, and finding why
  `proficiency_rollup` serves nothing: #5557.
- The org-level claude.ai skill. The trimmed markdown is shaped for it; the
  skill itself is later work.
- `pct_proficient_formative` semantics. Whether to widen it or add a
  module-coded rollup is a pooling decision on the open-policy list.
- Any change to `int_assessments__response_rollup` or the reports that read it.
