import argparse
from copy import deepcopy
from io import BytesIO

import dagster as dg
from dagster_shared import check
from fastavro import parse_schema, reader, writer
from fastavro.types import Schema
from google.cloud import storage

from teamster.core.resources import GCS_RESOURCE


def rewrite_blob(
    blob: storage.Blob, asset_name: str, bucket: storage.Bucket, schema: Schema
):
    # split blob name
    blob_name_split = check.inst(obj=blob.name, ttype=str).split("/")

    # find index of blob name that matches asset name
    asset_name_index = blob_name_split.index(asset_name)

    # create copies
    blob_name_split_new = deepcopy(blob_name_split)
    blob_name_split_archive = deepcopy(blob_name_split)

    # rename index value
    blob_name_split_new[asset_name_index] = f"{asset_name}_new"
    blob_name_split_archive[asset_name_index] = f"{asset_name}_archive"

    # create new blobs
    new_blob = bucket.blob(blob_name="/".join(blob_name_split_new))
    archive_blob = bucket.blob(blob_name="/".join(blob_name_split_archive))

    # copy original blob to archive
    print(f"ARCHIVING: {blob.name}")
    archive_blob.rewrite(source=blob)

    print(f"READING: {blob.name}")
    records = []

    with blob.open(mode="rb") as fo_read:
        # trunk-ignore(pyright/reportArgumentType)
        for record in reader(fo=fo_read):
            records.append(
                # trunk-ignore(pyright/reportAttributeAccessIssue)
                # trunk-ignore(pyright/reportOptionalMemberAccess)
                {key: str(value) for key, value in record.items() if value is not None}
            )

    print(f"WRITING: {new_blob.name}")
    with BytesIO() as fo_write:
        writer(fo=fo_write, schema=schema, records=records, codec="snappy")
        fo_write.seek(0)
        new_blob.upload_from_file(file_obj=fo_write)


def rewrite_blobs(asset_key: list[str], schema: Schema):
    with dg.build_resources(resources={"gcs": GCS_RESOURCE}) as resources:
        gcs: storage.Client = resources.gcs

    bucket = gcs.get_bucket(bucket_or_name=f"teamster-{asset_key[0]}")

    for blob in bucket.list_blobs(match_glob=f"dagster/{'/'.join(asset_key)}/**/data"):
        rewrite_blob(blob=blob, asset_name=asset_key[-1], bucket=bucket, schema=schema)


# def kipptaf_grow_assignments():
#     from teamster.code_locations.kipptaf.level_data.grow.schema import ASSIGNMENT_SCHEMA

#     rewrite_blobs(
#         asset_key=["kipptaf", "schoolmint", "grow", "assignments"],
#         schema=parse_schema(ASSIGNMENT_SCHEMA),
#     )


# def kippcamden_deanslist_incidents():
#     from teamster.code_locations.kippcamden.deanslist.schema import INCIDENTS_SCHEMA

#     rewrite_blobs(
#         asset_key=["kippcamden", "deanslist", "incidents"],
#         schema=parse_schema(INCIDENTS_SCHEMA),
#     )


# def kippmiami_deanslist_incidents():
#     from teamster.code_locations.kippmiami.deanslist.schema import INCIDENTS_SCHEMA

#     rewrite_blobs(
#         asset_key=["kippmiami", "deanslist", "incidents"],
#         schema=parse_schema(INCIDENTS_SCHEMA),
#     )


# def kippnewark_deanslist_incidents():
#     from teamster.code_locations.kippnewark.deanslist.schema import INCIDENTS_SCHEMA

#     rewrite_blobs(
#         asset_key=["kippnewark", "deanslist", "incidents"],
#         schema=parse_schema(INCIDENTS_SCHEMA),
#     )


def kippmiami_fldoe_eoc():
    from teamster.code_locations.kippmiami.fldoe.schema import EOC_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "fldoe", "eoc"], schema=parse_schema(EOC_SCHEMA)
    )


def kippmiami_fldoe_fast():
    from teamster.code_locations.kippmiami.fldoe.schema import FAST_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "fldoe", "fast"], schema=parse_schema(FAST_SCHEMA)
    )


def kippmiami_fldoe_fsa():
    from teamster.code_locations.kippmiami.fldoe.schema import FSA_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "fldoe", "fsa"], schema=parse_schema(FSA_SCHEMA)
    )


