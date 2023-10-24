with
    enrollment_union as (
        select
            e.id as enrollment_id,
            e.student,
            e.start_date,
            ifnull(
                e.actual_end_date, date({{ var("current_fiscal_year") }}, 6, 30)
            ) as actual_end_date,
            if(e.status = 'Graduated', 1, 0) as is_graduated,
            if(
                e.pursuing_degree_type
                in ("Bachelor's (4-year)", "Associate's (2 year)", 'Certificate'),
                1,
                null
            ) as is_ecc_degree_type,
            case
                when e.pursuing_degree_type = "Bachelor's (4-year)"
                then 'BA'
                when e.pursuing_degree_type = "Associate's (2 year)"
                then 'AA'
                when e.pursuing_degree_type in ("Master's", 'MBA')
                then 'Graduate'
                when e.pursuing_degree_type in ('High School Diploma', 'GED')
                then 'Secondary'
                when e.pursuing_degree_type = 'Elementary Certificate'
                then 'Primary'
                when
                    e.pursuing_degree_type = 'Certificate'
                    and ifnull(e.account_type, '') not in (
                        'Traditional Public School',
                        'Alternative High School',
                        'KIPP School'
                    )
                then 'Vocational'
            end as pursuing_degree_level,

            if(
                date(
                    extract(year from c.contact_actual_hs_graduation_date),
                    10,
                    31
                ) between e.start_date and ifnull(
                    e.actual_end_date, date({{ var("current_fiscal_year") }}, 6, 30)
                ),
                1,
                0
            ) as is_ecc_dated,

            0 as is_employment,
        from {{ ref("stg_kippadb__enrollment") }} as e
        inner join {{ ref("base_kippadb__contact") }} as c on e.student = c.contact_id
        where e.status != 'Did Not Enroll'

        union all

        select
            id as enrollment_id,
            contact,
            coalesce(
                `start_date`, enlist_date, bmt_start_date, meps_start_date
            ) as `start_date`,
            ifnull(
                coalesce(end_date, discharge_date, bmt_end_date, meps_end_date),
                date({{ var("current_fiscal_year") }}, 6, 30)
            ) as actual_end_date,
            null as is_graduated,
            null as is_ecc_degree_type,
            'Employment' as pursuing_degree_level,
            null as is_ecc_dated,
            1 as is_employment,
        from {{ ref("stg_kippadb__employment") }}
    ),

    enrollment_ordered as (
        select
            student,
            enrollment_id,
            pursuing_degree_level,
            is_ecc_degree_type,
            is_ecc_dated,
            is_employment,
            row_number() over (
                partition by student, pursuing_degree_level
                order by start_date asc, actual_end_date asc
            ) as rn_degree_asc,
            row_number() over (
                partition by student, is_ecc_degree_type, is_ecc_dated
                order by start_date asc, actual_end_date asc
            ) as rn_ecc_asc,
            row_number() over (
                partition by student, pursuing_degree_level
                order by is_graduated desc, start_date desc, actual_end_date desc
            ) as rn_degree_desc,
            row_number() over (
                partition by student, is_employment
                order by start_date desc, actual_end_date desc
            ) as rn_current,
        from enrollment_union
    ),

    enrollment_grouped as (
        select
            student,
            max(
                if(
                    pursuing_degree_level = 'BA' and rn_degree_desc = 1,
                    enrollment_id,
                    null
                )
            ) as ba_enrollment_id,
            max(
                if(
                    pursuing_degree_level = 'AA' and rn_degree_desc = 1,
                    enrollment_id,
                    null
                )
            ) as aa_enrollment_id,
            max(
                if(
                    pursuing_degree_level = 'Vocational' and rn_degree_desc = 1,
                    enrollment_id,
                    null
                )
            ) as vocational_enrollment_id,
            max(
                if(
                    pursuing_degree_level = 'Secondary' and rn_degree_desc = 1,
                    enrollment_id,
                    null
                )
            ) as secondary_enrollment_id,
            max(
                if(
                    pursuing_degree_level = 'Graduate' and rn_degree_desc = 1,
                    enrollment_id,
                    null
                )
            ) as graduate_enrollment_id,
            max(
                if(
                    pursuing_degree_level = 'Employment' and rn_degree_desc = 1,
                    enrollment_id,
                    null
                )
            ) as employment_enrollment_id,
            max(
                if(
                    is_ecc_degree_type = 1 and is_ecc_dated = 1 and rn_ecc_asc = 1,
                    enrollment_id,
                    null
                )
            ) as ecc_enrollment_id,
            max(
                if(rn_current = 1 and is_employment = 0, enrollment_id, null)
            ) as curr_enrollment_id,
        from enrollment_ordered
        group by student
    ),

    enrollment_wide as (
        select
            e.student,
            e.ba_enrollment_id,
            e.aa_enrollment_id,
            e.ecc_enrollment_id,
            e.secondary_enrollment_id as hs_enrollment_id,
            e.vocational_enrollment_id as cte_enrollment_id,
            e.graduate_enrollment_id,

            ba.name as ba_school_name,
            ba.pursuing_degree_type as ba_pursuing_degree_type,
            ba.status as ba_status,
            ba.start_date as ba_start_date,
            ba.actual_end_date as ba_actual_end_date,
            ba.anticipated_graduation as ba_anticipated_graduation,
            ba.account_type as ba_account_type,
            ba.major as ba_major,
            ba.major_area as ba_major_area,
            ba.college_major_declared as ba_college_major_declared,
            ba.date_last_verified as ba_date_last_verified,
            ba.of_credits_required_for_graduation as ba_credits_required_for_graduation,

            baa.name as ba_account_name,
            baa.billing_state as ba_billing_state,
            baa.nces_id as ba_nces_id,

            aa.name as aa_school_name,
            aa.pursuing_degree_type as aa_pursuing_degree_type,
            aa.status as aa_status,
            aa.start_date as aa_start_date,
            aa.actual_end_date as aa_actual_end_date,
            aa.anticipated_graduation as aa_anticipated_graduation,
            aa.account_type as aa_account_type,
            aa.major as aa_major,
            aa.major_area as aa_major_area,
            aa.college_major_declared as aa_college_major_declared,
            aa.date_last_verified as aa_date_last_verified,
            aa.of_credits_required_for_graduation as aa_credits_required_for_graduation,

            aaa.name as aa_account_name,
            aaa.billing_state as aa_billing_state,
            aaa.nces_id as aa_nces_id,

            ecc.name as ecc_school_name,
            ecc.pursuing_degree_type as ecc_pursuing_degree_type,
            ecc.status as ecc_status,
            ecc.start_date as ecc_start_date,
            ecc.actual_end_date as ecc_actual_end_date,
            ecc.anticipated_graduation as ecc_anticipated_graduation,
            ecc.account_type as ecc_account_type,
            ecc.of_credits_required_for_graduation
            as ecc_credits_required_for_graduation,
            ecc.date_last_verified as ecc_date_last_verified,

            ecca.name as ecc_account_name,
            ecca.adjusted_6_year_minority_graduation_rate
            as ecc_adjusted_6_year_minority_graduation_rate,

            hs.name as hs_school_name,
            hs.pursuing_degree_type as hs_pursuing_degree_type,
            hs.status as hs_status,
            hs.start_date as hs_start_date,
            hs.actual_end_date as hs_actual_end_date,
            hs.anticipated_graduation as hs_anticipated_graduation,
            hs.account_type as hs_account_type,
            hs.of_credits_required_for_graduation as hs_credits_required_for_graduation,

            hsa.name as hs_account_name,

            cte.pursuing_degree_type as cte_pursuing_degree_type,
            cte.status as cte_status,
            cte.start_date as cte_start_date,
            cte.actual_end_date as cte_actual_end_date,
            cte.anticipated_graduation as cte_anticipated_graduation,
            cte.account_type as cte_account_type,
            cte.of_credits_required_for_graduation
            as cte_credits_required_for_graduation,
            cte.date_last_verified as cte_date_last_verified,

            ctea.name as cte_school_name,
            ctea.billing_state as cte_billing_state,
            ctea.nces_id as cte_nces_id,

            cur.pursuing_degree_type as cur_pursuing_degree_type,
            cur.status as cur_status,
            cur.start_date as cur_start_date,
            cur.actual_end_date as cur_actual_end_date,
            cur.anticipated_graduation as cur_anticipated_graduation,
            cur.account_type as cur_account_type,
            cur.of_credits_required_for_graduation
            as cur_credits_required_for_graduation,
            cur.date_last_verified as cur_date_last_verified,

            cura.name as cur_school_name,
            cura.billing_state as cur_billing_state,
            cura.nces_id as cur_nces_id,
            cura.adjusted_6_year_minority_graduation_rate
            as cur_adjusted_6_year_minority_graduation_rate,

            emp.status as emp_status,
            emp.category as emp_category,
            emp.last_verified_date as emp_date_last_verified,

            empa.billing_state as emp_billing_state,
            empa.nces_id as emp_nces_id,

            case
                when ba.start_date > aa.start_date
                then e.ba_enrollment_id
                when aa.start_date is null
                then e.ba_enrollment_id
                else e.aa_enrollment_id
            end as ugrad_enrollment_id,

            coalesce(
                emp.start_date, emp.enlist_date, emp.bmt_start_date, emp.meps_start_date
            ) as emp_start_date,
            coalesce(
                emp.end_date, emp.discharge_date, emp.bmt_end_date, emp.meps_end_date
            ) as emp_actual_end_date,
            coalesce(emp.employer, empa.name, emp.name) as emp_name,
        from enrollment_grouped as e
        left join
            {{ ref("stg_kippadb__enrollment") }} as ba on e.ba_enrollment_id = ba.id
        left join {{ ref("stg_kippadb__account") }} as baa on ba.school = baa.id
        left join
            {{ ref("stg_kippadb__enrollment") }} as aa on e.aa_enrollment_id = aa.id
        left join {{ ref("stg_kippadb__account") }} as aaa on aa.school = aaa.id
        left join
            {{ ref("stg_kippadb__enrollment") }} as ecc on e.ecc_enrollment_id = ecc.id
        left join {{ ref("stg_kippadb__account") }} as ecca on ecc.school = ecca.id
        left join
            {{ ref("stg_kippadb__enrollment") }} as hs
            on e.secondary_enrollment_id = hs.id
        left join {{ ref("stg_kippadb__account") }} as hsa on hs.school = hsa.id
        left join
            {{ ref("stg_kippadb__enrollment") }} as cte
            on e.vocational_enrollment_id = cte.id
        left join {{ ref("stg_kippadb__account") }} as ctea on cte.school = ctea.id
        left join
            {{ ref("stg_kippadb__enrollment") }} as cur on e.curr_enrollment_id = cur.id
        left join {{ ref("stg_kippadb__account") }} as cura on cur.school = cura.id
        left join
            {{ ref("stg_kippadb__employment") }} as emp
            on e.employment_enrollment_id = emp.id
        left join
            {{ ref("stg_kippadb__account") }} as empa
            on emp.employer_organization_look_up = empa.id
    )

