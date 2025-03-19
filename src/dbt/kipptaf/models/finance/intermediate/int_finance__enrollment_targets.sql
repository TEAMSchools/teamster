select
    et.fiscal_year,
    et.academic_year,
    et.region,
    et.schoolid,
    et.school_name,
    et.grade_level,
    et.target_enrollment,
    et.adjustment,
    et.attrition_factor,
    et.financial_model_enrollment,
    et.grade_band_ratio,
    et.at_risk_and_lep_ratio,
    et.at_risk_only_ratio,
    et.lep_only_ratio,
    et.sped_ratio,

    sch._dbt_source_relation,
from {{ ref("stg_finance__enrollment_targets") }} as et
inner join
    {{ ref("stg_powerschool__schools") }} as sch on et.schoolid = sch.school_number
