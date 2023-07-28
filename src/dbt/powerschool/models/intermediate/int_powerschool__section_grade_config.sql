with
    sec_gfs as (
        select
            sec.sections_dcid,
            sec.sections_schoolid,
            sec.sections_termid,

            coalesce(
                gsec.gradeformulasetid, gsfa.gradeformulasetid, 0
            ) as grade_formula_set_id,
        from {{ ref("base_powerschool__sections") }} as sec
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sec.sections_schoolid = sch.school_number
        left join
            {{ ref("stg_powerschool__gradesectionconfig") }} as gsec
            on sec.sections_dcid = gsec.sectionsdcid
            and gsec.type = 'Admin'
        left join
            {{ ref("stg_powerschool__gradeschoolconfig") }} as gsch
            on sch.dcid = gsch.schoolsdcid
            and sec.terms_yearid = gsch.yearid
        left join
            {{ ref("stg_powerschool__gradeschoolformulaassoc") }} as gsfa
            on gsch.gradeschoolconfigid = gsfa.gradeschoolconfigid
            and gsfa.isdefaultformulaset = 1
        where
            {# PTP #}
            sec.sections_gradebooktype = 2
    )

select
    sgfs.sections_dcid,
    sgfs.grade_formula_set_id,

    t.abbreviation as term_abbreviation,

    tb.storecode,
    tb.date1 as term_start_date,
    tb.date2 as term_end_date,

    gfs.name as grade_formula_set_name,

    gcfw.weight as grade_calc_formula_weight,
    gcfw.teachercategoryid as teacher_category_id,
    gcfw.districtteachercategoryid as district_teacher_category_id,

    coalesce(
        gct.gradecalculationtypeid, gcfw.gradecalcformulaweightid, -1
    ) as grading_formula_id,
    coalesce(gct.type, gcfw.type) as grading_formula_weighting_type,

    coalesce(
        gcfw.teachercategoryid,
        gcfw.districtteachercategoryid,
        gct.gradecalculationtypeid,
        -1
    ) as category_id,
    coalesce(tc.name, dtc.name, gct.type) as category_name,
    coalesce(tc.defaultscoretype, dtc.defaultscoretype) as default_score_type,
    coalesce(tc.isinfinalgrades, dtc.isinfinalgrades, 0) as is_in_final_grades,
from sec_gfs as sgfs
inner join
    {{ ref("stg_powerschool__terms") }} as t
    on sgfs.sections_termid = t.id
    and sgfs.sections_schoolid = t.schoolid
inner join
    {{ ref("stg_powerschool__termbins") }} as tb
    on t.schoolid = tb.schoolid
    and t.id = tb.termid
left join
    {{ ref("stg_powerschool__gradeformulaset") }} as gfs
    on sgfs.grade_formula_set_id = gfs.gradeformulasetid
left join
    {{ ref("stg_powerschool__gradecalculationtype") }} as gct
    on sgfs.grade_formula_set_id = gct.gradeformulasetid
    and t.abbreviation = gct.abbreviation
    and tb.storecode = gct.storecode
left join
    {{ ref("stg_powerschool__gradecalcformulaweight") }} as gcfw
    on gct.gradecalculationtypeid = gcfw.gradecalculationtypeid
left join
    {{ ref("stg_powerschool__teachercategory") }} as tc
    on gcfw.teachercategoryid = tc.teachercategoryid
left join
    {{ ref("stg_powerschool__districtteachercategory") }} as dtc
    on gcfw.districtteachercategoryid = dtc.districtteachercategoryid
