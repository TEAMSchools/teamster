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

### The supported agent path

Everything in this spec assumes agents reach Cube through our Cube MCP server,
which calls the REST API. That path carries member and view `description`,
`meta.ai_context`, the `load` and `meta` docstrings, and the empty-result note.
The SQL API is the BI path (Superset): Cube serves `description` text there as
Postgres column comments (`pg_catalog.pg_description`), and nothing in its code
reads `ai_context`, the docstrings or the note. An agent that needs the SQL API
is a new design question; its guidance would come from its own prompt or skill.

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
- **REST check on the branch.** Before merge, a local Cube server on the
  branch's model confirms over REST `/meta` that every `ai_context` comes back:
  member-level and view-level as `ai_context`, the 2 view overrides as
  `aiContext`. REST is the path our MCP server and other clients use.

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
- **View-level overrides for shared members:** to give a member guidance in one
  view only, override its `ai_context` in that view's `includes:` entry. The
  override replaces the member's whole `meta` in that view, and REST `/meta`
  returns it as `aiContext`. Use it for view-specific guidance on members of
  shared cubes (`staff`, `locations`, `courses`, `dates`). If the cube member
  also carries an `ai_context`, the override must restate it; a schema test
  fails otherwise.

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
count as proficient is a policy question. It goes on the orchestrator's _Flag,
don't invent_ list, and Cube text says only that it is open.

Checked 2026-09-28, behind the `module_type` draft: `module_type` is entered by
hand in a Google AppSheet app
(`stg_google_appsheet__illuminate_assessments_extension`), and nothing documents
its codes. UA is Unit Assessment, per `rpt_deanslist__mod_assessment.yml`. The
assessment titles suggest ET is Exit Ticket, TP is Test Prep, and WPP is a
Literacy writing task, but those are inferences. They go on the reference file's
open-questions list, with the title evidence, for whoever maintains the AppSheet
app to confirm.

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
| `count_assigned`                         | Shared, "Three nested counts"                                                                                              | Every assessment row, including the Illuminate not_taken rows where a student was assigned an assessment and never sat it. The widest of 3 nested counts: assigned contains taken contains scored.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | For assessments actually sat use count_taken; for the population pct_proficient is computed over use count_scored.                                                                                                                                                                                                                                                                                                                                                  |
| `count_taken`                            | Shared, "Three nested counts"; DIBELS and STAR, "Proficiency"                                                              | Assessments a student actually sat: every row except the Illuminate not_taken placeholders. Only Illuminate records non-participation, so for every other source this equals count_assigned. Wider than count_scored, because a sat assessment can carry no proficiency verdict: STAR rows with no level, and DIBELS Tested Out subtests.                                                                                                                                                                                                                                                                                                                                                                                                                         | Use this for "how many assessments were taken".                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `count_scored`                           | Shared, "Headline metric" and "Three nested counts"                                                                        | Assessments carrying a proficiency verdict (is_mastery set). The narrowest count, and the denominator of pct_proficient.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Report it alongside pct_proficient whenever the rate carries weight; it is the n the rate rests on.                                                                                                                                                                                                                                                                                                                                                                 |
| `pct_taken`                              | Shared, "Three nested counts"; Illuminate, "Measures — `pct_taken` is meaningful here and nowhere else"                    | Grain: meaningful only within Illuminate; pooling across sources is a silent-failure trap. Participation rate: assessments sat / assessments assigned. Every other source reads 100% by construction.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Filter assessment_type to illuminate before reporting it.                                                                                                                                                                                                                                                                                                                                                                                                           |
| `pct_proficient`                         | Shared, "Headline metric"                                                                                                  | Proficiency rate: proficient scores / scores carrying a verdict (count_scored). The headline metric, and the only score measure comparable across sources' incompatible scales.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Pair it with count_scored; never multiply it by count_assigned to get a proficient count.                                                                                                                                                                                                                                                                                                                                                                           |
| `count_assessments` (new)                | Illuminate, "How many times was this standard assessed"                                                                    | Distinct Illuminate assessments in the filtered set — not sittings, not scored responses. Illuminate only: every other source has no source_assessment_id, so it reads 0 there.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Use this for "how many times was this assessed". A standard resting on 1 assessment is a thin base for a trend; say so rather than trending it.                                                                                                                                                                                                                                                                                                                     |
| `avg_scale_score`, `avg_percent_correct` | Shared, "Headline metric" ("scope-bound")                                                                                  | Present. The leading `Grain:` clause stays in `description:` under the #4476 convention: pooling across sources is meaningless in the data itself.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `pct_proficient_formative`               | Illuminate, "Measures — `pct_proficient_formative` does not cover all formative work"                                      | Proficiency rate across the QA, MQQ and CRQ module types only; excludes TP, UA, ET and WPP, about a third of module-coded Illuminate scores. CRQ is also available alone as pct_proficient_crq.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Not "all internal checkpoints". For that, build the rollup from the intended module types and flag the pooling choice as an open decision.                                                                                                                                                                                                                                                                                                                          |

