# Score the measures a student sat in a partial DIBELS PM round

Issue: #6493. Short design (small change).

## Intent

On the Literacy Dashboard's Aimline tabs, a student who sat some of a progress
monitoring round's measures but not all of them reads `Round Incomplete` on
every measure under the default view (Granularity `Measure Standard`, Comparison
Item `Aimline and Benchmark`), including the measures they sat. Middle schoolers
who sat ORF but not yet Maze are most of these students, and their ORF results
are hidden until they finish.

Academics decided on 2026-11-24:

1. Score each measure the student sat with the usual rules.
2. Keep `Round Incomplete` at Round granularity, and keep the headline Round
   Incomplete tile as it is.
3. Aimline tabs only. The Internal PM tabs do not change.

## Goals, non-goals, anti-goals

- Goal: under `Aimline and Benchmark` at Measure Standard and Measure
  granularity, each sat measure shows its verdict (Below Aimline, Meeting
  Aimline split by benchmark, or No Aimline Data split by benchmark), and each
  measure not sat shows `Not Tested`, as it does today.
- Goal: the ⏳ Round Incomplete tile counts the same students it counts today,
  at every granularity.
- Non-goals: the Internal chain; the Round granularity; the landing-page
  participation views; the Cube facts (#6473 follows this rule later).
- Anti-goals: the default view losing its count of students still testing; any
  Internal row changing; a tile and a bar disagreeing on a scored student's
  verdict.

## Approaches

Considered for the ⏳ tile on the default view:

- A. Let the tile follow the bars. At Measure Standard and Measure the tile
  drops to about zero, and `Round Incomplete` appears only at Round granularity.
  dbt-only, and the tiles still add to 100%. Rejected: the default view loses
  the still-testing count academics asked to keep.
- B. Keep the tile counting students who have not finished the round, beside
  their scores. Chosen by the dashboard owner on 2026-11-24. While a round is
  open, one student can count in both ⏳ and a verdict tile, so the tiles can
  add to more than 100%.

## Design

### dbt: `int_amplify__pm_met_criteria_aimline`

- `aimline_category` drops its first branch,
  `when not completed_test_round then 'Round Incomplete'`. Every row of this
  model is a measure the student sat, so each now gets its verdict.
- `measure_name_code_aimline_benchmark_status` drops its `Round Incomplete`
  branch, which can no longer fire.
- `aimline_round_category` keys its `Round Incomplete` branch on
  `completed_test_round` directly. Today it counts
  `aimline_category = 'Round Incomplete'`, which would silently stop firing.
  `rpt_tableau__dibels_dashboard` already takes this state from the roster's
  `round_test_status`, so the dashboard's Round view does not move either way.
- `pm_round_status` and `round_benchmark_status` already key on
  `completed_test_round` and do not change.

### Workbook: the ⏳ tile

`BAN 5 - Numerator` reads `[BAN Category] = 'Round Incomplete'` today. It
becomes:

```text
COUNTD(IF [round_test_status] = 'Round Incomplete'
       AND [measure_test_status] = 'Tested'
       THEN [student_number] END)
```

On today's data this matches the current tile row for row in academic years 2025
and 2026, so it can ship before the dbt change without moving a number. The
other tiles keep reading `BAN Category`, which now carries the scored verdicts.
The tile's title does not change.

### Ship order

1. Publish the workbook edit (no visible change), through the
   `tableau-workbook-xml` skill and its production gate.
2. Merge the dbt change. The scores appear on the next extract refresh.

### Docs

- `docs/models/dibels-dashboard-data-model.md`: the "Partial rounds" row and the
  matching _Labels and reporting_ bullet. Also fix the stale "Uncoloured No
  Aimline Data categories" row (production colours them `#1170aa` and
  `#ffbc79`).
- `dibels-dashboard` skill, `references/aimline-method.md`: the partial-round
  rule, the "Do not align the two" note, and the BAN note. The BANs follow
  Granularity through the `BAN Category` calc, not always `aimline_category`.
- Column descriptions in both properties files.

## Calls made here, for the owner to check

- The rule applies to every academic year, so academic year 2025 history shifts
  too. One rule is simpler to explain than a cutover year.
- The Category Status Over Time line follows the bars, so at Measure Standard
  and Measure it loses its Round Incomplete band. The incomplete state stays on
  the ⏳ tile, at Round granularity, and in `round_test_status`, which keeps the
  percent-tested states (fully tested, incomplete, not tested) apart.
- The ⏳ tile's title stays as it is, although the tiles can now add to more
  than 100% during an open round.

## Left to the builder

- Test shape: a dbt unit test on `int_amplify__pm_met_criteria_aimline` for a
  student who sat one of two measures, covering all three changed columns.
- Proof: a dev build of `rpt_tableau__dibels_dashboard` against prod. Only rows
  whose `aimline_category` or `measure_name_code_aimline_benchmark_status` read
  `Round Incomplete` change; Internal rows and every round-grain column are
  identical.
- Render the ⏳ tile and the bars at all three granularities before and after.
