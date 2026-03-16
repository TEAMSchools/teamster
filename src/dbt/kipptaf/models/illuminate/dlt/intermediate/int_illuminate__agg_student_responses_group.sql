select
    asr.student_assessment_id,
    asr.assessment_id,
    asr.reporting_group_id,
    asr.student_id,
    asr.performance_band_id,
    asr.performance_band_level,
    asr.mastered,
    asr.points,
    asr.points_possible,
    asr.answered,
    asr.percent_correct,
    asr.number_of_questions,
    asr.raw_score,
    asr.raw_score_mastered,
    asr.raw_score_possible,

    arg.performance_band_set_id,
    arg.sort_order,

    rg.label,
from {{ ref("stg_illuminate__dna_assessments__agg_student_responses_group") }} as asr
inner join
    {{ ref("stg_illuminate__dna_assessments__assessments_reporting_groups") }} as arg
    on asr.assessment_id = arg.assessment_id
    and asr.reporting_group_id = arg.reporting_group_id
inner join
    {{ ref("stg_illuminate__dna_assessments__reporting_groups") }} as rg
    on asr.reporting_group_id = rg.reporting_group_id
