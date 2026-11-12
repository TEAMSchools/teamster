# Region-aware roll-up for internal assessments

Closes #6308.

## Intent

Internal Illuminate assessments that carry the same tags (school year, scope,
subject, module code, grade) roll up into one group. That is by design: it is
how the parts of a multi-part assessment, and alternate versions, become one
result per student.

The region tag (`regions_assessed`) was added after the roll-up was built, and
the roll-up never took it into account. When Camden and Newark each have their
own copy of a module, both copies land in one group, and the copy with the
lowest `assessment_id` supplies the group's title, date, band set and report
card tags for every region. The region whose copy was not created first then
shows:

- another region's title and date, so its scores sit in the wrong week on the
  DDI weekly views and the wrong quarter under the Term filter;
- a section lookup on a date the student did not sit the test, which drops a
  small number of scores from the scores fact;
- another region's report card and progress report tags, which today leaves
  Camden's grade 1 and 2 literacy assessments off Camden's feeds;
- another region's performance band set (see _Open items_).

The Data Team decided that the whole roll-up becomes region-aware, not only the
date: two copies combine for a region only when both are tagged for that region.

## Decisions

| Decision                                                                                                                                                                                                     | Source             |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------ |
| The roll-up is regional. A region's group is every identically tagged copy whose `regions_assessed` lists that region. A copy tagged for several regions sits in each of those regions' groups.              | Decided 2026-11-12 |
| A regional group's ID is the lowest `assessment_id` among the copies tagged for that region.                                                                                                                 | Decided 2026-11-12 |
| Rejected: grouping copies only when their region lists match exactly. It splits one combined score in two for about 2,500 student-assessments in SY25-26 and 1,400 in SY26-27.                               | Decided 2026-11-12 |
| The Assessment Dashboard shows one row per regional assessment. No workbook change ships with this.                                                                                                          | Decided 2026-11-12 |
| Scores whose section cannot be resolved are the resolver working as designed. No resolver fallback, no "first copy with sittings" rule, no clean-up of old-year dates, and no anchor-count acceptance check. | Decided 2026-11-12 |
| Replacement scores missing from the scores fact get their own issue.                                                                                                                                         | Issue #6308        |

## Goals

- Two copies combine for a region only when both are tagged for that region.
- Each region's scores carry the title, date, and report card and progress
  report tags of that region's own first copy.
- No student's combined score changes: the set of copies rolled into each
  student's result, and its percent correct, are the same before and after.
- Every key derived from the group ID is hashed from the same ID and date by its
  producer and all of its consumers.

## Non-goals

- Correcting tag errors, such as a WPP2 copy tagged WPP 1. Those are on the
  tagging work list and are fixed in the tagging app.
- Changing the section resolver or the scaffold's course enrollment join
  (`between`), including making it half-open.
- The replacement-score gap.
- Removing `is_florida_assessment` from the tag grouping. Miami-only copies
  already group apart, and their group IDs do not change under this design.
- Tableau workbook changes.
- An override for Camden's Literacy G1 UA2, which moves to Camden's Q2 because
  Camden gave it on November 9, 2026.

## Anti-goals

- A student's combined score splitting into two results.
- One column name, `canonical_assessment_id`, carrying two meanings (the tag
  group on one model, the regional group on another).
- A producer and a consumer hashing different group IDs or dates. No mart test
  catches an orphaned key.

## Constraints

- A5: `int_assessments__score_anchors` holds an existing `row_number() = 1`
  pick. Do not edit inside it. It needs no edit, because its date comes from the
  canonical model by group ID.
- Hash-change discipline (`src/dbt/kipptaf/models/marts/CLAUDE.md`): the group
  ID and date are hash inputs to `assessment_administration_key` and to the
  score key. Producer and every consumer change in one commit.
- Key churn is unavoidable for the regions that get a new group ID. Issue #6308
  asked to keep `c.administered_date` as the hash input to avoid churn; that
  held for a date-only fix and does not hold here.
