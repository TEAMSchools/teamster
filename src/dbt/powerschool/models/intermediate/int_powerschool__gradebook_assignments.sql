with
    assignment_category as (
        select
            asec.assignmentsectionid,
            asec.sectionsdcid,
            asec.assignmentid,
            asec.name,
            asec.duedate,
            asec.scoretype,
            asec.totalpointvalue,
            asec.extracreditpoints,
            asec.weight,
            asec.iscountedinfinalgrade,

            coalesce(tc.districtteachercategoryid, tc.teachercategoryid) as category_id,

            coalesce(dtc.name, tc.name) as category_name,
        from {{ ref("stg_powerschool__assignmentsection") }} as asec
        left join
            {{ ref("stg_powerschool__assignmentcategoryassoc") }} as aca
            on asec.assignmentsectionid = aca.assignmentsectionid
        left join
            {{ ref("stg_powerschool__teachercategory") }} as tc
            on aca.teachercategoryid = tc.teachercategoryid
        left join
            {{ ref("stg_powerschool__districtteachercategory") }} as dtc
            on tc.districtteachercategoryid = dtc.districtteachercategoryid
    )

select *, upper(left(category_name, 1)) as category_code,
from assignment_category