### Assessments cube (`student_assessments`)

| Member                   | Reference text                                                                                                                            | `description:`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | `meta.ai_context:`                                                                                                                                                                                                                                                                                                                            |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `assessment_type`        | Shared, "Pick the source with `assessment_type`" (value list, "Treat this list as current, not closed"); NJ, "Spring 2026 onward"         | Present value list, plus: From spring 2026, NJSLA and NJGPA are computer-adaptive, and no field separates adaptive from fixed-form scores. NJSLA Science did not change.                                                                                                                                                                                                                                                                                                                                                                                  | Use this member to select a source. Flag any NJSLA or NJGPA comparison that crosses spring 2026 as possibly comparing 2 scales; never present that trend as settled.                                                                                                                                                                          |
| `is_internal_assessment` | Shared, "Pick the source with `assessment_type`, not `is_internal_assessment`"                                                            | TRUE for Illuminate (KIPP-authored interims) only; FALSE for every other source, including the i-Ready, DIBELS and STAR diagnostics KIPP administers itself.                                                                                                                                                                                                                                                                                                                                                                                              | Do not select a source with this flag; it groups vendor diagnostics with state tests. Filter assessment_type instead.                                                                                                                                                                                                                         |
| `module_type`            | Illuminate, "Module types: there are seven, not three"                                                                                    | Illuminate module type. An open list: QA (Quick Assessments), MQQ (Multiple-Choice Quick Questions), CRQ (Constructed Response Questions), UA (Unit Assessment), TP, ET, WPP, and older types. What TP, ET and WPP stand for is not documented. Illuminate only; null for every other source.                                                                                                                                                                                                                                                             | Do not expand TP, ET or WPP. pct_proficient_formative covers only QA, MQQ and CRQ.                                                                                                                                                                                                                                                            |
| `module_code`            | Illuminate, "Which module codes exist varies by subject, grade, AND region", "not in chronological order by name", "not a subject filter" | Code identifying the assessment within its source. Illuminate: the checkpoint code within a module type (for example QA1, MQQ2); one code spans every subject assessed in that round, and a small share of Illuminate assessments have none. State tests: subject and grade (for example ELA05, MAT08, ALG01; ELAGP and MATGP for NJGPA). i-Ready and STAR: the subject. DIBELS: Composite.                                                                                                                                                               | Not a subject filter on its own for Illuminate, where one code spans every subject in its round. Always pair it with academic_subject. Which Illuminate codes exist varies by subject, grade and region, so check the exact slice before pooling across checkpoints. Illuminate code names are not chronological; order by median date_taken. |
| `academic_subject`       | Shared, "Two different subject fields, and `academic_subject` values are source-dependent"                                                | Subject tested; the vocabulary is per source. State tests: English Language Arts, Mathematics, Science, and course names for end-of-course tests (Algebra I, Geometry, Civics). i-Ready and STAR: Math and Reading, plus Early Literacy for STAR. DIBELS: Reading. Illuminate: course-level names, with no English Language Arts value; its ELA equivalent is Text Study, alongside Writing, English 100–400, CCR and AP courses, and math appears as Mathematics and course names such as Algebra I and Geometry. Distinct from the course's discipline. | Check this member's values for the source before filtering; a wrong label returns zero rows with no error. Which labels count as 'math' or 'ELA' across sources is an open decision; say which labels you included.                                                                                                                           |
| `grade_level_tested`     | Shared, "Three different grade fields"; the i-Ready, DIBELS and STAR "Grade field" bullets                                                | Grade the assessment targets; 0 is kindergarten. Illuminate and state tests only; null for every other source, for the NJSLA end-of-course tests (Algebra I, Geometry, Algebra II), and for a small share of Illuminate assessments.                                                                                                                                                                                                                                                                                                                      | For a vendor diagnostic (i-Ready, DIBELS, STAR) or an NJSLA end-of-course test, filter grade_level instead; this member returns zero rows with no error. Where both are populated they answer different questions, and which one grade-band reporting should use is an open decision; say which you used.                                     |

### Administrations cube (`student_assessment_administrations`)

| Member                  | Reference text                                                                                                                                                                                                                                                           | `description:`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `meta.ai_context:`                                                                                                                                                                                                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `administration_period` | Shared, "`administration_period` is populated for every source except Illuminate"; i-Ready, "Administrations", "Resolving 'the most recent diagnostic'", "EOY is administered _after_ NJSLA"; each source's "Administrations" or "Time" bullet; NJ, "A Fall NJGPA slice" | Window within the academic year; the vocabulary is per source. i-Ready and DIBELS: BOY, MOY, EOY, plus Outside Round for i-Ready sittings outside the 3 windows. STAR: Fall, Winter, Spring. NJGPA: Fall (the routine retake window) and Spring. NJSLA and NJSLA Science: Spring. FL FAST: PM1 to PM3; FL end-of-course and science: PM3. College: the College Board round. Every source except Illuminate. i-Ready and DIBELS EOY falls after spring state testing; MOY is the last named round before it. | Only meaningful with assessment_type scoped. A BOY/MOY/EOY filter drops Outside Round, so say which windows you used. "Most recent diagnostic" is the latest named round in the latest academic_year_label, not the max date_taken. An EOY-versus-state comparison in one year is concurrent, not predictive; use MOY. |
| `source_assessment_id`  | Illuminate, "How many times was this standard assessed"                                                                                                                                                                                                                  | Illuminate assessment id at the administration grain (the canonical id). Illuminate only; null for every other source.                                                                                                                                                                                                                                                                                                                                                                                      | "How many times was this assessed" is a distinct count of this, not a row count; count_assessments is that count.                                                                                                                                                                                                      |