- The assessment intermediates and marts are tables on one cron tick. Cube's
  `proficiency_rollup` pre-aggregation follows the scores fact's rebuild only
  for partitions from July 1 of the previous school year onward. Older
  partitions, which hold SY24-25's 12 split groups, rebuild only by hand in Cube
  Cloud.
- Never bare `dbt`; always `uv run`.

## Approaches

1. **A per-region date only.** Keep one group per tag set and give each region
   its own date. Smallest change and no key churn beyond the date. It leaves the
   title, band set and report card tags coming from another region's copy.
   Superseded by the decision above.
2. **A regional group ID from a copy-by-region crosswalk (chosen).** Keep the
   members model at one row per copy. Add one model at one row per copy and
   region that carries the regional group ID. Every consumer that needs a group
   reads it there or from the scaffold, which already works at that grain.
3. **Change the members model's grain to copy by region.** One model instead of
   two, but every copy-grain consumer (`rpt_appsheet__assessments`, the two tag
   audits, `dim_assessments`, the band model) would have to collapse it again.

## Design

### Terms

- **Tag group**: copies sharing source, internal flag, Florida flag, school
  year, scope, subject, module code and grade. This is today's grouping,
  unchanged. Its ID is the lowest `assessment_id` in it.
- **Regional group**: within a tag group, the copies tagged for one region. Its
  ID is the lowest `assessment_id` among them.

When a tag group's first copy is tagged for a region, that region's regional
group ID equals the tag group ID, so nothing changes for it.

### 1. `int_assessments__assessments_members`

Grain unchanged: one row per source and `assessment_id`.

Rename `canonical_assessment_id` to `tag_group_assessment_id`. The values do not
change. The rename makes every reader of the old column fail to compile until it
is pointed at the right group, which is the point: a reader left on the tag
group silently keeps the cross-region roll-up.

### 2. New `int_assessments__assessment_region_groups`

A build model (a crosswalk) at one row per source, `assessment_id` and region,
for internal assessments. It is the one place the regional rule lives.

```sql
select
    m.source,
    m.assessment_id,
    m.tag_group_assessment_id,

    region,

    min(m.assessment_id) over (
        partition by m.source, m.tag_group_assessment_id, region
    ) as canonical_assessment_id,
from {{ ref("int_assessments__assessments_members") }} as m
cross join unnest(m.regions_assessed_array) as region
where m.is_internal_assessment
```

Apex rows pass through unchanged: each is its own tag group with region Miami.
Uniqueness test on source, `assessment_id` and region.

### 3. `int_assessments__assessments_canonical`

Grain unchanged: one row per source and `canonical_assessment_id`. The set of
IDs becomes every regional group ID from the crosswalk plus every tag group ID.
A tag group ID that is no region's group (its first copy has no region tagged)
keeps its row with an empty `regions_array`, so the replacement fallback below
still finds a title and date.

- Attributes (title, date, subject, scope, module code, year, grade) come from
  the copy whose `assessment_id` is the group ID. The row is determined, so the
  `dbt_utils.deduplicate` pick is no longer needed.
- `regions_array` becomes the regions whose regional group this ID is. Today it
  is every region tagged anywhere in the tag group.
- Add `tag_group_assessment_id`.

`dim_assessment_administrations` reads this model fanned by `regions_array`. Its
SQL does not change, and it now yields one administration per regional group and
region, dated by that region's first copy.

### 4. `int_assessments__scaffold`

- `assessment_region_scaffold`: join the crosswalk in place of the `unnest`, and
  take `canonical_assessment_id` from it. Students are already rostered only to
  copies tagged for their region, so rows and rostering do not change.
- Replacement branch: the student's region comes from their school. Look up the
  regional group for the copy's tag group and that region in the canonical
  model. When one exists, use its ID and set `is_region_tagged` true. When none
  exists, fall back to `tag_group_assessment_id` and set it false, which matches
  today's value.
- Non-internal and Apex branches: `canonical_assessment_id` is the copy's own
  `tag_group_assessment_id`. Values do not change.

