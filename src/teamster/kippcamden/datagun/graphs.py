from dagster import graph

from teamster.core.datagun.graphs import etl_sftp


@graph
def powerschool_autocomm():
    students_accessaccounts = etl_sftp.alias("students_accessaccounts")
    students_accessaccounts()

    students_easyiep = etl_sftp.alias("students_easyiep")
    students_easyiep()

    teachers_accounts = etl_sftp.alias("teachers_accounts")
    teachers_accounts()


@graph
def cpn():
    attendance = etl_sftp.alias("attendance")
    attendance()

    demographic = etl_sftp.alias("demographic")
    demographic()
