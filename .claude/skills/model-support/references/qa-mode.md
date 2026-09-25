# QA mode

Check prod values for one family: after new data lands, or after a refactor that
should not change them.

If the family skill has its own QA procedure, read that reference file directly
and follow it instead of everything below; it already knows the grains and
ranges. Do not open the family's `SKILL.md` first: that costs a read the
procedure does not need. CARAT's is
`.claude/skills/carat-dashboard/references/official-scores-qa.md`. Find one with
`ls .claude/skills/<family>/references/`. If there is none, or the family skill
is a single long `SKILL.md` with no `references/`, do not read that file: use
the reference doc and the generic checks below, and suggest restructuring the
skill afterwards (`model-skill.md`).

Otherwise, read the family's reference doc for grains, keys, accepted ranges,
and known issues. Find it with `rg -l '<model>' docs/models`, list its headings
with `rg -n '^#{2,3} ' <doc>`, and Read only the sections for the views or steps
being checked, any section on accepted ranges or benchmarks, and every heading
containing "Known issue" (Read with `offset` and `limit`; long docs truncate).
If there is no doc, run `intake-and-inventory.md` first (consumers and
boundary), then continue here.

## New data landed

Compare prod against the previous load and against the same point last year:

| Check                                    | Query shape                                                 |
| ---------------------------------------- | ----------------------------------------------------------- |
| Rows by grain dimension                  | `count(*)` grouped by school, grade, term, test type        |
| Null rates                               | `countif(<col> is null) / count(*)` per column              |
| Out of range                             | `countif(<col> not between <lo> and <hi>)`; accepted values |
| Categories appeared or gone              | distinct values now vs before                               |
| Schools or students appeared or vanished | key set now `except distinct` key set before, both ways     |

Previous load:
`for system_time as of timestamp_sub(current_timestamp(), interval <n> hour)`.
Time travel reaches 7 days back, and one query can reference a table at only one
timestamp, so run "before" and "now" as separate queries. Same point last year:
filter `academic_year = <current> - 1` at the matching term.

Label every finding "expected" (with the reason) or "needs a look".

## Refactor parity

1. Build the changed `rpt_` views on the dev target. Invoke `dbt-local-dev`
   first: `--defer` and stale dev tables give false differences. Never build
   `--target staging` without the user's explicit go-ahead; it writes shared
   `zz_stg_*` relations. On a PR, the CI schema (`dbt_cloud_pr_<job>_<pr>_*`) is
   a read-only alternative.
2. Diff on each view's key, both directions:

   ```sql
   select 'only_in_dev' as side, count(*) as n,
   from (
       select <key cols>, from `<dev relation>`
       except distinct
       select <key cols>, from `<prod relation>`
   )
   union all
   select 'only_in_prod' as side, count(*) as n,
   from (
       select <key cols>, from `<prod relation>`
       except distinct
       select <key cols>, from `<dev relation>`
   )
   ```

3. On matched keys, count differing rows per column
   (`countif(d.<col> is distinct from p.<col>)`), grouped by school and term.
4. Read the refactor's hunks
   (`git -C <worktree> diff origin/main...HEAD -- <model>.sql`), tie each
   difference to the hunk that explains it, and label it a regression or an
   intended change. A difference no hunk explains is a regression until shown
   otherwise.
5. Extend the diff to every `rpt_` consumer downstream of the changed model.

## Tableau (opt-in)

Only when the warehouse diff is clean and the user needs proof the dashboard
itself matches, because workbook calculations or filters can still differ. Tell
the user it costs a lot of tokens, and wait for a yes before any Tableau MCP
call or loading `tableau-workbook-xml`.

## Where results go

Student-level rows stay in the terminal and the session scratchpad. GitHub gets
aggregates without small cells (`.claude/rules/ferpa-pii.md`).
