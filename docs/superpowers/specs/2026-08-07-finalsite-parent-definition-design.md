# Finalsite parent definition — design

Refs #4768

## Problem

`int_finalsite__student_contacts` fills two parent slots, `contact_1` and
`contact_2`, from `stg_finalsite__contact_relationships`. Three properties of
the current pick are wrong or unstated:

1. `contact_2` is defined relative to **Parent 1's household** — a candidate
   qualifies only if they co-belong to a household with the contact chosen as
   `contact_1`. This is an undocumented addition. The package CLAUDE.md states
   the intended rule as "`primary` = Parent 1, an additional
   `financial`-without-`primary` relationship = Parent 2" and notes that
   "`households` carry only id + address — membership has no roles."
1. Because `contact_2` is anchored on Parent 1, a missing `primary` flag
   suppresses **both** slots, not just the first.
1. Nothing checks that a selected contact is not themselves a student, and a
   third qualifying parent is silently discarded by a `relationship_id`
   tie-break.

### Audit evidence

Measured across the three cutover NJ regions (Newark, Camden, Paterson) on the
2026-08-07 load, scoped to `status = 'enrolled'` and `school_year_start = 2026`.

Qualifying parents per student under the proposed definition:

| Region   | Students | 0   | 1     | 2     | 3   | Max |
| -------- | -------- | --- | ----- | ----- | --- | --- |
| Newark   | 6,786    | 0   | 3,682 | 3,079 | 25  | 3   |
| Camden   | 2,163    | 52  | 1,264 | 840   | 7   | 3   |
| Paterson | 879      | 43  | 539   | 297   | 0   | 2   |

32 of these students have three, and today the third is discarded.

That table is scoped to currently enrolled students. **The model is not** — it
stays SIS-agnostic and emits a row for every student record, including withdrawn
students and prospects. Across that full population the cutover regions hold 72
students with three parent slots and 8 with four. Dense ranking has no upper
bound, so no fixed maximum can be asserted about `contact_slot`; see section 5.

Two failure modes the household filter causes, both observed:

- A parent with a **duplicate contact record** splits the household link. The
  flagged `primary` relationship points at one record while the student's
  household contains the other, so the co-membership test fails and the student
  gets no contacts despite having a correctly flagged parent.
- Legitimately **non-resident** parents are excluded. In the pre-refresh Newark
  snapshot, 369 relationship rows were flagged `financial`, typed as a
  caregiver, and dropped solely for living elsewhere.

## Decisions

### 1. Student scope — no filter

`int_finalsite__student_contacts` stays SIS-agnostic and continues to emit rows
for every student record, including prospects and applicants. This preserves the
package convention: "Filtering `where is_primary` yields ALL Finalsite student
records — scope to enrolled students downstream."

Verified that downstream receivers already scope correctly. Of 303 Newark
student records still carrying `status = 'enrolled'` for `school_year_start`
2025, 257 reach `int_students__contacts`, but only 15 reach
`rpt_parentsquare__parents` and `rpt_deanslist__family_contacts` — the
receivers' PowerSchool enrollment joins drop the rest.

Those 15 are **not** a leak. PowerSchool has all 15 at `academic_year = 2026`,
`grade_level = 12`, `enroll_status = 0` — actively enrolled retained seniors.
Finalsite is the stale side; it never created a current-year record for them. A
`school_year_start` filter applied on the Finalsite side would wrongly remove 15
current students' contacts from both receivers.

`is_alumni` is rejected as a scope signal. It marks two unrelated populations:
302 prior-year graduating seniors, and 104 adults who are current contacts and
themselves alumni of the school. Applied contact-side it would drop 104
legitimate parents. It is not added to staging.

### 2. Stale-enrolled warning

New `warn`-severity test on `stg_finalsite__contacts`, asserting no row has
`status = 'enrolled'` and `school_year_start < var('current_academic_year')`.

