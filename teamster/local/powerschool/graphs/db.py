from dagster import graph

from teamster.core.powerschool.graphs.db import sync_table


@graph
def sync_extensions():
    u_clg_et_stu = sync_table.alias("u_clg_et_stu")
    u_clg_et_stu()

    u_clg_et_stu_alt = sync_table.alias("u_clg_et_stu_alt")
    u_clg_et_stu_alt()

    u_def_ext_students = sync_table.alias("u_def_ext_students")
    u_def_ext_students()

    u_studentsuserfields = sync_table.alias("u_studentsuserfields")
    u_studentsuserfields()
