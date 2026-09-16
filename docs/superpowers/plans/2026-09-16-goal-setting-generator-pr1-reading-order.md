# PR 1 reading order

Read in this order. Each file says what to check. Every test name says which
methodology rule or failure it covers; read the test before the module.

1. `config/goal_setting/ay2026.yaml` and `ps_programs.yaml`. Check: the two
   groups match the SY27 decisions in the handoff. The `nj_math_1_2` group's
   Bucket 3 is `stretch_reachers`, per the SY27 decisions memo; the K group's
   Bucket 3 and both groups' `to_buckets` are open items marked in comments.
2. `tests/goal_setting/test_school_goal.py` then
   `src/teamster/goal_setting/rules/school_goal.py`. Check: the regression test
   reproduces the SY27 one-off to the cent. The formula is in the Global
   Constraints of the plan.
3. `tests/goal_setting/test_bucket2.py` then `rules/bucket2.py`. Check: ties at
   the cutoff are all admitted under `admit`.
4. `tests/goal_setting/test_bucket3.py`, `test_assign.py`, then
   `rules/bucket3.py` and `rules/assign.py`. Check: a below student whose
   stretch level is proficient enters Bucket 3; untested never does.
5. `tests/goal_setting/test_invariants.py` then `rules/invariants.py`. Check:
   every message names region, school, grade, subject.
6. `tests/goal_setting/test_freshness.py` then `rules/freshness.py`. Check:
   error versus warning split.
7. `adapters/iready_boy.py`. Check the SQL against
   `rpt_tableau__academic_goals_rollup.sql` roster filters and the crosswalk
   join. The join keys on region through the `IREADY_REGION` mapping because
   i-Ready labels districts by name, and student numbers repeat across
   PowerSchool instances. This is the one file where a wrong column name would
   be silent.
8. `pipeline.py`. Check the order: gate, classify, goals, bucket 2, bucket 3,
   finalize, invariants.
9. `__main__.py`. Check that nothing is written before the invariants and the
   diff verdict.
10. `tests/goal_setting/test_cli.py`. Check that
    `test_reclassification_exits_nonzero_without_flag` proves nothing is written
    when a re-run would move an already-proposed student, and that
    `test_replay_from_inputs_is_byte_identical` proves a saved run replays
    exactly.

Skip on first read: `archive.py`, `manifest.py`, `outputs.py`, `diff.py`,
`show.py`. They move data; their tests describe the file shapes.
