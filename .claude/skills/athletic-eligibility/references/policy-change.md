# Changing the rules to match the policy

For a new policy year, a policy edit, or a region-specific rule such as high
school ADA weighting. Work on a feature branch (root CLAUDE.md).

A single rule change that the report's Teaching and Learning owner already
confirmed in writing (such as one region's ADA weighting) skips steps 1 and 2:
state the one rule, then start at step 3. Ask the user for the policy doc link;
it is not in the repo.

## 1. Read the policy

- Read the policy doc with the Google Drive tools (`read_file_content`). A Doc's
  tabs arrive as `#` headings; list them first, then read the policy tabs and
  the Reporting tab. `get_file_metadata` gives its last-modified date.
- The Drive tools run as the user, so no sharing is needed for a Doc.

## 2. Build the rule table and diff it

For each quarter (Q1, Q2, Q3 and Q4) and each band (high school, middle school),
write down: the credit rule, which GPA, which ADA and whether it is weighted,
the cut points, and the exemptions. Put it next to the current table in the
reference doc's "Steps" section and list every difference.

Confirm the list with the user before coding. Each difference changes what
schools see on the sheet mid-season.

## 3. Change one rule at a time, test first

1. Add a unit test to `unit_tests:` in
   `src/dbt/kipptaf/models/students/intermediate/properties/int_students__athletic_eligibility.yml`.
   Copy the shape of the existing two: one student per case, the four mocked
   refs, `current_academic_year` pinned, and only the columns the case needs.
   Last year's GPA is a `int_powerschool__gpa_term_pivot` row with `yearid` one
   less than this year's; last year's credits are
   `stg_powerschool__storedgrades` Y1 rows for `academic_year - 1`.
2. Run it and watch it fail:

   ```bash
   cd <worktree> && uv run dbt test --select "int_students__athletic_eligibility,test_type:unit" \
     --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
     --project-dir src/dbt/kipptaf
   ```

3. Edit the `case` branches. Check the branch order: a rule that should win must
   come before any branch that also matches the row.
4. Run it again and watch it pass.

A region-specific rule adds `_dbt_source_project = '<region>'` to the high
school branches it applies to, where `<region>` is `kippnewark`, `kippcamden`,
or `kipppaterson`, and a second branch without it keeps the other regions' rule.
The unweighted current-year columns are `cy_unweighted_term_q1` and
`cy_unweighted_s1_ada`.

## 4. Measure the change against prod

```bash
cd <worktree> && uv run dbt compile --select int_students__athletic_eligibility --target dev \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir src/dbt/kipptaf
cd /workspaces/teamster && uv run python <worktree>/.claude/skills/athletic-eligibility/scripts/status_diff.py \
  <worktree>/src/dbt/kipptaf/target/compiled/kipptaf/models/students/intermediate/int_students__athletic_eligibility.sql \
  <scratchpad>/athletic_eligibility_status_changes.tsv
```

It prints status transitions by quarter and band, and writes the student list to
the TSV. Every transition must be explained by a rule you changed. A status that
turns blank is a branch-order bug until shown otherwise. Report the count of
students who lose eligibility.

## 5. Update the doc and YAML

- The reference doc's "Steps" tables, and "Known issues" or "Open questions" if
  the change resolves one.
- The `q*_ae_status` descriptions in the model's properties YAML.
- Then the model-support skill's checks: cold review of the edited doc sections,
  `dbt parse --no-partial-parse`, trunk.