select
    ew.student,
    ew.ba_enrollment_id,
    ew.aa_enrollment_id,
    ew.ecc_enrollment_id,
    ew.hs_enrollment_id,
    ew.cte_enrollment_id,
    ew.graduate_enrollment_id,
    ew.ugrad_enrollment_id,
    ew.ba_school_name,
    ew.ba_pursuing_degree_type,
    ew.ba_status,
    ew.ba_start_date,
    ew.ba_actual_end_date,
    ew.ba_anticipated_graduation,
    ew.ba_account_type,
    ew.ba_major,
    ew.ba_major_area,
    ew.ba_college_major_declared,
    ew.ba_date_last_verified,
    ew.ba_credits_required_for_graduation,
    ew.ba_account_name,
    ew.ba_billing_state,
    ew.ba_nces_id,
    ew.aa_school_name,
    ew.aa_pursuing_degree_type,
    ew.aa_status,
    ew.aa_start_date,
    ew.aa_actual_end_date,
    ew.aa_anticipated_graduation,
    ew.aa_account_type,
    ew.aa_major,
    ew.aa_major_area,
    ew.aa_college_major_declared,
    ew.aa_date_last_verified,
    ew.aa_credits_required_for_graduation,
    ew.aa_account_name,
    ew.aa_billing_state,
    ew.aa_nces_id,
    ew.ecc_school_name,
    ew.ecc_pursuing_degree_type,
    ew.ecc_status,
    ew.ecc_start_date,
    ew.ecc_actual_end_date,
    ew.ecc_anticipated_graduation,
    ew.ecc_account_type,
    ew.ecc_credits_required_for_graduation,
    ew.ecc_account_name,
    ew.ecc_adjusted_6_year_minority_graduation_rate,
    ew.ecc_date_last_verified,
    ew.hs_school_name,
    ew.hs_pursuing_degree_type,
    ew.hs_status,
    ew.hs_start_date,
    ew.hs_actual_end_date,
    ew.hs_anticipated_graduation,
    ew.hs_account_type,
    ew.hs_credits_required_for_graduation,
    ew.hs_account_name,
    ew.cte_pursuing_degree_type,
    ew.cte_status,
    ew.cte_start_date,
    ew.cte_actual_end_date,
    ew.cte_anticipated_graduation,
    ew.cte_account_type,
    ew.cte_credits_required_for_graduation,
    ew.cte_school_name,
    ew.cte_billing_state,
    ew.cte_nces_id,
    ew.cte_date_last_verified,
    ew.cur_pursuing_degree_type,
    ew.cur_status,
    ew.cur_start_date,
    ew.cur_actual_end_date,
    ew.cur_anticipated_graduation,
    ew.cur_account_type,
    ew.cur_credits_required_for_graduation,
    ew.cur_school_name,
    ew.cur_billing_state,
    ew.cur_nces_id,
    ew.cur_adjusted_6_year_minority_graduation_rate,
    ew.cur_date_last_verified,
    ew.emp_status,
    ew.emp_category,
    ew.emp_date_last_verified,
    ew.emp_start_date,
    ew.emp_actual_end_date,
    ew.emp_billing_state,
    ew.emp_nces_id,
    ew.emp_name,

    ug.name as ugrad_school_name,
    ug.pursuing_degree_type as ugrad_pursuing_degree_type,
    ug.status as ugrad_status,
    ug.start_date as ugrad_start_date,
    ug.actual_end_date as ugrad_actual_end_date,
    ug.anticipated_graduation as ugrad_anticipated_graduation,
    ug.account_type as ugrad_account_type,
    ug.major as ugrad_major,
    ug.major_area as ugrad_major_area,
    ug.college_major_declared as ugrad_college_major_declared,
    ug.date_last_verified as ugrad_date_last_verified,
    ug.of_credits_required_for_graduation as ugrad_credits_required_for_graduation,

    uga.name as ugrad_account_name,
    uga.billing_state as ugrad_billing_state,
    uga.nces_id as ugrad_nces_id,
    uga.adjusted_6_year_minority_graduation_rate
    as ugrad_adjusted_6_year_minority_graduation_rate,
    uga.act_composite_25_75 as ugrad_act_composite_25_75,
    uga.competitiveness_ranking as ugrad_competitiveness_ranking,
from enrollment_wide as ew
left join {{ ref("stg_kippadb__enrollment") }} as ug on ew.ugrad_enrollment_id = ug.id
left join {{ ref("stg_kippadb__account") }} as uga on ug.school = uga.id