def kippmiami_fldoe_fte():
    from teamster.code_locations.kippmiami.fldoe.schema import FTE_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "fldoe", "fte"], schema=parse_schema(FTE_SCHEMA)
    )


def kippmiami_fldoe_science():
    from teamster.code_locations.kippmiami.fldoe.schema import SCIENCE_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "fldoe", "science"], schema=parse_schema(SCIENCE_SCHEMA)
    )


def kippnewark_edplan_njsmart_powerschool():
    from teamster.code_locations.kippnewark.edplan.schema import (
        NJSMART_POWERSCHOOL_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippnewark", "edplan", "njsmart_powerschool"],
        schema=parse_schema(NJSMART_POWERSCHOOL_SCHEMA),
    )


def kippnewark_pearson_njgpa():
    from teamster.code_locations.kippnewark.pearson.schema import NJGPA_SCHEMA

    rewrite_blobs(
        asset_key=["kippnewark", "pearson", "njgpa"], schema=parse_schema(NJGPA_SCHEMA)
    )


def kippnewark_pearson_njsla():
    from teamster.code_locations.kippnewark.pearson.schema import NJSLA_SCHEMA

    rewrite_blobs(
        asset_key=["kippnewark", "pearson", "njsla"], schema=parse_schema(NJSLA_SCHEMA)
    )


def kippnewark_pearson_njsla_science():
    from teamster.code_locations.kippnewark.pearson.schema import NJSLA_SCHEMA

    rewrite_blobs(
        asset_key=["kippnewark", "pearson", "njsla_science"],
        schema=parse_schema(NJSLA_SCHEMA),
    )


def kippnewark_pearson_parcc():
    from teamster.code_locations.kippnewark.pearson.schema import PARCC_SCHEMA

    rewrite_blobs(
        asset_key=["kippnewark", "pearson", "parcc"], schema=parse_schema(PARCC_SCHEMA)
    )


def kippnewark_pearson_student_list_report():
    from teamster.code_locations.kippnewark.pearson.schema import (
        STUDENT_LIST_REPORT_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippnewark", "pearson", "student_list_report"],
        schema=parse_schema(STUDENT_LIST_REPORT_SCHEMA),
    )


def kippnewark_pearson_student_test_update():
    from teamster.code_locations.kippnewark.pearson.schema import (
        STUDENT_TEST_UPDATE_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippnewark", "pearson", "student_test_update"],
        schema=parse_schema(STUDENT_TEST_UPDATE_SCHEMA),
    )


def kippnewark_titan_person_data():
    from teamster.code_locations.kippnewark.titan.schema import PERSON_DATA_SCHEMA

    rewrite_blobs(
        asset_key=["kippnewark", "titan", "person_data"],
        schema=parse_schema(PERSON_DATA_SCHEMA),
    )


def kippcamden_edplan_njsmart_powerschool():
    from teamster.code_locations.kippcamden.edplan.schema import (
        NJSMART_POWERSCHOOL_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippcamden", "edplan", "njsmart_powerschool"],
        schema=parse_schema(NJSMART_POWERSCHOOL_SCHEMA),
    )


def kippcamden_pearson_njgpa():
    from teamster.code_locations.kippcamden.pearson.schema import NJGPA_SCHEMA

    rewrite_blobs(
        asset_key=["kippcamden", "pearson", "njgpa"], schema=parse_schema(NJGPA_SCHEMA)
    )


def kippcamden_pearson_njsla():
    from teamster.code_locations.kippcamden.pearson.schema import NJSLA_SCHEMA

    rewrite_blobs(
        asset_key=["kippcamden", "pearson", "njsla"], schema=parse_schema(NJSLA_SCHEMA)
    )


def kippcamden_pearson_njsla_science():
    from teamster.code_locations.kippcamden.pearson.schema import NJSLA_SCHEMA

    rewrite_blobs(
        asset_key=["kippcamden", "pearson", "njsla_science"],
        schema=parse_schema(NJSLA_SCHEMA),
    )


def kippcamden_pearson_parcc():
    from teamster.code_locations.kippcamden.pearson.schema import PARCC_SCHEMA

    rewrite_blobs(
        asset_key=["kippcamden", "pearson", "parcc"], schema=parse_schema(PARCC_SCHEMA)
    )


def kippcamden_pearson_student_list_report():
    from teamster.code_locations.kippcamden.pearson.schema import (
        STUDENT_LIST_REPORT_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippcamden", "pearson", "student_list_report"],
        schema=parse_schema(STUDENT_LIST_REPORT_SCHEMA),
    )


