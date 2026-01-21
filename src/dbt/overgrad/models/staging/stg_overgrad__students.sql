with
    deduplicate as (
        /* students object might contain duplicate ids */
        {{
            dbt_utils.deduplicate(
                relation=source("overgrad", "src_overgrad__students"),
                partition_by="id",
                order_by="id desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        custom_field_values, school, assigned_counselor, academics, student_aid_index
    ),

    cast(student_aid_index as int) as student_aid_index,

    /* records */
    school.id as school__id,
    school.object as school__object,
    school.name as school__name,

    assigned_counselor.id as assigned_counselor__id,
    assigned_counselor.first_name as assigned_counselor__first_name,
    assigned_counselor.last_name as assigned_counselor__last_name,
    assigned_counselor.email as assigned_counselor__email,

    academics.unweighted_gpa as academics__unweighted_gpa,
    academics.weighted_gpa as academics__weighted_gpa,
    academics.projected_act as academics__projected_act,
    academics.projected_sat as academics__projected_sat,
    academics.act_superscore as academics__act_superscore,
    academics.sat_superscore as academics__sat_superscore,
    academics.highest_act as academics__highest_act,
    academics.highest_preact as academics__highest_preact,
    academics.highest_preact_8_9 as academics__highest_preact_8_9,
    academics.highest_aspire_10 as academics__highest_aspire_10,
    academics.highest_aspire_9 as academics__highest_aspire_9,
    academics.highest_sat as academics__highest_sat,
    academics.highest_psat_nmsqt as academics__highest_psat_nmsqt,
    academics.highest_psat_10 as academics__highest_psat_10,
    academics.highest_psat_8_9 as academics__highest_psat_8_9,
from deduplicate
