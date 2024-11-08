with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__users"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        dcid,
        homeschoolid,
        photo,
        numlogins,
        allowloginstart,
        allowloginend,
        psaccess,
        groupvalue,
        lunch_id,
        supportcontact,
        wm_tier,
        wm_createtime,
        wm_exclude,
        adminldapenabled,
        teacherldapenabled,
        maximum_load,
        gradebooktype,
        fedethnicity,
        fedracedecline,
        ptaccess,
        whomodifiedid
    ),

    /* column transformations */
    dcid.int_value as dcid,
    homeschoolid.int_value as homeschoolid,
    photo.int_value as photo,
    numlogins.int_value as numlogins,
    allowloginstart.int_value as allowloginstart,
    allowloginend.int_value as allowloginend,
    psaccess.int_value as psaccess,
    groupvalue.int_value as groupvalue,
    lunch_id.double_value as lunch_id,
    supportcontact.int_value as supportcontact,
    wm_tier.int_value as wm_tier,
    wm_createtime.int_value as wm_createtime,
    wm_exclude.int_value as wm_exclude,
    adminldapenabled.int_value as adminldapenabled,
    teacherldapenabled.int_value as teacherldapenabled,
    maximum_load.int_value as maximum_load,
    gradebooktype.int_value as gradebooktype,
    fedethnicity.int_value as fedethnicity,
    fedracedecline.int_value as fedracedecline,
    ptaccess.int_value as ptaccess,
    whomodifiedid.int_value as whomodifiedid,
from deduplicate