The score anchors, section resolver and scores fact read the group ID from the
scaffold and the date from the canonical model, so they follow without logic
changes, apart from the joins named below. The response roll-up follows for the
group ID, title and date; its band lookup changes as described next.

### 5. `int_assessments__performance_bands` and the roll-up's band lookup

Depends on open item 1. As recommended there, only the band set becomes
regional:

- **Rule.** A score is labeled from the band set on its regional group's first
  copy. For a standard or reporting group, that is the first copy in the group
  that carries it. A replacement row uses the group the scaffold assigned it.
- **The standard merge stays on the tag group.** `canonical_response_type_id`
  keeps its window over the tag group. It is only a representative ID for the
  same standard across copies. Making it regional could change
  `response_type_id`, and with it the score key, for regions whose group ID does
  not change.
- **The roll-up's join moves.** `int_assessments__response_rollup` joins the
  band model in `responses_keyed`, on single sittings that carry no group yet,
  and aggregates on the band set before the scaffold join. The band set lookup
  has to happen once the group is known. `rpt_deanslist__mod_standards` reads
  the band set through the roll-up's group ID and follows the same rule.

If the decision goes the other way, the band model only swaps
`canonical_assessment_id` for `tag_group_assessment_id` and nothing else moves.

### 6. Marts

- `fct_assessment_scores_enrollment_scoped`: the roll-up's `assessment_id` is
  the group ID. Join the canonical model on it directly instead of through the
  member's own group column. Raw `academic_year` and `module_code` still come
  from the member row for that ID.
- `bridge_assessment_administration_members` is disabled, so it does not compile
  and the rename will not flag it. Update its SQL to read copy, region and group
  ID from the crosswalk anyway, so it is right if it is re-enabled. It stays
  disabled and is not part of verification.
- `bridge_assessment_expectations_student_scoped` and
  `bridge_assessment_expectations_enrollment_scoped`: take the group ID from the
  scaffold row, not from the member's own group column.
- `dim_assessments`: member grain, and its key does not hash the group ID, so no
  key changes. It joins the canonical model only for the grade, which is the
  same for every copy in a tag group.

Key effects: `assessment_administration_key` and the score key change for rows
whose regional group ID differs from today's group ID. `assessment_key` on the
fact moves to the regional first copy's existing `dim_assessments` row. No
column is added to or removed from a mart, so the Cube model files need no edit.

### 7. One reader outside the assessment star

`int_assessments__college_assessment_practice` (CARAT practice SAT and ACT
scores) joins the roll-up's group ID to a hand-kept conversion sheet. A practice
test in a group that splits would need its new ID on the sheet. None of the 11
practice IDs sits in a split group today (checked 2026-11-12). No change is
needed; verification re-checks it.

### 8. After merge

- All changed tables rebuild in one pass so keys agree.
- The Data Team rebuilds the `proficiency_rollup` partitions before July 1, 2025
  by hand in Cube Cloud, so SY24-25 picks up its new keys and dates.

### 9. Tests, docs and skill

- Update `int_assessments__assessments_members__no_cross_source_canonical`,
  `int_assessments__scaffold__replacement_region_untagged` and the properties
  files that name the renamed column.
- `docs/models/ddi-stack-data-model.md`: replace the decision "Canonical
  grouping by attributes, not region" and the terms that describe the group.
- `.claude/skills/ddi-stack/references/tagging.md`: rewrite "Canonical
  grouping", including the Florida note. `report-cards.md`: the gate now reads
  the tags on the region's own first copy.

## Size of the change in data (prod, 2026-11-12)

| Year    | Tag groups that split by region | Student-assessments that get a new group ID |
| ------- | ------------------------------- | ------------------------------------------- |
| SY24-25 | 12                              | 1,177                                       |
| SY25-26 | 37                              | 13,735 of 404,150                           |
| SY26-27 | 15                              | 2,708 of 219,723                            |
| Earlier | 0                               | 0                                           |

