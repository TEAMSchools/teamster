{% set quarter = ["Q1", "Q2", "Q3", "Q4", "Y1"] %}

with
    student_roster as (
        select
            enr._dbt_source_relation,
            enr.academic_year,
            enr.yearid,
            enr.region,
            enr.school_level,
            enr.schoolid,
            enr.school_abbreviation as school,
            enr.studentid,
            enr.student_number,
            enr.lastfirst,
            enr.gender,
            enr.enroll_status,
            enr.grade_level,
            enr.ethnicity,
            enr.cohort,
            enr.year_in_school,
            enr.advisor_lastfirst as advisor_name,
            enr.is_out_of_district,
            enr.lep_status,
            enr.is_504,
            enr.is_self_contained as is_pathways,
            enr.lunch_status,
            enr.year_in_network,
            enr.is_retained_year,
            enr.is_retained_ever,
            enr.rn_undergrad,

            ktc.contact_id as salesforce_id,
            ktc.ktc_cohort,

            hos.head_of_school_preferred_name_lastfirst as hos,

            quarter,

            'Local' as roster_type,

            if(
                enr.school_level in ('ES', 'MS'), advisory_name, advisor_lastfirst
            ) as advisory,

            if(enr.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

            case
                when quarter in ('Q1', 'Q2')
                then 'S1'
                when quarter in ('Q3', 'Q4')
                then 'S2'
                else 'S#'  -- for Y1
            end as semester,

            case when sp.studentid is not null then 1 end as is_counseling_services,

            case when sa.studentid is not null then 1 end as is_student_athlete,

            round(ada.ada, 3) as ada,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        left join
            {{ ref("int_kippadb__roster") }} as ktc
            on enr.student_number = ktc.student_number
        left join
            {{ ref("int_powerschool__spenrollments") }} as sp
            on enr.studentid = sp.studentid
            and current_date('America/New_York') between sp.enter_date and sp.exit_date
            and sp.specprog_name = 'Counseling Services'
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="sp") }}
        left join
            {{ ref("int_powerschool__spenrollments") }} as sa
            on enr.studentid = sa.studentid
            and sa.specprog_name = 'Student Athlete'
            and current_date('America/New_York') between sa.enter_date and sa.exit_date
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="sa") }}
        left join
            {{ ref("int_powerschool__ada") }} as ada
            on enr.yearid = ada.yearid
            and enr.studentid = ada.studentid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="ada") }}
        left join
            {{ ref("int_people__leadership_crosswalk") }} as hos
            on enr.schoolid = hos.home_work_location_powerschool_school_id
        cross join unnest({{ quarter }}) as quarter
        where
            enr.rn_year = 1
            and enr.grade_level != 99
            and not enr.is_out_of_district
            and enr.academic_year = {{ var("current_academic_year") }}
    ),

    transfer_roster as (
        select distinct
            tr._dbt_source_relation,
            tr.academic_year,
            tr.yearid,
            tr.studentid,
            tr.grade_level,

            'Q#' as quarter,
            'S#' as semester,

            'Transfer' as roster_type,

            coalesce(co.region, e1.region) as region,
            coalesce(co.school_level, e1.school_level) as school_level,
            coalesce(co.schoolid, e1.schoolid) as schoolid,
            coalesce(co.school, e1.school) as school,
            coalesce(co.student_number, e1.student_number) as student_number,
            coalesce(co.lastfirst, e1.lastfirst) as lastfirst,
            coalesce(co.gender, e1.gender) as gender,
            coalesce(co.enroll_status, e1.enroll_status) as enroll_status,
            coalesce(co.ethnicity, e1.ethnicity) as ethnicity,
            coalesce(co.cohort, e1.cohort) as cohort,
            coalesce(co.year_in_school, e1.year_in_school) as year_in_school,
            coalesce(co.advisor_name, e1.advisor_name) as advisor_name,
            coalesce(
                co.is_out_of_district, e1.is_out_of_district
            ) as is_out_of_district,
            coalesce(co.lep_status, e1.lep_status) as lep_status,
            coalesce(co.is_504, e1.is_504) as is_504,
            coalesce(co.is_pathways, e1.is_pathways) as is_pathways,
            coalesce(co.lunch_status, e1.lunch_status) as lunch_status,
            coalesce(co.year_in_network, e1.year_in_network) as year_in_network,
            coalesce(co.is_retained_year, e1.is_retained_year) as is_retained_year,
            coalesce(co.is_retained_ever, e1.is_retained_ever) as is_retained_ever,
            coalesce(co.rn_undergrad, e1.rn_undergrad) as rn_undergrad,
            coalesce(co.salesforce_id, e1.salesforce_id) as salesforce_id,
            coalesce(co.ktc_cohort, e1.ktc_cohort) as ktc_cohort,
            coalesce(co.hos, e1.hos) as hos,
            coalesce(co.advisory, e1.advisory) as advisory,
            coalesce(co.iep_status, e1.iep_status) as iep_status,
            coalesce(co.is_counseling_services, 0) as is_counseling_services,
            coalesce(co.is_student_athlete, 0) as is_student_athlete,
            coalesce(co.ada, e1.ada) as ada,
        from {{ ref("stg_powerschool__storedgrades") }} as tr
        left join
            student_roster as co
            on tr.academic_year = co.academic_year
            and tr.schoolid = co.schoolid
            and tr.studentid = co.studentid
            and {{ union_dataset_join_clause(left_alias="tr", right_alias="co") }}
        left join
            student_roster as e1
            on tr.schoolid = e1.schoolid
            and tr.studentid = e1.studentid
            and e1.year_in_school = 1
            and {{ union_dataset_join_clause(left_alias="tr", right_alias="e1") }}
        where
            tr.academic_year = {{ var("current_academic_year") }}
            and tr.storecode = 'Y1'
            and tr.is_transfer_grade
    ),

    students as (
        select
            _dbt_source_relation,
            academic_year,
            yearid,
            region,
            school_level,
            schoolid,
            school,
            studentid,
            student_number,
            lastfirst,
            gender,
            enroll_status,
            grade_level,
            ethnicity,
            cohort,
            year_in_school,
            advisor_name,
            is_out_of_district,
            lep_status,
            is_504,
            is_pathways,
            lunch_status,
            year_in_network,
            is_retained_year,
            is_retained_ever,
            rn_undergrad,
            salesforce_id,
            ktc_cohort,
            hos,
            advisory,
            iep_status,
            is_counseling_services,
            is_student_athlete,
            ada,
            roster_type,
            semester,
            quarter,

        from student_roster

        union all

        select
            _dbt_source_relation,
            academic_year,
            yearid,
            region,
            school_level,
            schoolid,
            school,
            studentid,
            student_number,
            lastfirst,
            gender,
            enroll_status,
            grade_level,
            ethnicity,
            cohort,
            year_in_school,
            advisor_name,
            is_out_of_district,
            lep_status,
            is_504,
            is_pathways,
            lunch_status,
            year_in_network,
            is_retained_year,
            is_retained_ever,
            rn_undergrad,
            salesforce_id,
            ktc_cohort,
            hos,
            advisory,
            iep_status,
            is_counseling_services,
            is_student_athlete,
            ada,
            roster_type,
            semester,
            quarter,

        from transfer_roster
    )

select *
from students