### Shared cubes

| Member                   | Reference text                                          | `description:`                                                                                    | `meta.ai_context:`                                                                                                                                               |
| ------------------------ | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `locations.grade_band`   | Shared, "Three different grade fields"                  | Grade band the school serves (ES, MS, HS): a school attribute, not a student's grade.             | A grade_band filter is a school filter. For a student's grade, use grade_level.                                                                                  |
| `courses.discipline`     | Shared, "Two different subject fields"                  | Present                                                                                           | —                                                                                                                                                                |
| `courses.is_foundations` | Shared, "`is_foundations` marks intervention courses"   | TRUE when the section is a Foundations (intervention) course, per the course-subject crosswalk.   | Treat it as course enrollment, not a record of intervention services delivered. The assessment view overrides this to add its view-specific sentence; see below. |
| `students` identifiers   | NJ, "Student identifier"                                | Present on `lea_student_identifier`, `district_student_identifier` and `state_student_identifier` | —                                                                                                                                                                |
| `staff.full_name`        | Shared, "Resolve staff names against `staff_directory`" | Present                                                                                           | — the advice goes to an override on the assessment view; see below                                                                                               |

`staff_lead_teacher` has no members of its own: it `extends: staff`. An
`ai_context` on `staff.full_name` would therefore also reach `staff_directory`,
where "resolve against `staff_directory` first" is circular.

Cube lets a view give one included member its own `meta.ai_context`
(`- name: full_name` with a `meta:` block under `includes:`). Tested 2026-09-29
on a local Cube 1.7.43, first with its schema compiler and then over REST
`/meta`:

- The override lands on that member in that view only, not on its sibling fields
  and not on `staff_directory.full_name`.
- It replaces the member's whole `meta` in that view; a cube-level `ai_context`
  on the same member disappears there and survives in other views.
- REST `/meta` returns it as `aiContext`, while member-level and view-level
  values keep `ai_context`. Cube's YAML loader camel-cases the include entry,
  and its `meta` with it.

The assessment view uses 2 overrides:

| View member                    | Override `ai_context`                                                                                                                                                       |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `staff_lead_teacher_full_name` | Stored Last, First. Resolve a name against staff_directory before filtering; a zero-row result is not proof the teacher has no students.                                    |
| `is_foundations`               | The only intervention signal on this view; there is no program- or MTSS-tracking dimension. Treat it as course enrollment, not a record of intervention services delivered. |

The `is_foundations` override restates the cube-level `ai_context`, because the
override replaces it. Guards:

- The `meta` pointer names both spellings (see _Server changes_).
- The length test checks both `ai_context` and `aiContext`.
- A schema test fails when a view override sits on a member whose cube-level
  `ai_context` it does not contain, so a later cube-level addition cannot be
  hidden silently.

### The view (`student_assessment_scores_view`)

Views have no dbt twin, so the split is: `description:` says what the view is,
and `ai_context:` says how to read results from it. The shipped description is
corrected: `group` rows are not Illuminate-only, and bare "vendor" is replaced.

`description:` (863 characters):

> Assessment scores across Illuminate interims, NJ and FL state tests, and
> vendor diagnostics (i-Ready, DIBELS, STAR), one row per student x assessment x
> administration x response type. Enrollment-scoped: a score appears only if it
> resolves to a section enrollment. pct_proficient is the source-agnostic
> headline; scale_score is null for Illuminate rows and percent_correct is null
> for every other source. response_type splits scores into overall, standard and
> group rows: standard is Illuminate only, and group covers Illuminate, i-Ready
> and DIBELS. There is no growth measure. The Date members resolve for every
> source but read different dates: the administration date for Illuminate and
> college, the test date for state tests and vendor diagnostics, so a cross-
> source date cut mixes the two. Contains direct student identifiers; see
> access_policy for PII gating.

`ai_context:` (1,050 of 2,000 characters):

