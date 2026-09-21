-- Both branches of int_google_sheets__kippfwd__goals_unpivot are driven from the
-- scaffold, so a goal whose score type has no scaffold row does not appear at all
-- rather than appearing with a null threshold. This surfaces those goals, which
-- would otherwise be stated by KIPP Forward and silently unreported.
--
-- psat10nmsqt_total is expected to fail here today: it is a combined PSAT10 and
-- PSAT NMSQT goal with no scaffold equivalent, because a combined row has no
-- single honest expected_scope. Adding one means widening the scaffold's
-- expected_scope accepted values to admit PSAT10/NMSQT. TODO(#4658).
select
    g.academic_year, g.test_type, g.grade_level, g.score_type, g.expected_metric_type,

from {{ ref("stg_google_sheets__kippfwd__goals") }} as g
left join
    {{ ref("stg_google_sheets__kippfwd__scaffold") }} as s
    on g.academic_year = s.academic_year
    and g.test_type = s.expected_test_type
    and g.score_type = s.expected_score_type
where s.expected_score_type is null
