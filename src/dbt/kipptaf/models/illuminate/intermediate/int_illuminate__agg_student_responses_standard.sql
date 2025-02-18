{{- config(materialized="view") -}}

select
    asr.*,

    astd.performance_band_set_id,

    std.custom_code,
    std.description as standard_description,

    rstd.description as root_standard_description,
from {{ ref("stg_illuminate__dna_assessments__agg_student_responses_standard") }} as asr
inner join
    {{ ref("stg_illuminate__dna_assessments__assessment_standards") }} as astd
    on asr.assessment_id = astd.assessment_id
    and asr.standard_id = astd.standard_id
inner join
    {{ ref("stg_illuminate__standards__standards") }} as std
    on asr.standard_id = std.standard_id
left join
    {{ ref("int_illuminate__root_standards") }} as rs
    on asr.standard_id = rs.standard_id
left join
    {{ ref("stg_illuminate__standards__standards") }} as rstd
    on rs.root_standard_id = rstd.standard_id
