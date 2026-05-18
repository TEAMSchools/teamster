with
    paterson_id_map as (
        select
            scf.prevstudentid as paterson_district_sis_id,
            s.student_number as kipp_student_number,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on s.dcid = scf.studentsdcid
        where s.enroll_status in (0, 2, 3) and scf.prevstudentid is not null
    )

select
    raw.* replace (
        coalesce(
            m.kipp_student_number, raw.localstudentidentifier
        ) as localstudentidentifier
    ),
from {{ ref("stg_pearson__njsla") }} as raw
left join
    paterson_id_map as m on raw.localstudentidentifier = m.paterson_district_sis_id
