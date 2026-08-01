# Finalsite address of record — pick the best household

Issue: [#4680](https://github.com/TEAMSchools/teamster/issues/4680). Follows
[#4651](https://github.com/TEAMSchools/teamster/issues/4651), merged as
`09f9513fa`.

## Problem

The Focus `ADDRESS` and `CONTACTS` feeds are import-once: a student's address
record is sent once and never overwritten, so a missing address is permanent for
that student. Measured against production on 2026-08-01, **158 KIPP Miami
students would receive no address in either feed**.

Neither `contacts_csv` nor `addresses_csv` has ever materialized, so nothing is
locked in. This is correctable before first delivery.

The intended rule, stated by the data owner:

> Students should have no address only if they have no primary contact or their
> primary contact has no valid address.

Today's behavior is much stricter than that.

## Measured baseline

The 158 stranded students break down as:

| Cause                                           | Students |
| ----------------------------------------------- | -------: |
| Several candidate addresses, so nothing is sent |      100 |
| No Parent 1 designated                          |       38 |
| Parent 1 has no valid address                   |       20 |

Only the last two match the intended rule. The 100 are withheld because
`int_finalsite__contact_address_of_record` emits an address only when a contact
resolves to exactly one distinct address, and refuses to choose between several.

Two supporting measurements shaped the design.

**Household membership is family-level, not per-person.** Of the 38 students
with no Parent 1, 14 have a household of their own and **13 of those share the
exact `household_id` with one of their caregivers**. Resolving such a student
from their own linkage reads the same household row the caregiver is already in
— it does not invent an address.

**Tier order changes the answer for 113 students.** Across all 3,428 Miami
students with a Parent 1: 2,239 resolve to the same address from either the
student's own household or Parent 1's, 1,024 resolve from neither, 43 resolve
only from Parent 1, 9 resolve only from their own, and **113 resolve to
different addresses depending on which is tried first**.

## The rule

A contact's address of record is the **best** of its street-bearing households,
not the only one. Best is `is_complete_address` descending, then `household_id`
ascending. A contact with no street-bearing household still has no address.

A student's address of record comes from **Parent 1's household first**, falling
back to **the student's own** when Parent 1 has none. There is no third tier: a
student with neither gets no address, which is the state Ops must correct in
Finalsite.

Picking partly re-opens what
[#4651](https://github.com/TEAMSchools/teamster/issues/4651)'s strict-key
reversal closed, and that is deliberate. For two spellings of one address the
pick is harmless — either is correct. For two genuinely different addresses it
is a real choice, justified by the same reasoning already applied to the
completeness gate: a visibly wrong address is correctable in Focus, a blank one
is silent.

## Commit 1 — `int_finalsite__contact_address_of_record`

Replace the `candidate_count = 1` gate with a second deduplication over the
distinct-address set, partitioned by contact:

```sql
{{
    dbt_utils.deduplicate(
        relation="address_candidates",
        partition_by="finalsite_enrollment_id",
        order_by="is_complete_address desc, household_id asc",
    )
}}
```

`candidate_count` is unchanged. `resolution_status` becomes:

| Value       | Meaning                                            |
| ----------- | -------------------------------------------------- |
| `resolved`  | exactly one candidate — unchanged meaning          |
| `picked`    | several candidates, chosen by completeness then id |
| `no_street` | no street-bearing household                        |

`desc` on a boolean is safe inside the macro's `array_agg`; BigQuery rejects
only the explicit `asc nulls last` and `desc nulls first` forms.

Two `dbt_utils.expression_is_true` invariants in the properties YAML change:

- `resolved` implies `candidate_count = 1` survives verbatim.
- `ambiguous` implies `candidate_count > 1` becomes `picked` implies
  `candidate_count > 1`.
- The invariant that a non-`resolved` status implies a null address **inverts**
  — `picked` now carries an address. It is restated as `no_street` implies a
  null address.

Several unit-test fixtures currently assert `resolution_status: ambiguous` with
null address columns; those cases now assert `picked` with the winning address.

This commit alone un-blanks a large share of the 436 guardian rows in the
`CONTACTS` feed, including the 13 contacts the strict-key reversal moved from
`resolved` to `ambiguous`.

## Commit 2 — `int_finalsite__student_address_of_record`

Four changes.

**Spine.** From `where is_primary` to contacts carrying a workflow status —
`status != 'not_in_workflow'` on `stg_finalsite__contacts`. `is_primary` is the
current definition of a student record, which is why a student with no Parent 1
gets no row at all today. `stg_finalsite__contacts` is one row per contact, so
no explicit deduplication is needed. The `is_primary` row is left-joined purely
to supply `primary_contact_id`, preserving today's behavior where two primaries
on one student fail the uniqueness test loudly.

Scoping to `status = 'enrolled'` was considered and rejected: it would place an
enrollment scope inside a deliberately SIS-agnostic package, denying addresses
to applicants and prospects if another receiver ever wants them.
`rpt_focus__addresses` keeps its own `stu.status = 'enrolled'` filter.

**Tier order.** Parent 1's household first, the student's own as fallback. The
existing comment justifies student-first on the grounds that a parent carries
more households and so more competing addresses — decisive under the old
withhold rule, irrelevant once the model picks. The student's own tier must stay
as a fallback: dropping it would strand the 9 students who have an address of
their own while their Parent 1 has none.

**Gates.** From `candidate_count = 1` to "the tier resolved to an address at
all", since the contact model now emits one whenever a street-bearing household
exists.

**New column.** `is_picked_address` (`boolean`) reports whether the winning
tier's address was chosen from several candidates. `resolution_status` continues
to name the tier, with values `primary_contact_household`, `student_household`,
and `unresolved` — replacing `ambiguous`, which no longer describes the cause.

The model's documented grain, "one row per student record (a contact carrying a
`primary` relationship)", becomes "one row per student record (a contact
carrying a workflow status)". This requires description updates in the model's
properties YAML and in `src/dbt/finalsite/CLAUDE.md`.

## Expected impact

| Metric                                         | Before |            After |
| ---------------------------------------------- | -----: | ---------------: |
| Miami students with no address anywhere        |    158 |               46 |
| Students whose shipped address changes         |    n/a |              113 |
| Guardian rows with a blank address, `CONTACTS` |    436 | materially lower |

The 113 changes come from the tier reorder. Nothing has shipped, so they carry
no import-once cost.

The remaining 46 are Finalsite data gaps — 20 families with no address recorded
anywhere, 21 with no household at all, and a handful of edge cases. No code
change reaches them.

## Validation

The safety bar: **no student who has an address today may lose one**, and the
only address changes are the 113 from the tier reorder. Anything else is a
defect.

Because the parent work is already deployed, production is the comparison
baseline. Compare a dev build of the full chain against the deployed
`kippmiami_extracts.rpt_focus__addresses` and `rpt_focus__contacts` relations,
row by row, and report:

- students gaining an address, losing one, and changing to a different one
- the stranded count, which must land at 46
- the `resolution_status` distribution across both models
- the guardian blank-address count in the `CONTACTS` feed

## Testing

New unit tests on `int_finalsite__contact_address_of_record`:

- two candidates differing in completeness — the complete one wins
- two equally complete candidates — the lower `household_id` wins
- one candidate — status stays `resolved`
- no street-bearing household — status stays `no_street`

New unit tests on `int_finalsite__student_address_of_record`:

- Parent 1 and the student both resolve to different addresses — Parent 1 wins
- Parent 1 has no address, the student does — the student's own is used
- a student with no Parent 1 resolves from their own household
- neither resolves — `resolution_status` is `unresolved` and the address is null

## Out of scope

- Renaming `int_finalsite__student_address_of_record`. The name remains accurate
  under the workflow-status spine. Bundling a rename with a behavior change
  would obscure the validation diff.
- A third fallback tier sourcing any caregiver's household. It would recover 3
  students, and measurement confirmed it recovers none of the 20 whose Parent 1
  has no address, because no caregiver in those families has one either.
- Ops cleanup of the 46 remaining students. That is Finalsite data entry, not a
  pipeline change.

## Open risks

`not_in_workflow` is the discriminator this design leans on, and it is good but
not perfect in either direction.

Adults are almost entirely `not_in_workflow`, so the spine excludes them: of the
roughly 3,568 Miami contacts carrying a workflow status, essentially all hold a
student id, and only one reads as a plausible adult. Row count is therefore
close to today's `where is_primary` set rather than a large widening.

In the other direction, 63 Miami contacts carry `not_in_workflow` while also
holding a `primary` relationship, so they read as children and the spine
excludes them. None is `enrolled`, so none reaches the Focus feed today. If that
status is ever applied to an enrolled student, they would be silently dropped —
the failure would be invisible rather than loud, which is the weakest point in
this design.

A downstream guard already limits the blast radius of any spine
misclassification: `rpt_focus__addresses` inner-joins
`int_finalsite__contact_id_attributes` on
`focus_student_id_prefixed is not null`, so a non-student admitted by the spine
cannot reach the feed.
