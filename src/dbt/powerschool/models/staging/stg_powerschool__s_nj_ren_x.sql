with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__s_nj_ren_x"),
                partition_by="reenrollmentsdcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        reenrollmentsdcid,
        lep_tf,
        pid_504_tf,
        cumulativedaysabsent,
        cumulativedayspresent,
        cumulativestateabs,
        daysopen,
        deviceowner,
        devicetype,
        homelessprimarynighttimeres,
        internetconnectivity,
        remotedaysabsent,
        remotedayspresent,
        learningenvironment,
        retained_tf,
        languageacquisition,
        lep_completion_date_refused,
        sid_excludeenrollment
    ),

    /* column transformations */
    reenrollmentsdcid.int_value as reenrollmentsdcid,
    lep_tf.int_value as lep_tf,
    pid_504_tf.int_value as pid_504_tf,
    cumulativedaysabsent.int_value as cumulativedaysabsent,
    cumulativedayspresent.int_value as cumulativedayspresent,
    cumulativestateabs.int_value as cumulativestateabs,
    daysopen.int_value as daysopen,
    deviceowner.int_value as deviceowner,
    devicetype.int_value as devicetype,
    homelessprimarynighttimeres.int_value as homelessprimarynighttimeres,
    internetconnectivity.int_value as internetconnectivity,
    remotedaysabsent.int_value as remotedaysabsent,
    remotedayspresent.int_value as remotedayspresent,
    learningenvironment.int_value as learningenvironment,
    retained_tf.int_value as retained_tf,
    languageacquisition.int_value as languageacquisition,
    lep_completion_date_refused.int_value as lep_completion_date_refused,
    sid_excludeenrollment.int_value as sid_excludeenrollment,
from deduplicate
