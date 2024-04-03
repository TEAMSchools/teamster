with
    school_config as (
        select gsch.schoolsdcid, gsch.yearid, gsfa.gradeformulasetid,
        from {{ ref("stg_powerschool__gradeschoolconfig") }} as gsch
        inner join
            {{ ref("stg_powerschool__gradeschoolformulaassoc") }} as gsfa
            on gsch.gradeschoolconfigid = gsfa.gradeschoolconfigid
            and gsfa.isdefaultformulaset = 1
    ),

    grade_calc as (
        select
            gct.gradecalculationtypeid,
            gct.gradeformulasetid,
            gct.yearid,
            gct.abbreviation,
            gct.storecode,
            gct.type,

            gcsa.schoolsdcid,
        from {{ ref("stg_powerschool__gradecalculationtype") }} as gct
        inner join
            {{ ref("stg_powerschool__gradecalcschoolassoc") }} as gcsa
            on gct.gradecalculationtypeid = gcsa.gradecalculationtypeid
    ),

    category_weight as (
        select
            gcfw.gradecalcformulaweightid,
            gcfw.gradecalculationtypeid,
            gcfw.teachercategoryid,
            gcfw.districtteachercategoryid,
            gcfw.weight,
            gcfw.type,

            coalesce(tc.name, dtc.name) as `name`,
            coalesce(tc.defaultscoretype, dtc.defaultscoretype) as defaultscoretype,
            coalesce(tc.isinfinalgrades, dtc.isinfinalgrades) as isinfinalgrades,
        from {{ ref("stg_powerschool__gradecalcformulaweight") }} as gcfw
        left join
            {{ ref("stg_powerschool__teachercategory") }} as tc
            on gcfw.teachercategoryid = tc.teachercategoryid
        left join
            {{ ref("stg_powerschool__districtteachercategory") }} as dtc
            on gcfw.districtteachercategoryid = dtc.districtteachercategoryid
    ),

    sec as (
        select
            sec.sections_dcid,
            sec.sections_schoolid,
            sec.sections_termid,

            sch.dcid as schools_dcid,

            t.yearid,
            t.abbreviation as term_abbreviation,

            coalesce(
                gsec.gradeformulasetid, gsfa.gradeformulasetid, 0
            ) as grade_formula_set_id,
        from {{ ref("base_powerschool__sections") }} as sec
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sec.sections_schoolid = sch.school_number
        inner join
            {{ ref("stg_powerschool__terms") }} as t
            on sec.sections_termid = t.id
            and sec.sections_schoolid = t.schoolid
        left join
            {{ ref("stg_powerschool__gradesectionconfig") }} as gsec
            on sec.sections_dcid = gsec.sectionsdcid
            and gsec.type = 'Admin'
        left join
            school_config as gsfa
            on sch.dcid = gsfa.schoolsdcid
            and t.yearid = gsfa.yearid
        where
            /* PTP */
            sec.sections_gradebooktype = 2
    )

select
    sec.sections_dcid,
    sec.grade_formula_set_id,
    sec.term_abbreviation,

    tb.storecode,
    tb.date1 as term_start_date,
    tb.date2 as term_end_date,

    gfs.name as grade_formula_set_name,

    gcfw.weight as grade_calc_formula_weight,
    gcfw.teachercategoryid as teacher_category_id,
    gcfw.districtteachercategoryid as district_teacher_category_id,
    gcfw.defaultscoretype as default_score_type,

    coalesce(gcfw.isinfinalgrades, 0) as is_in_final_grades,

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
    coalesce(gcfw.name, gct.type) as category_name,
from sec
inner join
    {{ ref("stg_powerschool__termbins") }} as tb
    on sec.sections_schoolid = tb.schoolid
    and sec.sections_termid = tb.termid
left join
    {{ ref("stg_powerschool__gradeformulaset") }} as gfs
    on sec.grade_formula_set_id = gfs.gradeformulasetid
left join
    grade_calc as gct
    on sec.schools_dcid = gct.schoolsdcid
    and sec.yearid = gct.yearid
    and sec.term_abbreviation = gct.abbreviation
    and sec.grade_formula_set_id = gct.gradeformulasetid
    and tb.storecode = gct.storecode
left join
    category_weight as gcfw on gct.gradecalculationtypeid = gcfw.gradecalculationtypeid
