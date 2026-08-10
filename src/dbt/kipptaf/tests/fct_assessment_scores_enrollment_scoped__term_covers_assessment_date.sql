-- Asserts that a score's resolved reporting quarter actually contains the date
-- the score was administered or taken. Guards the #4484 regression: term_key
-- resolved at any grain coarser than the score row (via the section enrollment,
-- or via int_assessments__resolved_section_enrollments' per-score-GRAIN anchor
-- date) assigns quarters that do not cover the row's own date.
select
    f.assessment_score_key,
    f.assessment_date_key,

    t.term_name,
    t.`start_date`,
    t.end_date,
from {{ ref("fct_assessment_scores_enrollment_scoped") }} as f
inner join {{ ref("dim_terms") }} as t on f.term_key = t.term_key
where f.assessment_date_key < t.`start_date` or f.assessment_date_key > t.end_date
