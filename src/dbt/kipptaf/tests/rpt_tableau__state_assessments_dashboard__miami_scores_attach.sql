-- Guards the FLDOE leg of the dashboard's assessment_scores union. That leg
-- once emitted `null as localstudentidentifier` while the attaching join
-- inner-joins on exactly that column, so every Florida score was discarded and
-- the dashboard held zero Miami rows in every year while every test stayed
-- green -- the breakage produced no error, only absent rows (#5042). A revert
-- to a null or a state-only id would re-drop them just as quietly, so assert
-- the rows are present rather than trusting the union leg to stay correct.
--
-- Deliberately a presence check, not a count floor: Miami's row count moves
-- with enrollment and with which FAST windows have landed, so a floor would
-- either drift stale or fire on real change. Zero rows is the only value that
-- is always wrong.
with
    miami_rows as (
        select countif(region = 'Miami') as miami_row_count,
        from {{ ref("rpt_tableau__state_assessments_dashboard") }}
    )

select miami_row_count,
from miami_rows
where miami_row_count = 0