> Totals will not reconcile to vendor-diagnostic or state reports, because of
> enrollment scoping; i-Ready Outside Round sittings lose the most, so treat
> those counts as a floor. Coverage is uneven by region, source and year, and a
> source's first year can be partial; check volume by region and year before
> calling a narrow result a failure or trending across a boundary. A gap between
> two instruments on the same students is a calibration difference until shown
> otherwise: report both rates side by side and flag it rather than presenting
> an achievement gap. Any growth figure is analyst-built; say so. Students can
> sit a diagnostic more than once in a window, mostly i-Ready; de-duplicate
> repeat sittings before any student-level count, and since which sitting counts
> is an open decision, say which you kept. A missing current-year state result
> is a release lag, not a defect. Query this view, not upstream i-Ready tables,
> which carry re-pull duplicates. A CCSS code's own grade can differ from
> grade_level_tested; that is spiral review, not an error.

The lead-teacher and `is_foundations` sentences live in view overrides (above).

Measured 2026-09-28, behind the repeat-sittings sentence: student-windows with
more than one test date are 2.6% on i-Ready, 0.4% on STAR, and 7 of about 61,000
on DIBELS.

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

| Reference text                                                                                                                                                                                                                          | Goes to                                                                                                                                                                                                                                            | Sieve step |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| Shared, "Filter a genuinely nullable field with `set` / `notSet`, never `equals "null"`"                                                                                                                                                | `load` docstring                                                                                                                                                                                                                                   | 4          |
| Shared, "A dimension-only pull silently de-duplicates"                                                                                                                                                                                  | `load` docstring                                                                                                                                                                                                                                   | 4          |
| Shared, "Section/teacher rollups" ("force-refresh `meta` if the lead-teacher fields appear to be missing")                                                                                                                              | `meta` docstring                                                                                                                                                                                                                                   | 4          |
| Shared, "Time" ("use `academic_year_label` as the canonical year filter")                                                                                                                                                               | present in the shipped `dates` descriptions and the `load` crosswalk; the markdown line is deleted. No `ai_context` is written on `dates`: Step 0 placed guidance there only for the test, and the crosswalk's one home stays the `load` docstring | 4          |
| Shared, "Performance bands" — the band-set table                                                                                                                                                                                        | stays, corrected and without volumes, until #5573 ships band-set members; it notes that the table describes `overall` rows, and `standard` and `group` rows may use a different band scale                                                         | 1          |
| Point-in-time figures: Text Study's score volume; the Outside Round and Newark loss shares; QA3's subject count; the median test dates; the repeat-sitting rate; the Fall NJGPA counts; STAR's yearly volume; the adaptive window dates | deleted; the qualitative claim stays in its row                                                                                                                                                                                                    | 1          |
| Coverage specifics: Paterson's sources and years; i-Ready's regions; DIBELS and STAR start years; the Newark 2025-26 module-code example; FL is Miami                                                                                   | deleted; the view says coverage is uneven                                                                                                                                                                                                          | 3          |
| Shared, "Two different subject fields" — "At K-2, `Text Study` is the _only_ ELA-equivalent subject present"                                                                                                                            | stays; evidence for the open ELA decision                                                                                                                                                                                                          | 2          |
| Shared, "Open decisions"; i-Ready, which sitting is authoritative; NJ, whether NJDOE reset the adaptive cut scores                                                                                                                      | stays, and gains the 2 questions this review added: whether a DIBELS Tested Out subtest counts as proficient, and what TP, ET and WPP stand for (see _Open questions for the network_)                                                             | 2          |
| The i-Ready, DIBELS and STAR provenance notes ("Documented from the live schema …")                                                                                                                                                     | stays                                                                                                                                                                                                                                              | 2          |

### Stays in the markdown

The standing protocol, calibration gate, session log and Drive filing, PII
delivery rules, the open-decision list, and the modeling and deliverables rules.
The routing section shrinks to the assessment-family hints and a pointer to
`meta`, since the per-source sections it routes to no longer exist.

## Open questions for the network

Policy and definition questions this review turned up. None is decided here.
Cube text says each one is open and never states a default (placement step 2).
Each also goes on the orchestrator's _Flag, don't invent_ list
(`assessment-cube-orchestrator.md`), so the working group sees it.

| Question                                                                                                                                                                                          | Evidence                                                                                                                                                                                                                                              | Who can answer                                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Which `academic_subject` labels count as "math" and which as "ELA"? Already on the orchestrator's list.                                                                                           | Labels differ by source: state uses English Language Arts and Mathematics, i-Ready and STAR use Math and Reading, DIBELS uses Reading, Illuminate uses Text Study and course names. At K-2, Text Study is the only ELA-equivalent Illuminate subject. | Teaching & Learning                                       |
| Should a DIBELS subtest a student tested out of count as proficient?                                                                                                                              | `Tested Out` rows carry no `is_mastery`, so `pct_proficient` leaves them out of the denominator entirely.                                                                                                                                             | Teaching & Learning                                       |
| What do the Illuminate module types TP, ET and WPP stand for?                                                                                                                                     | Titles suggest Test Prep, Exit Ticket, and a Literacy writing task; UA is documented as Unit Assessment.                                                                                                                                              | Whoever maintains the Illuminate assessments AppSheet app |
| Should grade-band reporting key on the student's `grade_level` or the assessment's `grade_level_tested`? Already on the orchestrator's list.                                                      | The 2 disagree where both are populated, and `grade_level_tested` is null for vendor diagnostics and NJSLA end-of-course tests, so the choice changes results and coverage.                                                                           | Teaching & Learning                                       |
| When a student sits the same diagnostic more than once in a window, which sitting counts? Already on the orchestrator's list; most recent by date is the working convention, not ratified policy. | Repeat sittings are 2.6% of i-Ready student-windows, rare on STAR and DIBELS. Skipping the de-duplication inflates student-level counts and growth figures.                                                                                           | Teaching & Learning                                       |

