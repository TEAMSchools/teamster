-- Guards the FLDOE leg of both state-assessment models. The dashboard once
-- emitted `null as localstudentidentifier` while its attaching join inner-joins
-- on exactly that column, and the comps model joined
-- e.state_studentnumber = a.student_id, which is null for every Miami row under
-- Focus. Both discarded every Florida score and held zero Miami rows in every
-- year while every test stayed green -- the breakage produced no error, only
-- absent rows (#5042). A revert to either key would re-drop Miami just as
-- quietly, so assert the rows are present rather than trusting the joins to
-- stay correct.
--
-- Deliberately a presence check, not a count floor: Miami's row count moves
-- with enrollment and with which FAST windows have landed, so a floor would
-- either drift stale or fire on real change. Zero rows is the only value that
-- is always wrong.
with
    miami_rows as (
        select
            'rpt_tableau__state_assessments_dashboard' as model_name,
            countif(region = 'Miami') as miami_row_count,
        from {{ ref("rpt_tableau__state_assessments_dashboard") }}

        union all

        select
            'int_tableau__state_assessments_demographic_comps' as model_name,
            countif(district_state = 'KTAF FL') as miami_row_count,
        from {{ ref("int_tableau__state_assessments_demographic_comps") }}
    )

select model_name, miami_row_count,
from miami_rows
where miami_row_count = 0
