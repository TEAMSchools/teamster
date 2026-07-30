# NJ SLEDS Student Course Roster — grade and credit backfill

Design spec for [#4630](https://github.com/TEAMSchools/teamster/issues/4630).

Extends the audit runbook in
[`docs/superpowers/nj-sleds-roster/runbook.md`](../nj-sleds-roster/runbook.md)
(branch `anthonygwalters/docs/claude-nj-sleds-course-roster-runbook`, PR
[#4281](https://github.com/TEAMSchools/teamster/pull/4281), unmerged as of this
writing) and its design spec
[`2026-06-29-nj-sleds-course-roster-runbook-design.md`](2026-06-29-nj-sleds-course-roster-runbook-design.md).

## Context

The Student Course Roster extract PowerSchool generates carries no usable grade
values and a uniformly wrong credit value. Measured against the 2026-07-29
extract loaded into `cokafor` (43,493 rows: Newark 33,150, Camden 10,343):

- `NumericGradeEarned`, `AlphaGradeEarned`, and `CompletionStatus` are empty on
  **every** row in both regions.
- `CreditsEarned` is populated on all 14,343 secondary-code rows but has exactly
  **one distinct value, `0.000`**. Every high school student currently reports
  earning zero credits toward graduation.
- Every row carries a `SectionExitDate`, so no row escapes the requirement on
  the exit-date condition.

Two causes, neither fixable at the source in the time available: customizations
in the KTAF grading model, and mapping gaps in PowerSchool's NJ state-reporting
configuration. Filing the submission is a formal certification that the data is
accurate, so the file cannot ship in this state.

### What the handbook requires

All citations are to the **NJ SLEDS Student Course Roster Submission Handbook,
Version 1.4, dated July 28, 2026** — a newer revision than the copy the runbook
was originally written against. Pages 33 through 36 state the grade requirement
four times in identical terms (overview, then once under each of the three grade
elements):

> Grades or Completion Status are required to be collected for all students in
> courses with Secondary course codes and an available credit of greater than
> 0.000.
>
> Grades or Completion Status are also required for students with
> Prior-to-secondary course codes that have a grade span of 060X and higher
> (where X is replaced with a full Grade Span such as 0606, 0607, 0608, and so
> on).

Each element's "Is this Data Element Required?" section adds the exit-date
condition: the rule applies to "all students with a `SectionExitDate` entered"
in those two populations.

Relevant domains and constraints:

| Element              | Page | Type and domain                                   | Notes                                                                                               |
| -------------------- | ---- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `NumericGradeEarned` | 34   | numeric, `0`–`100`, whole number                  | not weighted; round decimals                                                                        |
| `AlphaGradeEarned`   | 35   | `A A+ A- B B+ B- C C+ C- D D+ D- E E+ E- F F+ F-` | `E` is a grade, not "Exempt"                                                                        |
| `CompletionStatus`   | 36   | `P` `F` `W` `I` `NG`                              | `P` is **not** legal in `AlphaGradeEarned`                                                          |
| `CreditsEarned`      | 32   | numeric, `0.000`–`35.000`, min length 5           | mandatory for Secondary codes with a `SectionExitDate`; **error if greater than `AvailableCredit`** |
| `AvailableCredit`    | 27   | numeric, `0.000`–`35.000`                         | mandatory for Secondary; may be blank for Prior-to-secondary                                        |

One or more of the three grade elements must be present for a row in scope; the
handbook does not require all three.

## Decisions (load-bearing)

1. **Populate `AlphaGradeEarned`, not `NumericGradeEarned`.** Letter grades are
   what the transcript shows, and — see the data profile below — the stored
   letter grades already fall inside the handbook domain, so this needs no
   mapping table and does not re-open the grading-model customization.
2. **Pass/fail is out of scope.** `P` is illegal in `AlphaGradeEarned`, so
   pass/fail would have to go in `CompletionStatus`. The rows that would need it
   are the ones the handbook does not require a grade for. See _Contingencies_ —
   this is deliberately deferred, not overlooked.
3. **`CreditsEarned` comes from PowerSchool's own earned-credit value**, not
   from a pass/fail rule we invent. `storedgrades.earnedcrhrs` already encodes
   the outcome.
4. **Two fields only.** Every other column passes through byte-identical to the
   native extract. This is a narrow, named exception to source-fix-only, not a
   replacement for it.
5. **A view plus a thin export script**, both region-aware, living in `cokafor`
   and the repo respectively. Not a dbt model — see _Non-goals_.

## Scope

| Field              | Rows in scope | Rule                                                                                                                                              |
| ------------------ | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AlphaGradeEarned` | 28,946        | Secondary-code rows with `AvailableCredit` greater than `0.000`, plus prior-to-secondary rows whose `GradeSpan` **upper bound** is `06` or higher |
| `CreditsEarned`    | 14,343        | Secondary-code rows only                                                                                                                          |

Row counts by band, from the 2026-07-29 extract:

| Band         | Classification                                  | Newark     | Camden     | Total      |
| ------------ | ----------------------------------------------- | ---------- | ---------- | ---------- |
| HS           | `sced_level = 'secondary'`                      | 10,695     | 3,648      | 14,343     |
| MS           | prior-to-secondary, span upper bound `06`+      | 10,746     | 3,857      | 14,603     |
| Out of scope | prior-to-secondary, span upper bound below `06` | 11,709     | 2,838      | 14,547     |
| **Total**    |                                                 | **33,150** | **10,343** | **43,493** |

### The band rule, and why the upper bound

The handbook's `060X and higher` phrasing does not say which end of a grade span
is tested. Testing the **upper** bound resolves the ambiguity in the direction
that cannot cause a rejection: a span reaching grade 6 or above gets a grade.
Applied to the observed spans:

| Span                                   | Upper bound      | In scope | Rows   |
| -------------------------------------- | ---------------- | -------- | ------ |
| `0606`, `0707`, `0808`                 | `06`, `07`, `08` | yes      | 14,384 |
| `0508`                                 | `08`             | yes      | 20     |
| `KG08`                                 | `08`             | yes      | 199    |
| `0505`, `0404`, `0303`, `0202`, `0101` | below `06`       | no       | 12,872 |
| `KGKG`                                 | `KG`             | no       | 1,675  |

The 219 rows on straddling spans (`0508`, `KG08`, both Camden) are in scope
under this rule. A strict reading of "spans starting at `06`" would exclude
them; at 219 rows the cost of being generous is negligible and the cost of being
wrong is a rejected file.

Note that `KG` must be excluded explicitly. A naive string comparison places
`'KG'` above `'06'` lexicographically, which would pull all 1,675 `KGKG` rows
into scope. The implementation must test membership in
`('06','07','08','09','10','11','12')` rather than using a range comparison.

## Architecture

### Source and join

Primary source is `{region}_powerschool.stg_powerschool__storedgrades`, filtered
to `academic_year = 2025` and `storecode = 'Y1'` — the year-final grade, which
matches the handbook's "grade the student received upon completion of the course
section."

Join path, validated in both regions:

```text
stg_student_extract.LocalIdentificationNumber -> students.student_number
students.id                                   -> storedgrades.studentid
stg_student_extract.LocalSectionCode          -> storedgrades.sectionid
```

`LocalSectionCode` is PowerSchool's `sections.id`. This was confirmed rather
than assumed: all 1,508 distinct Newark section codes match `sections.id`, and
**zero** match `section_number` or `dcid`.

The join is 1:1. Joined row counts equal extract row counts exactly in both
regions (33,150 and 10,343), so there is no fan-out. The extract itself is one
row per `(LocalIdentificationNumber, LocalSectionCode)` pair with no duplicates.

### Field derivation

`AlphaGradeEarned` is a **pass-through** of `storedgrades.grade`, guarded
against the handbook domain: a value outside the 18 legal codes resolves to
blank and appears in the exception report rather than being emitted. The guard
exists because the domain is an external contract that can drift, not because
the current data violates it.

`CreditsEarned` is `storedgrades.earnedcrhrs` formatted to exactly three decimal
places as a string. Formatting is part of the contract, not presentation: the
handbook sets a minimum length of 5, so `1` is invalid where `1.000` is valid.

### Region scoping is structural

The view is a `union all` of two region-specific selects. The Newark branch
reads `kippnewark_powerschool` against `stg_student_extract_newark`; Camden
reads `kippcamden_powerschool` against `stg_student_extract_camden`. Neither
branch can see the other's data.

This matters because local identifiers are unique only within a district. The
runbook documents 33 student local IDs shared across the two regions in the EOY
data. A single select joining on `LocalIdentificationNumber` alone would
manufacture false cross-region matches and assign grades to the wrong students.
Structural separation makes that failure mode unreachable rather than relying on
a `region` predicate being remembered in every join.

### Fallback for the coverage gap

Secondary source is `{region}_powerschool.stg_powerschool__pgfinalgrades`
(PowerTeacher live final grades), used **only** to fill nulls. A stored grade
always wins; the fallback never overrides one.

- `AlphaGradeEarned` uses the same domain-guarded pass-through.
- `CreditsEarned` requires a derived rule, because live grades carry no
  earned-credit value: a passing grade (`D-` or better) takes **the row's own
  `AvailableCredit`**; a failing grade takes `0.000`. Sourcing the value from
  the row itself makes the "must not exceed `AvailableCredit`" constraint
  impossible to violate by construction.

This is the only invented rule in the design, and it is bounded to roughly 52
secondary rows — small enough to review individually before upload.

Rows still blank after both sources stay blank and are listed in the exception
report. Nothing is guessed.

## The artifact

### The view

`cokafor.rpt_student_course_submission` — all 25 submission columns in
submission order, plus a `region` column, at one row per extract row.

The view is re-runnable with no edits. Each cycle the intern reloads the base
tables with the existing reload script and the view reflects the new data
automatically. This replaces the current practice of hand-editing a copy of the
reload script per extract cycle.

Because it is a view in `cokafor`, it is queryable from the BigQuery console,
which keeps it on the runbook's documented critical path and lets the existing
17 audit checks be pointed at the derived file as well as the native one.

### The export script

A script in the pattern of the existing reload scripts: select from the view for
one region, write a submission-ready CSV.

The script exists because of two hard constraints, not preference:

1. **Row count.** Newark's 33,150 rows exceed what the BigQuery console will
   hand back as a CSV download.
1. **Formatting is correctness.** `CreditsEarned` must keep three decimals and
   the CDS columns must keep leading zeros (`07`, not `7`). A naive export
   breaks both — the same failure class as the `--autodetect` trap the runbook
   already documents for loads, in the opposite direction.

Every column is written as a string, exactly as stored in the view. No numeric
coercion anywhere in the export path.

## Validation gate

A companion query that must return zero rows before the file goes to the
state-access uploader:

| #   | Check                                                                               |
| --- | ----------------------------------------------------------------------------------- |
| 1   | In-scope rows with a blank `AlphaGradeEarned`                                       |
| 2   | Secondary rows with a blank `CreditsEarned`, or one not formatted to three decimals |
| 3   | `AlphaGradeEarned` outside the 18 legal handbook values                             |
| 4   | `CreditsEarned` greater than `AvailableCredit`                                      |
| 5   | `CreditsEarned` outside `0.000`–`35.000`                                            |
| 6   | Row-count parity per region between the view and its base table (fan-out guard)     |
| 7   | Out-of-scope rows carrying a non-blank grade (scope-boundary guard)                 |

Check 7 is deliberate: it fails if the elementary contingency below is
implemented without also updating this spec, so scope cannot drift silently.

## Data profile (2026-07-29 extract)

Evidence behind the decisions above. All figures are aggregates; no identifiable
data appears in this spec.

### Stored letter grades are already handbook-legal

The complete set of `Y1` letter grades for SY 2025-26 is 13 values —
`A+ A A- B+ B B- C+ C C- D+ D D- F` — summing to exactly 25,006 (Newark) and
8,493 (Camden), which is every `Y1` row in each region. No nulls, no
out-of-domain codes, no local placeholder values. Every one of the 13 is legal
`AlphaGradeEarned`.

This is the finding that makes the pass-through viable and removes the need for
a grade-scale mapping table.

### Earned credit hours already encode pass and fail

`earnedcrhrs` and `potentialcrhrs` are populated on 100% of `Y1` rows (25,006 of
25,006 Newark; 8,493 of 8,493 Camden). `earnedcrhrs` equals `potentialcrhrs` for
passing students and `0` for failing ones.

Against the extract's own `AvailableCredit` on matched secondary rows:

- `earnedcrhrs` exceeds `AvailableCredit` on **zero** rows.
- `potentialcrhrs` differs from `AvailableCredit` on **zero** rows.

So the two scales agree, and the handbook's credit constraint is already
satisfied by the source data.

### Coverage

| Band                             | Rows       | Matched to a `Y1` stored grade | Gap     |
| -------------------------------- | ---------- | ------------------------------ | ------- |
| Newark HS                        | 10,695     | 10,675                         | 20      |
| Newark MS (`0606`/`0707`/`0808`) | 10,746     | 10,682                         | 64      |
| Camden HS                        | 3,648      | 3,616                          | 32      |
| Camden MS (`0606`/`0707`/`0808`) | 3,638      | 3,633                          | 5       |
| **In-scope subtotal**            | **28,727** | **28,606 (99.6%)**             | **121** |

Roughly 52 of the 121 gap rows are secondary, so only those need the derived
credit rule.

**Measurement caveat.** Coverage was measured before the straddling-span
decision, so the 219 `0508` and `KG08` rows were counted inside the out-of-scope
bucket and their `Y1` coverage is **not** included in the table above.
Implementation must re-measure with the final band rule. For reference, the
out-of-scope bucket as measured (which included those 219 rows) matched 3,502 of
11,709 in Newark and 1,224 of 3,057 in Camden.

## Named exception to source-fix-only

The runbook's cleaning model is explicit: defects are corrected at the source in
PowerSchool so the native extract comes out clean, the extract CSV is never
rewritten or post-filtered in BigQuery, and the handoff artifact is the
regenerated native extract.

**This work breaks that rule for two fields, on purpose.** PowerSchool cannot
emit `AlphaGradeEarned` or `CreditsEarned` correctly because of the
grading-model customization and the state-reporting mapping gaps, and neither is
fixable inside the submission window. The handoff artifact for the student file
becomes the **derived** CSV rather than the native one.

Constraints that keep the exception narrow:

- Exactly two fields are written. Every other column passes through unchanged.
- No row is added, removed, or filtered. Row-count parity is check 6.
- Every other defect — CDS above all — is still fixed at source.
- The exception is scoped to the student file. The staff file is untouched.

Recording it here means the boundary is a decision with a rationale rather than
an undocumented contradiction between the runbook and what actually ships.

## Contingencies and follow-ups

### Elementary pass/fail (contingent, not planned)

The 14,547 out-of-scope rows (prior-to-secondary, span upper bound below `06`,
including all `KGKG`) get no grade under this design, because the handbook does
not require one for them.

That reading is an inference. The handbook states the requirement affirmatively
for two populations and is **silent** on whether a grade is permitted or
expected outside them — it does not say those rows must be blank. Validators are
routinely stricter than the prose they implement, and prior-year KTAF experience
suggests the state may in fact expect values here.

**If NJSLEDS returns errors or warnings on blank grade fields for those rows,**
the contingency is a `CompletionStatus` of `P` or `F` per row, derived from
promotion: a student promoted to the next grade (SY 2026-27 grade level higher
than SY 2025-26) takes `P` on all their courses; a student retained (grade level
equal) takes `F`. `P` must go in `CompletionStatus`, never `AlphaGradeEarned`,
where it is not a legal value.

Adding it requires resolving, at minimum:

- The authoritative source for the SY 2026-27 grade level —
  `students.sched_nextyeargrade` versus actual SY 2026-27 enrollment records.
- Students with no SY 2026-27 record at all: transfers out, and any student who
  left the network. The equality test would mark them retained, which is wrong.
- Whether `int_reporting__promotional_status` should drive this instead. It is a
  status indicator built on attendance and credits with region-specific
  thresholds, not a record of the retention decision, so it likely cannot.

Validation-gate check 7 fails if this is implemented without updating this spec.

### NJSLEDS identity splice (follow-up)

For mismatch records that cannot be reconciled on the NJSLEDS end, a follow-up
would splice state-held values into the extract's identity fields — writing
`ref_state_student` and `ref_state_staff` values over the extract's own so the
combination checks (runbook checks 2 and 12) pass.

This is a materially larger departure than the grade backfill: it overwrites
identity data rather than filling empty derived fields, and it applies to the
staff file as well. Out of scope here, tracked separately.

## Blockers outside this scope

The CDS defect identified in the June audit is **still live** in the 2026-07-29
extract and gates the same upload:

| Region | County | District | School | Rows   | Status            |
| ------ | ------ | -------- | ------ | ------ | ----------------- |
| Newark | `80`   | `7325`   | `965`  | 22,841 | correct           |
| Newark | blank  | `7325`   | `732`  | 5,958  | wrong on both     |
| Newark | `80`   | `7325`   | `732`  | 4,351  | wrong school code |
| Camden | blank  | `1799`   | `179`  | 6,695  | wrong on both     |
| Camden | `07`   | `1799`   | `179`  | 3,648  | wrong school code |

20,652 of 43,493 rows (47%) carry a bad CDS, including every Camden row. Camden
emits `179`, which is neither the expected `111` nor the Newark-style `732`
pattern, but fits the same root cause: an unset Alternate School Number causing
a fallback to the internal school number prefix.

The fix remains the one-pass School Setup change on 3 Newark and 5 Camden
schools documented in the runbook. **A clean grade backfill does not make the
file submittable on its own.**

## Open items to confirm during implementation

- Re-measure `Y1` coverage with the final band rule, including the 219
  straddling rows.
- Confirm the exported CSV matches the native extract's quoting, line endings,
  and encoding. The reload scripts read the native files with `utf-8-sig`,
  implying a BOM; the export must not silently change what the state's parser
  sees.
- Verify the expected Camden school code is still `111` against the NJDOE
  directory before anyone keys it.
- Diff handbook v1.4 against the version the runbook was written from,
  particularly the v1.2 change making `GradeSpan` blank-able for Secondary and
  `AvailableCredit` blank-able for Prior-to-secondary, which runbook check 9
  encodes.
- Confirm `pgfinalgrades` exposes a year-final reporting term for the gap rows,
  and decide the selection rule if several final-grade records exist for one
  section.
- Confirm no in-scope row draws a grade from a section whose `CourseType` is `C`
  (dual enrollment) where the grade is held by the college rather than
  PowerSchool.

## Non-goals

- **No dbt model.** This is a submission-window tool reading a hand-loaded
  dataset (`cokafor`) that exists only during the audit cycle. Promoting it to
  dbt is a reasonable durability question for next year's cycle, and is noted as
  such in the project context, but it is not this work.
- No changes to the staff file.
- No correction of any field other than the two named, including CDS.
- No promotion or retention logic (see _Contingencies_).
- No row filtering, deduplication, or reordering.
- No row-level identifiable data on any external surface. The exported CSV is
  PII-bearing and goes to the state-access uploader only; the view stays in
  `cokafor`, in-tenant.