The test lives in the finalsite package so all four regions inherit it. It will
sit yellow as a standing population — accepted deliberately, because the count
is a live Ops worklist rather than a transient anomaly. It catches two distinct
Finalsite failures with the same predicate: graduates never rolled off
`enrolled`, and current students never rolled forward to the new year.

### 3. Parent selection

Replace the `contact_1` / `contact_2` CTEs with a single candidate set.

A **parent candidate** is a relationship on a student record where:

- `is_primary` or `is_financial` is true, and
- the related contact's `status` is `not_in_workflow`.

Slot assignment is **dense** — candidates are ranked, then numbered `contact_1`,
`contact_2`, `contact_3` with no gaps. The rank is:

1. `is_primary` descending (the flagged Parent 1 sorts first when present)
1. household co-membership with the **student** descending
1. `relationship_id` ascending

Dense numbering matters. If `contact_1` were reserved for the `primary`
relationship and left empty when none exists, the zero-contact test would
misreport: a student holding `contact_2` and `contact_3` but no `contact_1`
would be counted as having no contacts at all. Every slot number would also
shift by one for exactly the students whose data is already weakest, making the
`contact_2` column mean different things for different students.

The cost is that `contact_1` no longer means "the `primary` relationship"; it
means "the top-ranked parent". Of the 9,733 current students across the cutover
regions who have at least one candidate, 9,691 (99.6%) have a `primary` among
them, and for those the two readings select the same contact. The remaining 42
have candidates but no `primary`; a populated `contact_1` is what lets the wide
receivers show them a parent at all.

The Parent-1-household join, the `primary_household_ids` and
`contact_household_ids` CTEs, and the `rn_contact_2 = 1` cap are all deleted.
Household co-membership becomes a sort key computed against the student's own
`household_ids`, reusing the existing `int_finalsite__contacts__households`
model rather than re-flattening the array.

Two consequences worth stating explicitly:

- `contact_2` no longer depends on `contact_1`. A student with no `primary` flag
  but with `financial` relationships now gets contacts, where previously they
  got none.
- Ordering by household co-membership before `relationship_id` fixes observed
  cases where a non-resident candidate won the arbitrary tie-break over a
  co-resident one.

### 4. Guard shape — no carve-out

The guard is a single condition on the related contact:
`status = 'not_in_workflow'`. It folds into the join the model already performs
in `parents_typed` to fetch the contact's name, email, and phone.

No `not exists` form and no allowance for unresolvable `rel_id`s. Of 21,783
flagged relationship rows across the cutover regions, **zero** point at a
contact with no record; all 461 unresolvable rows are unflagged. The existing
inner join to `stg_finalsite__contacts` already drops them.

The guard currently excludes exactly one real parent network-wide — a contact
whose own record carries `status = 'inquiry'` and a grade, i.e. an adult
miskeyed as a student — out of 6,771 Newark primary relationships. This is
deliberately **not** carved out: a carve-out would be a permanent exception to
reason about, and the guard's whole value is that it has no exceptions.

The exclusion is **silent**, and an earlier draft of this spec was wrong about
why that is acceptable. It claimed the affected student would be left with no
`contact_1`, firing the zero-contact test. Dense ranking makes that false — the
student's other `financial` parent backfills `contact_1`, so no downstream
symptom appears at all. The student keeps a reachable parent, but the miskeyed
record goes unreported and their listed first contact is not their designated
primary.

Because the symptom is invisible, the condition is tested at the source instead
— see the fifth test in section 5, which reports any caregiver-flagged
relationship whose related contact lacks the adult status. That surfaces the
miskeyed record directly rather than hoping a downstream slot goes empty.

### 5. Tests

Five additions, all `warn` severity:

1. **Zero contacts** — a singular test listing students with
   `status = 'enrolled'` and `school_year_start = var('current_academic_year')`
   that have no `contact_1` row. The test applies the enrolled scope even though
   the model does not; scoping the denominator here avoids firing on prospects
   and applicants, who legitimately have no parent on file yet.
