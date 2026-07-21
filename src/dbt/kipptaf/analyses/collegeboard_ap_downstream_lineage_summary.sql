-- Downstream Lineage Verification -- Summary
--
-- Confirms a crosswalk fix actually reaches int_collegeboard__ap_unpivot and
-- the CARAT dashboard (rpt_tableau__ap_assessment_dashboard), not just the
-- crosswalk sheet. rpt_tableau__ap_assessment_dashboard lives in the
-- kipptaf_tableau dataset (not a generic 'extracts' dataset -- confirmed via
-- INFORMATION_SCHEMA, don't guess). The dashboard's actual Tableau workbook
-- is the 'College Admission Readiness Assessments Tracker (CARAT)' exposure
-- in src/dbt/kipptaf/models/exposures/tableau.yml
-- (name: college_admission_readiness_assessments_tracker_carat, LSID
-- 286156c4-2f9e-4983-926b-63c9b11f44f4, Dagster-owned refresh cron
-- '0 6 * * *') -- use the exposure file to find the workbook, don't guess at
-- names. Since the BQ table is a live VIEW, this count comparison already
-- reflects what a live Tableau connection would show; only cross-check via
-- the Tableau MCP (get-workbook / list-datasources with the LSID) if the
-- workbook turns out to use an extract instead.
--
-- Defaults to the network's current_academic_year -- override at compile
-- time for a different cycle: --vars '{current_academic_year: <year>}'.
--
-- kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves is
-- a dbt test's store_failures output, not a ref()-able dbt node -- kept as a
-- literal fully-qualified path.
with
    crosswalk_gaps as (
        select count(*) as remaining_crosswalk_gaps,
        from
            -- trunk-ignore(sqlfluff/LT05): fully-qualified test-audit path, can't wrap
            `teamster-332318`.kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves
    ),

    unpivot_count as (
        select count(*) as unpivot_rows,
        from {{ ref("int_collegeboard__ap_unpivot") }}
        where academic_year = {{ var("current_academic_year") }}
    ),

    dashboard_count as (
        select count(*) as dashboard_scored_rows,
        from {{ ref("rpt_tableau__ap_assessment_dashboard") }}
        where
            academic_year = {{ var("current_academic_year") }} and test_name is not null
    )

select cg.remaining_crosswalk_gaps, uc.unpivot_rows, dc.dashboard_scored_rows,
from crosswalk_gaps as cg
cross join unpivot_count as uc
cross join dashboard_count as dc
