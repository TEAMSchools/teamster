# Anchor the Focus ADDRESS feed on the student's primary contact

Refs [#4613](https://github.com/TEAMSchools/teamster/issues/4613).

## Problem

`rpt_focus__addresses` sources the student's address of record from
`stg_finalsite__contacts.address_*`, which
[flattens seven scalar columns](../../../src/dbt/finalsite/models/api/staging/stg_finalsite__contacts.sql)
off `households[safe_offset(0)]`. Array position does not identify Finalsite's
primary household. The per-student primary designation is set in the Finalsite
UI and is absent from the API: the `Household` object carries id plus address
only, confirmed complete against both the vendor spec and the maintainer. It
will not appear after a re-pull, so no probe or schema change unblocks it.

Whichever household happens to sit at offset 0 therefore becomes the student's
address of record in Focus. Of 1,498 enrolled Miami students in the feed, 167
have more than one distinct complete address across their households, so offset
0 is an arbitrary pick for them.

Two facts make this urgent rather than merely wrong. The feed is import-once
with no overwrite path, and only 4 of 1,498 students have imported so far — so
almost every arbitrary pick is still prospective, and becomes permanent and
unmarked on first import at scale.

## Decision

The address of record is redefined as **the address of the student's primary
contact**, rather than as an attempt to reproduce Finalsite's primary-household
designation.

This is a deliberate redefinition, not an approximation. Under it, the objection
recorded in #4613 against anchoring on Parent 1 — that Parent 1 may not live in
the UI's designated primary household — stops applying, because the UI
designation is no longer the target.

Three things recommend it:

- It is already this repo's established semantics.
  `int_finalsite__student_contacts` states that "the student's primary household
  is the household their Parent 1 belongs to," and #4611 shipped that rule for
  the contact slots. The address columns simply never adopted it.
- It makes the two Focus feeds internally consistent. `rpt_focus__contacts`
  already emits each contact's own address, so Parent 1's address is already
  being pushed to Focus through the CONTACTS feed.
- It replaces an undefined rule with a stated one. Array position is something
  Finalsite never promised means anything; "the primary guardian's address" is a
  rule that can be explained to Ops and audited.

### What this decision does not do

It does not resolve the underlying ambiguity. Parent 1 belongs to **every one**
of the student's competing households in 202 of 229 cases — counted by household
record rather than by distinct address, hence 229 rather than 167 — so household
membership carries no discriminating signal. The 167 ambiguous students reduce
to 11 determinate ones. The remaining ambiguity is a Finalsite data-hygiene
problem — roughly 150 families hold two live household records, plausibly an old
address and a current one, and `Household` exposes no `created_at` or
`updated_at` to tell them apart. Retiring the stale row at the source is the
real fix and is out of scope here.

The honest case for this change is semantic, not accuracy. Where Parent 1 sits
in both competing households, the new value is a different pick, not a verified
better one. Whether that pick is arbitrary or systematic is itself unresolved —
see the consequence on offset-0 ordering below.

## Design

### The rule

Every field on the Focus ADDRESS record comes from the student's primary
contact. One rule, no fallback chain.

Parent 1 is the relationship Finalsite flags `primary`. That flag is a
per-student singleton and is never `false` — it is `true` or `NULL` — so a bare
`where is_primary` selects exactly the Parent 1 row.

### Placement

All changes land in `rpt_focus__addresses` as a self-join through the primary
relationship. Rationale for resolving it here rather than upstream:

- `stg_finalsite__contacts` is contract-enforced and cannot reach the
  relationships array without a staging-to-staging dependency.
- Its `address_*` columns must keep meaning "this contact's own address" — that
  is exactly what its other two consumers need (`rpt_focus__contacts` and
  `int_finalsite__student_contacts.household_address`). Redefining them would
  break both.
- kipptaf's `int_finalsite__student_contacts` unions the NJ regions only and
  deliberately excludes Miami, so its existing `primary_household_ids` anchor is
  not reachable from the Focus feed.
- kipptaf's `stg_finalsite__contact_relationships` **is** a Miami union, so
  `is_primary` is directly joinable here.
- No PowerSchool address extract exists, so no second SIS would inherit a
  shared-package version. Building one would be speculative.

Consequently this is a kipptaf-only change. The kippmiami `rpt_focus__addresses`
wrapper is untouched, no column is added or renamed, and no `source()` column
set changes — so it ships as a single PR with no cross-project staging seeding.

### Shape

```sql
with
    primary_contact as (
        select finalsite_enrollment_id, rel_id,
        from {{ ref("stg_finalsite__contact_relationships") }}
        where is_primary
    )

select
    ida.focus_student_id_prefixed as student_id,

    p1.address_1 as address,
    p1.address_2 as address2,
    p1.city,
    p1.state,
    p1.zip as zipcode,
    p1.phone_1_number as phone,

    cast(null as string) as mailing,
    cast(null as string) as mail_address,
    cast(null as string) as mail_address2,
    cast(null as string) as mail_city,
    cast(null as string) as mail_state,
from {{ ref("stg_finalsite__contacts") }} as c
inner join
    primary_contact as pc
    on c.finalsite_enrollment_id = pc.finalsite_enrollment_id
inner join
    {{ ref("stg_finalsite__contacts") }} as p1
    on pc.rel_id = p1.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on c.finalsite_enrollment_id = l.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on c.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
where
    c.status = 'enrolled'
    and p1.address_1 is not null
    and p1.city is not null
    and p1.state is not null
    and p1.zip is not null
```

The student's own row `c` is retained for the `status = 'enrolled'` filter and
as the relationship join key.

The four-column completeness filter on `p1` excludes a student whose primary
contact exists but has blank address fields, rather than emitting a row with
null address columns. `address_2` is deliberately not filtered — it is
legitimately null. This duplicates the kippmiami wrapper's #4320 completeness
gate in a second layer, which is a knowing trade: the two layers can drift, but
this view no longer claims a completeness it does not enforce, and desired-state
and feed agree on which students have a usable address. It does not change what
Focus receives, because the kippmiami gate already dropped those rows.

Both new joins are `inner`. That is what "emit nothing without a primary
contact" means operationally, and it matches the precedent in
`int_finalsite__student_contacts`, which treats a missing primary flag as a
Finalsite data-entry gap to fix at the source rather than something to infer.

The existing `trunk-ignore(sqlfluff/ST06)` on the final `select` still applies —
column order is fixed by the Focus ADDRESS contract.

### The phone follows the address

`phone` moves from the student's `phone_1_number` to Parent 1's. This is part of
the same one-rule design, and it is materially load-bearing: 1,497 of 1,498
students have a null `phone_1_number`, while 1,414 of their Parent 1 records
carry one. The completeness gate checks only address, city, state and zipcode,
so a record imports with a null phone and can then never be updated. Leaving the
phone on the student record would bake a permanently blank phone into roughly
1,414 Focus address records.

## Measured effect

Against the 1,498 enrolled Miami students currently in the feed:

| Outcome                                               | Students |
| ----------------------------------------------------- | -------- |
| Exported today                                        | 1,406    |
| Exported after this change                            | 1,377    |
| Address unchanged                                     | 1,305    |
| Address changes value                                 | 59       |
| Newly exported — blank today, complete via Parent 1   | 13       |
| — of which had exactly one complete address elsewhere | 9        |
| — of which had no complete address of their own       | 4        |
| Dropped — no primary relationship                     | 35       |
| Dropped — Parent 1's own address incomplete           | 7        |
| Phones newly populated                                | 1,365    |

Net coverage is 29 students lower. Ambiguous cases resolved: 11 of 167.

These are the validated counts, measured by compiling the model against prod and
comparing to the deployed view. The phone figure is 1,365 rather than the ~1,414
first estimated because the completeness filter reduces the row set to 1,377, of
which 12 primary contacts carry no phone.

### Consequences accepted

- **The 7 dropped students have a complete address on their own record** and
  lose it because Parent 1's is blank. This is a new failure mode the rule
  introduces, accepted for consistency with the strict-anchor decision.
- **In 12 ambiguous cases Parent 1's offset-0 household is one the student does
  not belong to**, so the pushed address is Parent 1's residence rather than the
  student's. This is a literal consequence of "the address of their primary
  contact."
- **Parent 1's address is itself offset-0-derived.** Where Parent 1 belongs to
  several households, their own address is an unverified pick, and the student
  inherits it. Resolving that would require the primary-household designation,
  which does not exist in the API. Note the tension with
  `int_finalsite__student_contacts`, which asserts that
  `households[safe_offset(0)]` is the UI's Household 2 for confirmed students:
  if array order were deterministic this would be a systematic pull of the
  secondary household, not a coin flip. That assertion rests on a single
  observed student record from #4610 and was never established for guardian
  contacts, which is a different record type — so it is not evidence of
  determinism here, and this change does not assume either way. Establishing the
  ordering rule would need Finalsite support or a UI-to-API comparison across
  many records.
- **35 students lose their address** because Finalsite has no `primary`
  relationship recorded for them. These should be routed to Ops as a data-entry
  gap.
- **A primary contact absent from the contacts pull is a third exclusion path.**
  The `p1` inner join drops any student whose primary `rel_id` has no row in
  `stg_finalsite__contacts` — possible because relationship links can point at
  people outside the pulled cohort. Zero students hit this today; the validated
  counts leave no room for a third bucket.

## Out of scope

- The 33 students whose offset 0 is blank while exactly one complete address
  sits elsewhere in their own array. 9 are incidentally fixed by this change
  because their Parent 1 happens to carry that address; the remaining 24 are
  not, and a dedicated rule for them is separate work.
- Collapsing the roughly 16 competing address pairs that differ only by
  punctuation, case, or apartment line.
- Retiring duplicate household records in Finalsite. This is the real fix for
  the remaining approximately 150 students and belongs with Miami ops.
- Whether `household_1_id` still earns its place in the staging contract, per
  #4613's own non-goals.

## Testing

- Update the `test_addresses_shape` unit test. It currently mocks only
  `ref('stg_finalsite__contacts')`; it needs a
  `ref('stg_finalsite__contact_relationships')` input and a Parent 1 contact
  row, with the expected address and phone now sourced from that row.
- Add a unit-test case for a student with no `primary` relationship, asserting
  the row is absent from the extract.
- Run the whole directory, not just this model:
  `dbt test --select "test_type:unit,extracts.focus"`. Sibling models mock the
  same refs and break on the same changes. `dbt build` no-ops on a unit-only
  selector.
- The existing `unique` and `not_null` tests on `student_id` guard against a
  duplicate `primary` relationship fanning out the grain — but only partially.
  When two primary contacts exist and one has an incomplete address, the
  completeness filter drops that branch and the duplicate never surfaces, so the
  model resolves it silently. Asserting the singleton at its source
  (`stg_finalsite__contact_relationships`, one `is_primary` row per
  `finalsite_enrollment_id`) would be loud regardless of downstream filters and
  would also protect `int_finalsite__student_contacts`, which depends on the
  same unstated invariant. Tracked as follow-up, not in this change.
- Validate the measured effect against prod before merge by running the compiled
  model and comparing row count and address values to the current extract.

## Documentation

- `rpt_focus__addresses` model description: state that the address and phone are
  the primary contact's, name the enrolled-plus-primary-relationship scope, and
  note that students without a primary relationship are excluded.
- The `address`, `address2`, `city`, `state`, `zipcode` and `phone` column
  descriptions currently say "from Finalsite" — they must say the source is the
  student's primary contact record.