def kippcamden_pearson_student_test_update():
    from teamster.code_locations.kippcamden.pearson.schema import (
        STUDENT_TEST_UPDATE_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippcamden", "pearson", "student_test_update"],
        schema=parse_schema(STUDENT_TEST_UPDATE_SCHEMA),
    )


def kippcamden_titan_person_data():
    from teamster.code_locations.kippcamden.titan.schema import PERSON_DATA_SCHEMA

    rewrite_blobs(
        asset_key=["kippcamden", "titan", "person_data"],
        schema=parse_schema(PERSON_DATA_SCHEMA),
    )


def kippnewark_iready_diagnostic_results():
    from teamster.code_locations.kippnewark.iready.schema import (
        DIAGNOSTIC_RESULTS_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippnewark", "iready", "diagnostic_results"],
        schema=parse_schema(DIAGNOSTIC_RESULTS_SCHEMA),
    )


def kippnewark_iready_instruction_by_lesson():
    from teamster.code_locations.kippnewark.iready.schema import (
        PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippnewark", "iready", "instruction_by_lesson"],
        schema=parse_schema(PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA),
    )


def kippnewark_iready_instruction_by_lesson_pro():
    from teamster.code_locations.kippnewark.iready.schema import (
        INSTRUCTION_BY_LESSON_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippnewark", "iready", "instruction_by_lesson_pro"],
        schema=parse_schema(INSTRUCTION_BY_LESSON_SCHEMA),
    )


def kippnewark_iready_instructional_usage_data():
    from teamster.code_locations.kippnewark.iready.schema import (
        INSTRUCTIONAL_USAGE_DATA_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippnewark", "iready", "instructional_usage_data"],
        schema=parse_schema(INSTRUCTIONAL_USAGE_DATA_SCHEMA),
    )


def kippmiami_iready_diagnostic_results():
    from teamster.code_locations.kippmiami.iready.schema import (
        DIAGNOSTIC_RESULTS_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippmiami", "iready", "diagnostic_results"],
        schema=parse_schema(DIAGNOSTIC_RESULTS_SCHEMA),
    )


def kippmiami_iready_instruction_by_lesson():
    from teamster.code_locations.kippmiami.iready.schema import (
        PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippmiami", "iready", "instruction_by_lesson"],
        schema=parse_schema(PERSONALIZED_INSTRUCTION_BY_LESSON_SCHEMA),
    )


def kippmiami_iready_instruction_by_lesson_pro():
    from teamster.code_locations.kippmiami.iready.schema import (
        INSTRUCTION_BY_LESSON_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippmiami", "iready", "instruction_by_lesson_pro"],
        schema=parse_schema(INSTRUCTION_BY_LESSON_SCHEMA),
    )


def kippmiami_iready_instructional_usage_data():
    from teamster.code_locations.kippmiami.iready.schema import (
        INSTRUCTIONAL_USAGE_DATA_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippmiami", "iready", "instructional_usage_data"],
        schema=parse_schema(INSTRUCTIONAL_USAGE_DATA_SCHEMA),
    )


# def kippnewark_renlearn_accelerated_reader():
#     from teamster.code_locations.kippnewark.renlearn.schema import (
#         ACCELERATED_READER_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=["kippnewark", "renlearn", "accelerated_reader"],
#         schema=parse_schema(ACCELERATED_READER_SCHEMA),
#     )


# def kippnewark_renlearn_star():
#     from teamster.code_locations.kippnewark.renlearn.schema import STAR_SCHEMA

#     rewrite_blobs(
#         asset_key=["kippnewark", "renlearn", "star"], schema=parse_schema(STAR_SCHEMA)
#     )


# def kippmiami_renlearn_accelerated_reader():
#     from teamster.code_locations.kippmiami.renlearn.schema import (
#         ACCELERATED_READER_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=["kippmiami", "renlearn", "accelerated_reader"],
#         schema=parse_schema(ACCELERATED_READER_SCHEMA),
#     )


# def kippmiami_renlearn_star():
#     from teamster.code_locations.kippmiami.renlearn.schema import STAR_SCHEMA

#     rewrite_blobs(
#         asset_key=["kippmiami", "renlearn", "star"], schema=parse_schema(STAR_SCHEMA)
#     )


# def kippmiami_renlearn_fast_star():
#     from teamster.code_locations.kippmiami.renlearn.schema import FAST_STAR_SCHEMA