## YAML description changes

The per-member drafts are the single source of the new wording. This section
lists what is wrong in the shipped text today, so a reviewer can see why each
member changes. Checked against `main` on 2026-09-28 and 2026-09-29.

Shipped text that is wrong or incomplete:

- `module_type`: "e.g., QA, CR". The values are an open list of about 28; see
  the `module_type` draft.
- `module_code`: "e.g., QA1, ELA05, sat_total_score". The code means something
  different per source; see the `module_code` draft.
- `is_internal_assessment`: "FALSE for state and college". It is FALSE for the
  i-Ready, DIBELS and STAR diagnostics too.
- `grade_level_tested`: "Null for college-entrance assessments". It is null for
  every vendor diagnostic and for the NJSLA end-of-course tests.
- `administration_period`: omits every vendor value, and the reference file
  gives NJ as Fall, Winter and Spring, where NJSLA is Spring only.
- `academic_subject`: lists English Language Arts as a plain example. Illuminate
  has no such value, and i-Ready, STAR and DIBELS use Math and Reading.
- `response_type_code`, `response_type_description` and
  `response_type_root_description`: each says only "Null for state". Each is
  null across a different and much larger slice (table below).
- `performance_band_label_number`: "Null for state assessments". It is
  Illuminate only, and not comparable across assessments or response types.
- `count_taken` and `count_scored`: attribute the DIBELS rows with no verdict to
  "K-2 phonics subtests have no benchmark level set upstream". They are the
  `Tested Out` rows.
- `date_taken`: says "internal" and "vendor" where it means Illuminate and the
  named diagnostics.
- The view description: "response_type / response_type_code carry the
  standard/skill breakdown (Illuminate only)". i-Ready and DIBELS carry `group`
  rows too.
- The instructions #5508 wrote into `description:` on `response_type`, the 3
  counts, `pct_taken` and `pct_proficient` move to `ai_context`.

Where the 3 `response_type_*` members are populated, measured 2026-09-23:

| Member                           | Populated on                                    | Null on                                                       |
| -------------------------------- | ----------------------------------------------- | ------------------------------------------------------------- |
| `response_type_code`             | `standard`, plus `group` for i-Ready and DIBELS | every Illuminate `group` row, and all `overall` / `not_taken` |
| `response_type_description`      | `standard` and every `group`                    | all `overall` / `not_taken`                                   |
| `response_type_root_description` | Illuminate `standard` only                      | every i-Ready, DIBELS, STAR and state row                     |

`response_type_code` is null on all 2,797,958 Illuminate `group` rows while
`response_type_description` is populated on them, so a standards-cluster cut
keyed on the code silently drops every Illuminate group row.

### Schema tests

`tests/cube/test_cube_schema.py` loads the YAML and asserts 4 things:

1. One key phrase per moved fact, keyed by member name, so a later edit cannot
   drop a fact silently.
2. Each Cube member that reads one column directly has a `description:` equal to
   that column's dbt `description:`.
3. Every `ai_context` in `src/cube/model/`, including view overrides, is 2,000
   characters or less.
4. No view override hides a cube-level `ai_context`: an override on a member
   whose cube member carries `ai_context` must contain that text.

A local Cube server compiles the branch's model and serves it over REST before
merge; the `ai_context` check above runs against it.

## Server changes

### Docstrings

The quoted sentences are the docstring text. Everything else in this subsection
is the reason for it and stays in the spec: docstrings are resent on every tool
call, so they carry the instruction only.

`load` gains 3 sentences, each added to an existing paragraph:

- **Filter operators paragraph:** "`equals "null"` matches the literal string
  and returns zero rows; filter a null with `notSet`."
- **Grain paragraph:** "A query with no measure groups by its dimensions, so
  identical rows collapse into one; add a count or the primary key to see every
  row." A Cube query with only dimensions works like `SELECT DISTINCT`, so a
  student with 2 identical sittings comes back as 1 row and nothing says rows
  were merged. The `count_students` fallback lives in that member's
  `ai_context`, not here. During the build, check whether Cube's `ungrouped`
  query option works on these views; if it does, name it as a third fix.
- **PII paragraph:** "Student views return only the schools the user can access;
  before describing a result as network-wide, check which regions or schools it
  covers." The row-level filter is silent, so a school- or region-scoped user
  asking a network question gets real, non-empty numbers for their own slice,
  and nothing else in the response says so.