All but one of the 52 groups in the last two years are Camden's own copy against
Newark's, or Newark and Paterson's. The 12 in SY24-25 are Camden high school
copies. The full list is on the Regional dates tab of the tagging work list
(Google Sheet "DDI assessment tagging fixes (SY25-26 and SY26-27)").

## Verification

1. **Combined scores do not change.** For internal, non-replacement rows of the
   response roll-up, compare the branch build to prod on student, the sorted
   list of member copies (`assessment_ids`) and response type. Row counts and
   percent correct match exactly.
2. **Only the expected rows get a new group ID.** Rows whose group ID differs
   from prod fall only in the tag groups listed above, and each row's region is
   tagged on its new first copy.
3. **Keys resolve.** Every internal `assessment_administration_key` on the
   scores fact and on the two expectation bridges exists in
   `dim_assessment_administrations`. Check counts, not compilation. For rows
   whose group ID does not change, the score key matches prod.
4. **Report cards.** Camden's grade 2 literacy domain rows appear for the
   students who lack them today (172 on 2026-11-12), and grade 1 and 2 literacy
   progress report rows appear (141 and 173). A replay of the feed logic matched
   the published feed exactly, so the same replay against the branch build is
   the check.
5. **Dates.** Literacy G3 ET3 (SY25-26): Newark and Paterson scores carry
   January 28, 2026, and Camden's carry September 22, 2025.
6. **Uniqueness tests** pass on the crosswalk and on every model whose grain is
   named above.
7. **CARAT.** No practice SAT or ACT ID on the conversion sheet sits in a group
   that splits.
8. **Bands, if open item 1 is yes.** Mastery changes only in the modules listed
   there, and replacement rows keep a band set.

## Left to the builder

- The final name of `tag_group_assessment_id` and of the crosswalk model.
- Whether the crosswalk needs a grain-projection `distinct` for a region typed
  twice in one tag, and how the empty-string region that a trailing comma
  produces is carried. Keep today's behavior for both.
- The exact join shape for the replacement branch's regional lookup.
- Whether `dim_assessments` keeps its canonical join or reads the grade from the
  member row.
- The rebuild after merge: all changed tables must rebuild in one pass so keys
  agree. Confirm how the deploy triggers that, per
  `src/dbt/kipptaf/models/marts/CLAUDE.md`.
- Follow-up issue for the replacement-score gap.

## Open items

1. **Should performance bands follow the regional group?** Today the tag group's
   first copy supplies the band set for everyone. In 11 of the 52 split groups
   the regional copies carry different band sets, and in 9 of those the cut
   points differ. If bands become regional, 130 overall results change mastery:
   67 in SY26-27 (Newark Chemistry ET 1, which today is judged by a Camden-only
   copy nobody sat) and 63 in SY25-26 across four literacy modules.
   Standard-level results were not measured. Recommended: yes, because the
   decision was that the whole roll-up is regional, and a region should be
   judged by the cut points on the test it sat. Two copies carry Illuminate's
   default band set (Camden's Literacy G4 ET1 and Newark's Literacy G7 ET1, both
   SY25-26), which looks like a setup miss; under this option those regions
   would be judged by the default set until the copy is corrected. This
   contradicts the stakeholder doc's line that no mastery result changes, so the
   doc changes with the answer.
2. **Camden Literacy G1 UA2 lands in Q2.** No override is planned. Teaching &
   Learning has not yet confirmed the quarter.

## Approval, 2026-11-12

Approved by the Data Team on 2026-11-12, with open item 1 decided:

- **Performance bands follow the regional group.** Section 5 is built as
  written: the band set becomes regional and the standard merge stays on the tag
  group.
- **It may be rolled back.** The decision is flagged to stakeholders as a
  question in the stakeholder doc. Build the band change as its own commit,
  after the group change, so it can be reverted without touching the regional
  grouping. Reverted, the band model reads `tag_group_assessment_id` and labels
  do not change from today.

Open item 2 stays open and does not block the build.
