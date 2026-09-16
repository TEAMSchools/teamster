with
    enrollments as (
        select distinct
            student_number,
            academic_year,
            schoolid,
            school_name,
            grade_level,
            gender,
            race_ethnicity,
            lunch_status,
            ml_status,
            iep_status,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year in ({{ var("ignite_academic_years") | join(", ") }})
            and grade_level in ({{ var("ignite_grade_levels") | join(", ") }})
            and region in ({{ "'" ~ (var("ignite_regions") | join("', '")) ~ "'" }})
            and student_number is not null
    ),

    /* Mathematica asks for the school the student was enrolled in longest when
     the site-lead list does not name one, so days enrolled is the ranking key.
     One student in academic year 2024 attended both Newark high schools and is
     attributed to the longer of the two enrollments. */
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    ranked as (
        select
            e.student_number,
            e.academic_year,
            e.schoolid,
            e.school_name,
            e.grade_level,
            e.gender,
            e.race_ethnicity,
            e.lunch_status,
            e.ml_status,
            e.iep_status,

            a.days_present,
            a.days_enrolled,

            coalesce(a.days_enrolled, 0) as days_enrolled_rank,
        from enrollments as e
        left join
            {{ ref("int_ignite__attendance") }} as a
            on e.student_number = a.student_number
            and e.academic_year = a.academic_year
            and e.schoolid = a.schoolid
    ),

    scaffold as (
        {{
            dbt_utils.deduplicate(
                relation="ranked",
                partition_by="student_number, academic_year",
                order_by="days_enrolled_rank desc, schoolid asc",
            )
        }}
    ),

    student_treatment as (
        select
            student_number,
            academic_year,
            max(cls_treatment_cp) as treatment_cp,
            max(cls_treatment_rdc) as treatment_rdc,
            max(cls_treatment_rr) as treatment_rr,
        from {{ ref("int_ignite__treatment_assignment") }}
        group by student_number, academic_year
    ),

    assembled as (
        select
            s.academic_year,
            s.school_name,
            s.grade_level,
            s.gender,
            s.race_ethnicity,
            s.lunch_status,
            s.ml_status,
            s.iep_status,

            x.stu_id,

            n.nces_school_id,

            t.treatment_cp,
            t.treatment_rdc,
            t.treatment_rr,

            sa.test_score_m,
            sa.test_grd_m,
            sa.test_subj_m_eoc,
            sa.test_name_m,
            sa.accom_m,
            sa.exemption_m,
            sa.test_score_r,
            sa.test_grd_r,
            sa.test_subj_r_eoc,
            sa.test_name_r,
            sa.accom_r,
            sa.exemption_r,

            ia.iready_boy_score_r,
            ia.iready_eoy_score_r,
            ia.iready_boy_score_m,
            ia.iready_eoy_score_m,

            cast(s.days_present as int64) as days_present,
            cast(s.days_enrolled as int64) as days_enrolled,
        from scaffold as s
        inner join
            {{ ref("int_ignite__student_id_crosswalk") }} as x
            on s.student_number = x.student_number
        left join
            {{ ref("seed_ignite__school_nces_ids") }} as n on s.schoolid = n.schoolid
        left join
            student_treatment as t
            on s.student_number = t.student_number
            and s.academic_year = t.academic_year
        left join
            {{ ref("int_ignite__state_assessment") }} as sa
            on s.student_number = sa.student_number
            and s.academic_year = sa.academic_year
        left join
            {{ ref("int_ignite__interim_assessment") }} as ia
            on s.student_number = ia.student_number
            and s.academic_year = ia.academic_year
    ),

    derived as (
        select
            stu_id,
            school_name,
            grade_level,
            gender,
            test_score_m,
            test_grd_m,
            test_subj_m_eoc,
            test_name_m,
            accom_m,
            exemption_m,
            test_score_r,
            test_grd_r,
            test_subj_r_eoc,
            test_name_r,
            accom_r,
            exemption_r,
            iready_boy_score_r,
            iready_eoy_score_r,
            iready_boy_score_m,
            iready_eoy_score_m,
            days_present,
            days_enrolled,

            nces_school_id as school_id,

            academic_year + 1 as school_year,

            coalesce(treatment_cp, 0) as treatment_cp,
            coalesce(treatment_rdc, 0) as treatment_rdc,
            coalesce(treatment_rr, 0) as treatment_rr,

            if(race_ethnicity = 'W', 1, 0) as white,
            if(race_ethnicity = 'B', 1, 0) as black,
            if(race_ethnicity = 'A', 1, 0) as asian,
            if(race_ethnicity = 'I', 1, 0) as amindian,
            if(race_ethnicity = 'T', 1, 0) as multirace,
            if(race_ethnicity = 'H', 1, 0) as hispanic,
            if(race_ethnicity is null, 1, 0) as missrace,
            if(lunch_status in ('F', 'R'), 1, 0) as frpl,
            if(ml_status = 'ML', 1, 0) as ell,
            if(iep_status = 'Has IEP', 1, 0) as iep,
        from assembled
    )

select
    stu_id,
    school_year,
    school_id,
    school_name,
    treatment_cp,
    treatment_rdc,
    treatment_rr,
    grade_level,
    gender,
    white,
    black,
    asian,
    amindian,
    multirace,
    missrace,
    hispanic,
    frpl,
    ell,
    iep,
    days_present,
    days_enrolled,
    test_score_m,
    test_grd_m,
    test_subj_m_eoc,
    test_name_m,
    accom_m,
    exemption_m,
    test_score_r,
    test_grd_r,
    test_subj_r_eoc,
    test_name_r,
    accom_r,
    exemption_r,
    iready_boy_score_r,
    iready_eoy_score_r,
    iready_boy_score_m,
    iready_eoy_score_m,
from derived