`meta` gains 2 sentences:

- "Refresh before concluding a member is missing."
- "Members may carry `meta.ai_context` (`aiContext` on some view-specific
  members): usage rules written for you. Read and follow a member's `ai_context`
  before building a query that uses it." This is the pointer tested in _Step 0_,
  added as a judgment call; the second spelling covers view overrides.

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
  must avoid. 6 are checked on the captured `load` query:
  - an i-Ready question by grade: must filter `grade_level`, not
    `grade_level_tested`
  - "how many STAR scores have no proficiency level?": must filter with
    `notSet`, not `equals "null"`
  - a "QA3 math" question: must pair `module_code` with a subject filter
  - a "vendor diagnostics" question: must not select on `is_internal_assessment`
  - an "all internal checkpoints" question: must not use
    `pct_proficient_formative` alone
  - a "most recent diagnostic" question: must scope to a named round
- 1 is checked on the answer text, and labeled as the only answer-scored trap: a
  Paterson i-Ready question must report coverage, not zero as a failure. The
  `load` stub returns 0 rows for it, and in arm B only it returns the server's
  empty-result note too, so the eval exercises the note.
- `scorer.py` reports a trap rate per arm with Wilson intervals, as today.
- Both arms' catalogs come from the same Cube-compiler script used in the
  override test: arm A compiles `origin/main`'s YAML from before the PR's first
  description change, and arm B compiles the branch. The output is committed as
  `eval/fixtures/meta_pre_drain.json` and regenerated for arm B on each run.
  Both arms use the real `server.py` docstrings; arm A substitutes the pre-drain
  `load` paragraphs by anchor, the same mechanism the crosswalk arm uses.
- The stub's canned `load` rows take the assessment view's shape; today they are
  attendance-shaped.
- The runner stays hermetic per `eval/README.md`, and runs on Haiku only, the
  weaker model and the one where Step 0 found headroom.

Every run records, per conversation, what the Agent SDK's `ResultMessage`
reports and the runner discards today: tokens in and out (with cache),
`total_cost_usd`, `num_turns` and `duration_ms`, beside the tool calls already
captured. The report gives each arm its median tokens, cost per conversation,
turns and tool calls, and also the character size of the full-catalog and
assessment-view `meta` responses before and after. Eval timing is not production
timing, because Cube is stubbed; #5613 measures real latency.

A third arm sizes the planned org-level skill without building it: **arm C** is
arm B plus the trimmed orchestrator as the system prompt. The gap between B and
C shows what process and recipes add beyond Cube text, and the traps C wins are
the recipes worth writing. Arm C reports; it does not gate.

The gate runs on Haiku. The before/after report adds one small Sonnet run of
family 4, arms A and B only: 7 prompts, 3 reps, 42 conversations.

The eval runs once the descriptions, docstrings and `count_assessments` are all
on the branch. Rules, written before any run:

1. Arm B passes when its pooled family 4 trap rate is lower than arm A's.
2. If it does not, revise the description text and rerun, at most 2 rounds.
3. After 2 rounds, record the result. Merge only if arm B is no worse than arm
   A, and open an issue for each trap arm B still fails.

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
2 fires: keep the split. The 3 placements are indistinguishable at this sample
size (0 of 60 wrong against 1 of 60; Fisher exact p = 1.0).

**Decision, 2026-09-29: add the pointer anyway, as a judgment call.** This
overrides rule 2's "without the pointer"; the eval did not show the pointer
helps. The reasons are not in the data. The pointer costs one sentence. It is
the only mechanism that gives `ai_context` meaning to an agent, the same one the
third-party Cube MCP server uses. And the real `ai_context` values carry
instructions that matter more than this test's crosswalk. The local REST check
before merge confirms the pointer's key names match what `/meta` returns.

| Arm          | Wrong year (95% interval) | Correct | No query |
| ------------ | ------------------------- | ------- | -------- |
| `F0_none`    | 28.3% [16–45]             | 71.7%   | 0%       |
| `F1_desc`    | 0.0% [0–7]                | 100%    | 0%       |
| `F2_ctx`     | 1.7% [0–10]               | 96.7%   | 1.7%     |
| `F3_ctx_ptr` | 0.0% [0–7]                | 96.7%   | 3.3%     |

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

The local REST check ran 2026-09-29 on Cube 1.7.43. The 2 overrides come back as
`aiContext` on their view members only, and 25 members carry `ai_context`. The
full `meta` catalog grows from 305,495 to 321,857 bytes (+5.4%), and the
assessment view's entry from 47,216 to 55,652 (+17.9%).

### Family 4 result

Arm B passes rule 1 on Haiku after 1 revision round. The Sonnet report run
agrees. Run 2026-09-29, 7 prompts, 3 reps, 21 conversations per arm.

Trap rate over all 7 traps, with Wilson 95% intervals clustered on prompt (see
the 2026-10-01 revision below):