1. **Three or more contacts** — asserts no `contact_3` row exists. Fires when
   the two conventional slots are insufficient, which today is 32 students.
1. **Stale enrolled** — section 2 above, on `stg_finalsite__contacts`.
1. **Multiple primary relationships** — asserts no student record holds more
   than one relationship flagged `is_primary`.
1. **Caregiver is an adult** — reports any relationship flagged `primary` or
   `financial` whose related contact does not carry `not_in_workflow`. Most rows
   are correct exclusions (a sibling flagged `financial`); the actionable ones
   are adults miskeyed with a student status, whose relationship the guard
   discards with no downstream symptom. 1 row for Newark on the current load.

The `accepted_values` enumeration on `contact_slot` is **removed**, not
extended. Dense ranking produces as many parent slots as a student has
qualifying adults — 8 students already have four — so an enumerated list is the
wrong shape and would fail again at five. It is replaced by a
`dbt_utils.expression_is_true` assertion at `severity: error`:

```text
regexp_contains(contact_slot, r'^(contact_[0-9]+|emergency_[1-4])$')
```

Parent slots stay unbounded; emergency slots stay bounded at four, because they
are a positional passthrough of four fixed `emrg_N` custom-field sets.

The fourth test replaces a signal the redesign removes. Today a second `primary`
on one student produces two `contact_1` rows and fails the model's
`(finalsite_enrollment_id, contact_slot)` uniqueness test — an intentional loud
failure, documented in the current model comments. Under dense ranking the
second `primary` silently becomes `contact_2` instead. Testing the source
condition directly preserves the signal and reports it against the record that
needs fixing. No current student holds more than one `primary`, so this test
starts green and guards against regression rather than reporting a backlog.

### 6. Downstream defensive fix

`dim_student_contact_persons` partitions rows with
`where contact_slot not in ('contact_1', 'contact_2')` into `emergency_persons`,
keyed by student plus slot rather than by person identity. A `contact_3` row
would fall into that branch and be recorded as an emergency contact. No test
would fail.

Change that predicate to an explicit `like 'emergency%'` so unknown parent slots
are excluded rather than misclassified.

### 7. Existing unit test

`test_student_contacts_parent_2` asserts the behaviour being removed: its `con3`
fixture is a `financial` relationship in a different household from Parent 1,
expected to be excluded. Rewrite it so `con3` becomes `contact_3`, ordered after
`con2` because `con2` shares the student's household. The fixture's `stu2` case
— no `primary`, two `financial` relationships, expecting no rows — must also
change: under dense ranking `stu2` yields `contact_1` and `contact_2`.

Fixtures need a `households` value on the student records, which the current
fixture omits, since co-membership is now computed against the student.

## Out of scope

- **Extending the wide receivers.** `int_students__contacts_pivot`,
  `rpt_parentsquare__parents`, `rpt_deanslist__family_contacts`, and
  `bridge_student_contacts` all hardcode a two-slot surface and will drop
  `contact_3`. No receiver needs a third contact today and it affects 32
  students; extending them is a separate change.
- **Emergency-slot duplication.** The `emrg_N` custom fields are a positional
  passthrough with no dedup against the parent slots or against each other. At
  least one student emits four contact rows for two people, with the primary
  parent's only reachable phone number sitting in a duplicated emergency slot
  under a misspelled name. Fixing this is a merge problem, not a filter, and is
  tracked separately.
- **Ops data corrections.** Miskeyed contact records surfaced by the new tests
  are fixed in Finalsite, not in dbt.

## Verification

- `uv run dbt build --select int_finalsite__student_contacts+` in each cutover
  region, plus the unit tests.
- Confirm the per-region distribution matches the audit table above.
- Confirm no student loses a contact relative to the current model, other than
  the single guard exclusion described in section 4.
- Confirm `dim_student_contact_persons` emits no `contact_3` row in its
  `emergency_persons` branch.