#     rewrite_blobs(
#         asset_key=["kippmiami", "renlearn", "fast_star"],
#         schema=parse_schema(FAST_STAR_SCHEMA),
#     )


# def kippmiami_renlearn_star_dashboard_standards():
#     from teamster.code_locations.kippmiami.renlearn.schema import (
#         STAR_DASHBOARD_STANDARDS_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=["kippmiami", "renlearn", "star_dashboard_standards"],
#         schema=parse_schema(STAR_DASHBOARD_STANDARDS_SCHEMA),
#     )


# def kippmiami_renlearn_star_skill_area():
#     from teamster.code_locations.kippmiami.renlearn.schema import STAR_SKILL_AREA_SCHEMA

#     rewrite_blobs(
#         asset_key=["kippmiami", "renlearn", "star_skill_area"],
#         schema=parse_schema(STAR_SKILL_AREA_SCHEMA),
#     )


# def kipptaf_adp_payroll_general_ledger_file():
#     from teamster.code_locations.kipptaf.adp.payroll.schema import (
#         GENERAL_LEDGER_FILE_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=["kipptaf", "adp", "payroll", "general_ledger_file"],
#         schema=parse_schema(GENERAL_LEDGER_FILE_SCHEMA),
#     )


# def kipptaf_adp_workforce_now_additional_earnings_report():
#     from teamster.code_locations.kipptaf.adp.workforce_now.sftp.schema import (
#         ADDITIONAL_EARNINGS_REPORT_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=["kipptaf", "adp", "workforce_now", "additional_earnings_report"],
#         schema=parse_schema(ADDITIONAL_EARNINGS_REPORT_SCHEMA),
#     )


# def kipptaf_adp_workforce_now_pension_and_benefits_enrollments():
#     from teamster.code_locations.kipptaf.adp.workforce_now.sftp.schema import (
#         PENSION_AND_BENEFITS_ENROLLMENTS_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=[
#             "kipptaf",
#             "adp",
#             "workforce_now",
#             "pension_and_benefits_enrollments",
#         ],
#         schema=parse_schema(PENSION_AND_BENEFITS_ENROLLMENTS_SCHEMA),
#     )


# def kipptaf_adp_workforce_now_time_and_attendance():
#     from teamster.code_locations.kipptaf.adp.workforce_now.sftp.schema import (
#         TIME_AND_ATTENDANCE_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=["kipptaf", "adp", "workforce_now", "time_and_attendance"],
#         schema=parse_schema(TIME_AND_ATTENDANCE_SCHEMA),
#     )


# def kipptaf_collegeboard_ap():
#     from teamster.code_locations.kipptaf.collegeboard.schema import AP_SCHEMA

#     rewrite_blobs(
#         asset_key=["kipptaf", "collegeboard", "ap"],
#         schema=parse_schema(AP_SCHEMA),
#     )


# def kipptaf_collegeboard_psat():
#     from teamster.code_locations.kipptaf.collegeboard.schema import PSAT_SCHEMA

#     rewrite_blobs(
#         asset_key=["kipptaf", "collegeboard", "psat"],
#         schema=parse_schema(PSAT_SCHEMA),
#     )


# def kipptaf_deanslist_reconcile_attendance():
#     from teamster.code_locations.kipptaf.deanslist.schema import (
#         RECONCILE_ATTENDANCE_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=["kipptaf", "deanslist", "reconcile_attendance"],
#         schema=parse_schema(RECONCILE_ATTENDANCE_SCHEMA),
#     )


# def kipptaf_deanslist_reconcile_suspensions():
#     from teamster.code_locations.kipptaf.deanslist.schema import (
#         RECONCILE_SUSPENSIONS_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=["kipptaf", "deanslist", "reconcile_suspensions"],
#         schema=parse_schema(RECONCILE_SUSPENSIONS_SCHEMA),
#     )


# def kipptaf_tableau_view_count_per_view():
#     from teamster.code_locations.kipptaf.tableau.schema import (
#         VIEW_COUNT_PER_VIEW_SCHEMA,
#     )

#     rewrite_blobs(
#         asset_key=["kipptaf", "tableau", "view_count_per_view"],
#         schema=parse_schema(VIEW_COUNT_PER_VIEW_SCHEMA),
#     )


def main(fn):
    globals()[fn]()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("fn")
    args = parser.parse_args()

    main(args.fn)