| Arm        | Haiku                | Sonnet             |
| ---------- | -------------------- | ------------------ |
| `A4_pre`   | 28.6% [6–73]         | 23.8% [5–67]       |
| `B4_post`  | 4.8% [1–30]          | 0.0% [0–22]        |
| `C4_skill` | 10.0% [2–36], n = 20 | 0.0% [0–76], n = 6 |

- **What B fixed.** On Haiku, `null_via_equals` went from 3 of 3 to 0 and
  `most_recent_not_named_round` from 3 of 3 to 1. On Sonnet,
  `grade_filter_on_vendor` went from 3 of 3 to 0 and `most_recent` from 2 of 3
  to 0.
- **What B still misses.** Haiku's 1 remaining fire is `most_recent`. On its
  first query, B still trips a trap 17% of the time on both models, then
  corrects itself after reading `meta`.
- **Arm C adds nothing measurable.** On Haiku it fires the Paterson trap 1 of 3
  times, where B fires it 0 times; that one conversation asked which benchmark
  window was meant and never reached the empty result. On Sonnet, 15 of C's 21
  conversations hit the account's session limit and are not scored, so its 6
  scored conversations settle nothing.
- **Cost.** B reads more `meta` text, and costs about the same per conversation.
  Median per conversation: Haiku A $0.042 and B $0.048; Sonnet A
  $0.143 and B $0.141. B's cache-read tokens are higher (Haiku 11,768 to 28,634;
  Sonnet 76,647 to 106,495) because cached input is cheap.

Round 1 changed 2 things at once, so its effect is not attributed to either:

- **The stub.** The first run's `load` stub returned the same fixed row for
  every query. Models noticed the fake data and probed with other filters, which
  tripped traps the text had avoided. That run scored Haiku A 33.3% against B
  44.4% on the 6 query traps, and Sonnet A 42.9% against B 19.0% on all 7. The
  stub now shapes its rows from the query.
- **The text.** `proficiency_level`, `administration_period` and `date_taken`
  gained the `notSet` and "latest named round" wording.

The scorer was amended twice after the Sonnet run, before these numbers were
written. Neither change moves arm A or B:

- A conversation the harness cut off with an error, other than the 12-turn
  limit, is left out of the trap rate. This drops 15 of arm C's Sonnet
  conversations. Conversations that hit the turn limit still score, because
  their queries were captured (2 in A and 3 in B on Sonnet).
- A query-scored trap on a conversation that never queried the view is left out.
  With no query, 4 of the 6 query predicates read a pass and 2 a fire, so the
  outcome means nothing. This drops 1 of arm C's Haiku conversations. Every A
  and B conversation queried the view on both models.

The final code review then found the round-1 `proficiency_level` sentence wrong
for DIBELS: DIBELS rows with no verdict carry `Tested Out`, not null, so
`notSet` finds almost none of them. The sentence now scopes `notSet` to STAR and
sends "no verdict" to `is_mastery`. The run above measured the text before that
fix; the `null_via_equals` prompt asks about STAR, so its trap reads the same
guidance either way.

Revised 2026-09-30, after the `claude-review` pass tightened 3 predicates:
`null_via_equals` also accepts `is_mastery` `notSet`;
`most_recent_not_named_round` needs `equals` on exactly 1 named round; and
`paterson_zero_as_failure` no longer passes on a bare "coverage", but does pass
an answer saying Paterson is absent from the data. Re-scoring the saved records
moves 1 cell: Haiku arm C drops from 15.0% [5–36] to 10.0% [3–30]. The old
predicate fired on a conversation that reported Paterson "not present in the
current assessment scores view", a phrasing none of its patterns matched. Arms A
and B are unchanged on both models.

Raw records: `src/cube/mcp/eval/out/family4_{haiku,sonnet}_r1.jsonl`
(gitignored, local only).

Revised 2026-10-01: the intervals in both tables above are now clustered on
prompt. The old Wilson interval pooled every rep of every prompt as an
independent trial, but reps of one prompt are correlated, so it was too narrow.
`scorer.py` now uses the Korn-Graubard effective sample size and a Student-t
critical value with `prompts - 1` degrees of freedom, ported from Inspect AI's
`ci_wilson(cluster=...)`. Recomputed from the saved records, not rerun. Point
rates are unchanged, and so are both decisions: placement rule 2 still fires,
and the family 4 pass rule compares point rates. With 7 trap prompts the family
4 intervals are wide, and arm A's and arm B's overlap on both models. Earlier
intervals quoted in the revision notes above are the pooled ones.

### Why family 4 is small

7 traps against about 50 facts looks like a sample. It is closer to the whole
set. A trap is a predicate over a captured query, so a fact can become one only
when the query alone proves the violation. The Paterson trap is the one
exception: it checks the answer text for a coverage statement, a narrow phrase
check rather than a judgment of the answer. The facts split 3 ways:

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

