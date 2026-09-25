# SAT and PSAT — crosswalk match

SAT and PSAT share one crosswalk tab, `src_collegeboard__sat_id_crosswalk`, and
both unpivots (`int_collegeboard__sat_unpivot`,
`int_collegeboard__psat_unpivot`) resolve `cb_id` through it with a left join.
AP IDs are a different ID space — see [SKILL.md](../SKILL.md).

The two feed different places. PSAT flows into the CARAT dashboard. SAT feeds
only the KIPP Forward SAT sheets (`rpt_gsheets__kippfwd_ogsat`, `_sfsat`, in the
Unified KFWD Processes Document). Those sheets list the College Board SAT scores
Salesforce doesn't have yet, and the data team loads them into Salesforce. CARAT
reads SAT from kippadb, so a newly matched SAT score shows on the dashboard only
after it's loaded. Tell the user which one a paste affects, and for SAT, that
the new rows are now on the sheet waiting to be loaded.

## Step 1: Ingestion check

Compare `mcp__dagster__get_asset_materializations` for the raw asset
(`kipptaf/collegeboard/sat` or `kipptaf/collegeboard/psat`) against its staging
model (`kipptaf/collegeboard/stg_collegeboard__sat` or `__psat`). A raw
materialization newer than staging's last one means staging has not rebuilt. Ask
before launching anything, the same way as AP Phase 1 in [ap.md](ap.md).

## Step 2: Count the gaps

```sql
with
    ids as (
        select 'SAT' as test, cb_id,
        from `teamster-332318.kipptaf_collegeboard.stg_collegeboard__sat`
        union all
        select 'PSAT' as test, cb_id,
        from `teamster-332318.kipptaf_collegeboard.stg_collegeboard__psat`
    )

select
    ids.test,
    count(distinct ids.cb_id) as distinct_cb_ids,
    count(distinct if(xw.college_board_id is null, ids.cb_id, null)) as gaps,
from ids
left join
    `teamster-332318.kipptaf_google_sheets.stg_google_sheets__collegeboard__sat_id_crosswalk`
    as xw
    on ids.cb_id = xw.college_board_id
group by ids.test
```

Baseline for comparison: zero gaps on 2026-09-24, with 897 SAT and 2,183 PSAT
IDs all mapped. Report today's counts and ask before running the match.

## Step 3: Run the tiered match

```bash
uv run dbt compile --select "path:analyses/collegeboard_sat_psat_tiered_crosswalk_match.sql" \
    --project-dir src/dbt/kipptaf --target prod
```

Run the compiled SQL
(`src/dbt/kipptaf/target/compiled/kipptaf/analyses/collegeboard_sat_psat_tiered_crosswalk_match.sql`)
via the BigQuery MCP. Its header comment defines the tiers. The one AP lacks is
Tier S: SAT and PSAT files carry `secondary_id`, which schools fill with the
PowerSchool `student_number`, accepted only when the DOB also agrees.
`district_student_id` is almost never filled (10 of 4,405 rows) and never agrees
with the crosswalk; ignore it.

Validated 2026-09-24 by running every current ID through the match
(`--vars '{sat_psat_match_all_ids: true}'`) and scoring it against the
crosswalk: all 3,035 `resolved` rows agreed, 30 went to `flagged_for_review` (7
of them Tier S rows whose `secondary_id` named the wrong student), 1 was
`ambiguous`, and 14 were `no_match`. Rerun that validation after changing a
tier.

## Step 4: Deliver, paste, reconcile

Present counts per tier and bucket, then follow _Handing rows to the user_ in
[SKILL.md](../SKILL.md) with destination tab
`src_collegeboard__sat_id_crosswalk`. `flagged_for_review` rows go in chat as a
table (CB name/DOB/gender against PS name/DOB/gender) for the user to decide
individually. `ambiguous` rows (several candidates the first-name tiebreak
couldn't narrow) go in chat the same way, with the candidates listed. For
`no_match` rows, run _No-match root cause review_ in [ap.md](ap.md).

## Step 5: Pipeline QA

Run _Pipeline QA after a crosswalk update_ in [SKILL.md](../SKILL.md).

## Gotcha: unresolved SAT scores vanish instead of showing as unmatched

`int_collegeboard__sat_unpivot` deduplicates on `powerschool_student_number`
(latest `report_date` wins) after the crosswalk left join. Every unresolved row
has a null student number, so they all fall into one partition and only one
survives. A backlog of SAT gaps therefore shows up downstream as a single
null-student row, not as one per student. Count gaps from staging (Step 2),
never from the unpivot. PSAT does not deduplicate, so its unresolved rows
survive with a null student number.
