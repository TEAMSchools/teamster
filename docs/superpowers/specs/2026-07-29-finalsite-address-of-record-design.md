# Resolve the Finalsite student address of record

Refs [#4613](https://github.com/TEAMSchools/teamster/issues/4613).

> **Amended during implementation.** Three parts of the design below were
> changed during review on
> [#4637](https://github.com/TEAMSchools/teamster/pull/4637): the households
> model became an intermediate reading `stg_finalsite__contacts` rather than a
> staging model reading the source (and was renamed
> `int_finalsite__contacts__households`), so the stated parallel to
> `stg_finalsite__contact_relationships` no longer holds; `min(country)` became
> a `dbt_utils.deduplicate` canonical-row pick; and the completeness test became
> a biconditional against `address_source`, the version described here having
> been trivially satisfiable. `int_finalsite__student_address_of_record` also
> carries the primary contact's phone, which this design argued for but did not
> plumb. See the "Amended during execution" section of
> `docs/superpowers/plans/2026-07-29-finalsite-address-of-record.md`.

> **Phase 2 re-measurement (2026-07-30).** Measured against prod: 1,240
> `student_household` + 17 `primary_contact_household` = 1,257 exported; 170
> `ambiguous`, of which 22 hold no complete address anywhere; 70 absent for want
> of a `primary` relationship. The Measured effect table and breakdown below
> (1,275 + 16 = 1,291 exported, 147 ambiguous, 23 with no address) are left as
> the point-in-time design record, not restated to match.

## Problem

`stg_finalsite__contacts` flattens seven address columns off
`households[safe_offset(0)]`. Array position does not identify Finalsite's
primary household — that designation is set in the UI and is absent from every
field the API exposes, confirmed against the vendor spec and by the maintainer.
`rpt_focus__addresses` maps those columns onto the Focus ADDRESS contract, so
whichever household sits at offset 0 becomes the student's address of record.

The feed is import-once with no overwrite path, and only 4 of 1,498 enrolled
Miami students have imported. Almost every wrong pick is still prospective and
becomes permanent on first import at scale.

## The finding that drives the design

`households` is an array on **every** contact record, students and adults alike.
`stg_finalsite__contacts.address_*` is `households[safe_offset(0)]` of whichever
contact row is read. Two facts follow.

**Parents carry more household rows than students.** Distinct complete addresses
per record, across the 1,427 feed-population students who have both a student
record and a primary contact, with `address_2` excluded from the address
identity:

| Distinct complete addresses       | Student record | Primary contact record |
| --------------------------------- | -------------- | ---------------------- |
| 1                                 | 1,245          | 1,145                  |
| 2                                 | 152            | 225                    |
| 3 or more                         | 2              | 30                     |
| 2 or more, so a pick is arbitrary | 154            | 255                    |

**The student's household linkage is a subset of the primary contact's** — true
for 1,383 of 1,427 students with both records present. The parent is
additionally linked to households the student is not in; the student is linked
to the household they live in.

Decisively: within those same 1,427, for **all 112** students whose own record
resolves to exactly one complete address while their primary contact's record
has several, the student's address is one of the parent's. Zero exceptions.

So Finalsite already records which of the parent's several addresses applies,
and records it on the student. The student's linkage is the disambiguating
signal.

This also corrects #4613's framing. The issue states that an address "has to
select exactly one household, so it genuinely requires the primary-household
designation." For 1,245 students the student's own record resolves to one
address with nothing to pick, and for 112 more it disambiguates the parent's
set. The designation is genuinely needed only for the residual 147.

## Superseded approach, and why it was wrong

An earlier revision of this design anchored the address on the primary contact
unconditionally — read that contact's `households[safe_offset(0)]` instead of
the student's. It shipped, passed CI and two review rounds, and was wrong.

It changed **whose** offset 0 was read without changing the fact that offset 0
was read, so #4613's objection still applied — to the parent's array. Because
parents carry more household rows, it moved the pick onto the record with more
competing addresses. On the 1,498-student basis it raised arbitrary picks from
164 to 256 (see Measured effect). Measured instead on the 1,377 students it
would have exported, ignoring `address_2` in the address identity, the same
regression reads as 152 to 253 — 112 students newly ambiguous against 11 newly
determinate, with 242 of the 253 being genuinely different streets rather than
formatting drift.

The analysis error worth recording: the design measured what the anchor fixed
(11) and never measured what it broke (112). Both numbers were one query apart.
Framing the change as "semantic, not accuracy" removed the incentive to check
whether accuracy got worse.

## Decision

Resolve the address of record from the student's own household linkage where
that linkage is decisive, and fall back to the primary contact only where it is
not.

1. Distinct complete addresses on the student's own households. Exactly one, use
   it.
1. Otherwise, distinct complete addresses on the primary contact's households.
   Exactly one, use it.
1. Otherwise, emit no address and flag the student.

Address identity is `address_1`, `address_2`, `city`, `state`, `zip`. Including
the apartment line moves the residual from 143 to 147 because 4 students'
households differ only by apartment — an apartment difference is a different
mailing address, so counting it is the correct reading.

"Complete" means `address_1`, `city`, `state`, and `zip` are all non-null.
`address_2` is not required; it is legitimately null.

## Design

### `stg_finalsite__contact_households` (finalsite package)

Flattens the `households` array to one row per contact-household. Exactly
parallel to the existing `stg_finalsite__contact_relationships`, which already
flattens the `relationships` array the same way.

- Grain: one row per (`finalsite_enrollment_id`, `household_id`). Verified
  unique in current data — 8,440 rows, zero duplicate pairs, zero null household
  ids.
- Columns: `finalsite_enrollment_id`, `household_id`, the six address fields
  carrying the same `nullif` / `trim` / `upper(state)` normalization
  `stg_finalsite__contacts` already applies, plus a derived
  `is_complete_address` boolean.
- Contract enforced and table-materialized, per the staging directory defaults.
- Uniqueness: `dbt_utils.unique_combination_of_columns` on the grain above.

This model exists because `households` is the only place addresses live, and
nothing currently exposes them per household. The `household_ids` array on
`stg_finalsite__contacts` carries ids without addresses.

### `int_finalsite__student_address_of_record` (finalsite package)

- Grain: one row per contact that has a `primary` relationship. Per the package
  docs, only child and student records carry a primary link, so that flag is how
  a student record is identified without reaching for a SIS-specific field.
- SIS-agnostic: no enrollment, status, or academic-year filter. Receivers scope
  downstream, matching `int_finalsite__student_contacts`.
- Emits the six address fields plus:
  - `address_source` — `student_household` or `primary_contact_household`
  - `resolution_status` — the two above plus `ambiguous`
  - `student_candidate_count` and `primary_contact_candidate_count`, so an Ops
    worklist can be built without re-deriving the rule
- Uniqueness: `unique` on `finalsite_enrollment_id`.

**Every emitted address is complete by construction**, because the rule only
selects among complete candidates. Downstream therefore needs no completeness
filter of its own.

### kipptaf consumption

- A `union_relations` wrapper over all four regions, **including Miami** —
  following `int_finalsite__contact_id_attributes` rather than
  `int_finalsite__student_contacts`. The latter excludes Miami to avoid
  double-counting contacts against the PowerSchool branch of
  `int_students__contacts`; no equivalent risk exists for an address model, and
  Focus is the Miami consumer.
- Source entries in all four `sources-kipp*.yml`, which already carry the
  `staging` → `zz_stg_` branch for finalsite.
- `rpt_focus__addresses` becomes a thin projection: join the wrapper, the
  lifecycle model, and the id-attributes pivot, and filter to resolved rows. The
  `p1` self-join and the four-column completeness filter both go away.

### The phone stays the primary contact's

A phone is a contact attribute, not a household one, so it is independent of
which household supplied the address. The student's own `phone_1_number` is null
for 1,497 of 1,498 students while 1,414 primary contacts carry one, and the
kippmiami completeness gate never checked phone — so leaving it on the student
record would bake a permanently blank phone into the Focus records under
import-once.

### The duplicated completeness gate goes away

Because the intermediate emits only complete addresses, `rpt_focus__addresses`
needs no address filter, and the kippmiami wrapper's #4320 gate becomes the only
one. The `src/dbt/kipptaf/CLAUDE.md` "finalsite→focus exception" paragraph added
for the superseded approach is reverted, restoring the convention that kipptaf
`rpt_focus__*` are desired-state.

## Measured effect

All figures below share one basis: the 1,498-student enrolled Miami feed
population, with address identity including `address_2`. Any figure elsewhere in
this document that uses a different basis says so explicitly — two errors during
this design came from comparing counts measured under mismatched definitions.

| Rule                                    | Exported  | Of those, arbitrary | Excluded, ambiguous |
| --------------------------------------- | --------- | ------------------- | ------------------- |
| Current production — student's offset 0 | 1,406     | 164                 | 0                   |
| Superseded — primary contact's offset 0 | 1,377     | 256                 | 0                   |
| **This design**                         | **1,291** | **0**               | **147**             |

This design is a trade, not a strict improvement:

- It eliminates all 164 arbitrary picks production currently exports.
- It adds 32 students production misses — a blank offset 0 masking a household
  linkage that does resolve.
- It withholds the 147 it cannot resolve, roughly 115 net against what Focus
  receives today.

The asymmetry is what justifies it. Withholding is recoverable: staff enter the
address manually, or the Finalsite duplicate-household cleanup lands and a later
feed run picks the student up. A guess is not recoverable — the feed is
import-once with no overwrite path, so a wrong address of record is permanent
and carries no marker distinguishing it from a verified one.

Breakdown under this design (as originally measured, except the
no-`primary`-relationship figure, updated to 70 per the 2026-07-30 note above —
so these figures no longer sum to 1,498): 1,275 resolved from the student's own
household linkage, 16 from the primary contact's, 147 flagged ambiguous, 70 with
no `primary` relationship (enrolled Miami feed-population students absent from
`int_finalsite__student_address_of_record` entirely, for want of a primary
contact to anchor on), and 23 whose records hold no complete address anywhere.

## Scope boundary

The 70 enrolled Miami feed-population students with no `primary` relationship
are absent from `int_finalsite__student_address_of_record` entirely, not flagged
as ambiguous. Representing them would require a student-versus-adult
discriminator the package layer does not have — a contact with no primary link
may simply be an adult. Those students are tracked in
[#4617](https://github.com/TEAMSchools/teamster/issues/4617) as a Finalsite
data-entry gap.

## Sequencing

Two PRs, per the district-first rule for package models consumed by kipptaf via
`source()`.

1. **Package PR** — `stg_finalsite__contact_households` and
   `int_finalsite__student_address_of_record`. These build in all four
   districts. Merge, then wait for Dagster to materialize prod.
1. **kipptaf PR** — source entries, the union wrapper, the
   `rpt_focus__addresses` rework, and the doc reversions. This is #4618, already
   converted to draft.

Shipping kipptaf first would fail CI deterministically: the `zz_stg_*` staging
copies would not carry the new models.

## Testing

- `stg_finalsite__contact_households` — grain uniqueness, `not_null` on both key
  columns, `severity: error` per the staging-layer requirement.
- `int_finalsite__student_address_of_record` — `unique` and `not_null` on
  `finalsite_enrollment_id`; `accepted_values` on `resolution_status` and
  `address_source`; an `expression_is_true` asserting that a row with a non-null
  `address_1` also has non-null `city`, `state`, and `zip`, which is the
  completeness guarantee downstream depends on.
- Unit tests on the intermediate covering each branch of the rule: student's own
  linkage decisive; student's ambiguous but primary contact's decisive; both
  ambiguous; student with no households but a primary contact that resolves.
  Input `format: sql` where a mocked upstream carries array or struct columns.
- Unit tests for `rpt_focus__addresses` updated to mock the new wrapper instead
  of the `p1` self-join, and the whole `extracts.focus` directory run with
  `dbt test` — `dbt build` no-ops on a unit-only selector in dbt-core 1.11.12.
- Validate against prod before merging the kipptaf PR by compiling with
  `--target prod` and comparing row counts and resolution-status distribution to
  the figures in this spec.

## Out of scope

- Retiring duplicate household records in Finalsite. Roughly 150 families hold
  two live household rows, plausibly an old address and a current one, and
  `Household` exposes no `created_at` or `updated_at` to tell them apart. This
  is the real fix for the residual and belongs with Miami ops.
- Asserting the `is_primary` singleton at its source, tracked in
  [#4616](https://github.com/TEAMSchools/teamster/issues/4616).
- Whether `household_1_id` still earns its place in the staging contract, per
  #4613's own non-goals. Note this design gives `stg_finalsite__contacts`'
  scalar address columns no consumer in the Focus address path, which
  strengthens the case for revisiting them — but `rpt_focus__contacts` and
  `int_finalsite__student_contacts.household_address` still read them.
