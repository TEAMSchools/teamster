with
    discipline_rollup as (
        select
            dli.student_school_id as student_number,
            dli.create_ts_academic_year as academic_year,

            case
                when
                    count(
                        distinct case
                            when cf.restraint_used = 'Y' then dli.incident_id else null
                        end
                    )
                    > 0
                then 1
                else 0
            end as is_restraint_int,

            count(
                distinct case
                    when cf.restraint_used = 'Y' then dli.incident_id else null
                end
            ) as n_restraint_incidents,

            case
                when
                    count(
                        distinct case
                            when dlp.penalty_name like '%Out-of-School Suspension'
                            then dlp.incident_penalty_id
                        end
                    )
                    = 1
                then 1
                else 0
            end as is_oss_one_int,

            case
                when
                    count(
                        distinct case
                            when dlp.penalty_name like '%Out-of-School Suspension'
                            then dlp.incident_penalty_id
                        end
                    )
                    > 1
                then 1
                else 0
            end as is_oss_two_plus_int,

            max(
                case
                    when dlp.penalty_name like '%In-School Suspension' then 1 else 0
                end
            ) as is_iss_int,

            sum(
                case
                    when dlp.penalty_name like '%Out-of-School Suspension'
                    then dlp.num_days
                    else null
                end
            ) as oss_days_missed,

            count(
                distinct case
                    when dlp.penalty_name like '%Out-of-School Suspension'
                    then dlp.incident_penalty_id
                end
            ) as oss_incident_count,

        from {{ ref("stg_deanslist__incidents") }} as dli
        left join
            {{ ref("stg_deanslist__incidents__penalties") }} as dlp
            on dli.incident_id = dlp.incident_id
            and {{ union_dataset_join_clause(left_alias="dli", right_alias="dlp") }}
        left join
            {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cf
            on dli.incident_id = cf.incident_id
            and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
        where dli.is_active
        group by dli.student_school_id, dli.create_ts_academic_year
    ),

    algebra_pass as (
        select
            sg.studentid,
            sg.academic_year,
            sg._dbt_source_relation,

            max(if sg.grade like 'F%', false, true) is_algebra1_pass,

        from {{ ref("stg_powerschool__storedgrades") }} as sg
        left join
            {{ ref("stg_powerschool__courses") }} as c
            on sg.course_number = c.course_number
            and {{ union_dataset_join_clause(left_alias="sg", right_alias="c") }}
        left join
            {{ ref("stg_powerschool__s_nj_crs_x") }} as nj
            on c.dcid = nj.coursesdcid
            and {{ union_dataset_join_clause(left_alias="c", right_alias="nj") }}
        where
            nj.nces_subject_area in ('02', '52')
            and nj.nces_course_id = '052'
            and sg.storecode = 'Y1'
        group by sg.studentid, sg.academic_year, sg._dbt_source_relation
    )

select *
from algebra_pass