The real dependency is **attribution and question text**, which #5613 provides:
one logged row per Cube MCP call, with `staff_key`, `question`, `query_json`,
`members_referenced`, outcome and `server_sha`. Its phase 1 (PII-free, no
question text) is unblocked; phase 2 adds `question` and `query_json` after a
retention decision. Once `query_json` is logged, each trap becomes a standing
detector instead of a pre-merge gate. That matters because the eval proves the
descriptions work on 7 written prompts, not on what people actually ask or on
whether they still work in November.

The Paterson trap cannot move to production this way: it is answer-scored, and
#5613 does not log answers. It stays an eval-only check.

The only obligation this spec takes on is keeping the trap predicates importable
rather than inlined in the scorer's main loop.

Once those monitors exist, each checkable fact has a definition of done: its
trap stops firing. That holds only for the malformed-query third. A correct
query that is misread leaves nothing to detect, so those facts stay
documentation.

## Project-knowledge trim

The open decisions have one home: the orchestrator's _Flag, don't invent_ list
(`assessment-cube-orchestrator.md`, 15 items). The reference file's shorter
"Open decisions" bullet repeats 7 of them and is deleted.

- **`assessment-cube-reference.md`.** The PR deletes every fact it moved. The
  K-2 `Text Study` evidence moves to the orchestrator, beside its open ELA
  decision, and the 3 provenance notes go with their facts. What remains is the
  corrected band-set table, with its `overall`-rows caveat. #5573 deletes that
  table, and the file with it, leaving the Project on one file.
- **`assessment-cube-orchestrator.md`.**
  - _Flag, don't invent_ gains the 2 questions this review added: whether a
    DIBELS `Tested Out` subtest counts as proficient, and what TP, ET and WPP
    stand for. The second is a documentation question for whoever maintains the
    Illuminate assessments AppSheet app, not a policy one, and says so.
  - Protocol step 3 changes from "filter `response_type` explicitly" to "confirm
    `response_type` from `meta`".
  - Every pointer into the reference file becomes "see the member's description
    in `meta`": step 3's "(Shared conventions)", the NJSLA item's "(NJ state)",
    and "called out inline in `assessment-cube-reference.md`".
  - _Routing_ keeps the region hint, the assessment-family hint and "ask before
    querying". The 7-section map goes, since those sections no longer exist.
  - The session-log and Drive-filing protocol stays untouched. #5613's server
    log retires most of it once its phase 2 ships; that issue lists which parts
    go and which judgments (confidence, inference flags) it keeps.
- **`README.md` in that folder** gains a step: after the PR merges, re-upload
  the changed files to the Project. Its update loop says a field fact goes to
  the Cube YAML, a query mechanic goes to `server.py`, and only protocol or
  policy goes to these files.

## PR and validation

#5495 carries all of it, this spec included, and closes #5236. Validation runs
against our own path: the MCP server and Cube's REST API, on a local Cube server
at the pinned version for anything the model serves.

| Change                                                             | Validation                                                                                                                                      |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Step 0                                                             | done 2026-09-29; result recorded under _Step 0_                                                                                                 |
| Descriptions and their dbt twins, `ai_context`, the authoring rule | `uv run pytest tests/cube/` (the 4 schema tests); dbt Cloud CI passes                                                                           |
| The 2 view overrides                                               | schema test 4; the local REST check shows each as `aiContext` on its view member only                                                           |
| `ai_context` reach and size                                        | the local REST check; `meta` response sizes recorded before and after                                                                           |
| `load` and `meta` docstrings, empty-result note                    | `uv run pytest tests/cube/`                                                                                                                     |
| `count_assessments`                                                | a local REST `/load` returns quartile-shaped counts (1, 1, 2, 3 per standard-year, measured 2026-09-22)                                         |
| Reference and orchestrator trim                                    | every deleted fact has a home in the diff; the 2 new questions are on _Flag, don't invent_; no pointer into a deleted section survives (`grep`) |
| All of it                                                          | eval family 4 passes per its rules, at most 2 revision rounds; arm C and the Sonnet report run are recorded but do not gate                     |

The PR body carries the markdown lines it deleted, so a reviewer can see each
fact beside its new wording.

## Out of scope

- Band-set columns: #5573.
- `assessment_family`: #5574.
- The canonical standard code: #5575. Fixing the upstream standards crosswalk
  instead is a separate issue, noted there.
- Partitioning `fct_assessment_scores_enrollment_scoped`, and finding why
  `proficiency_rollup` serves nothing: #5557.
- Building the org-level claude.ai skill. The trimmed orchestrator is its first
  draft, and eval arm C sizes what it would add; the skill itself is later work.
- The Cube MCP call log, and retiring the Project's session-log protocol: #5613.
- Answering the open questions under _Open questions for the network_: Teaching
  & Learning, plus whoever maintains the Illuminate AppSheet app for TP, ET and
  WPP.
- Agents that query Cube through the SQL API; see _The supported agent path_.
- `pct_proficient_formative` semantics. Whether to widen it or add a
  module-coded rollup is a pooling decision on the open-policy list.
- Any change to `int_assessments__response_rollup` or the reports that read it.
