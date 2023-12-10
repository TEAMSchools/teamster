import random

from dagster import (
    DailyPartitionsDefinition,
    DynamicPartitionsDefinition,
    EnvVar,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    instance_for_test,
    materialize,
)
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.ssh.resources import SSHResource
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.core.utils.functions import get_avro_record_schema
from teamster.staging import LOCAL_TIMEZONE

SSH_IREADY = SSHResource(
    remote_host="prod-sftp-1.aws.cainc.com",
    username=EnvVar("IREADY_SFTP_USERNAME"),
    password=EnvVar("IREADY_SFTP_PASSWORD"),
)

SSH_COUCHDROP = SSHResource(
    remote_host="kipptaf.couchdrop.io",
    username=EnvVar("COUCHDROP_SFTP_USERNAME"),
    password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
)

SSH_RENLEARN_KIPPNJ = SSHResource(
    remote_host="sftp.renaissance.com",
    username=EnvVar("KIPPNJ_RENLEARN_SFTP_USERNAME"),
    password=EnvVar("KIPPNJ_RENLEARN_SFTP_PASSWORD"),
)

SSH_RENLEARN_KIPPMIAMI = SSHResource(
    remote_host="sftp.renaissance.com",
    username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
    password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
)

SSH_TITAN_KIPPCAMDEN = SSHResource(
    remote_host="sftp.titank12.com",
    username=EnvVar("KIPPCAMDEN_TITAN_SFTP_USERNAME"),
    password=EnvVar("KIPPCAMDEN_TITAN_SFTP_PASSWORD"),
)

SSH_TITAN_KIPPNEWARK = SSHResource(
    remote_host="sftp.titank12.com",
    username=EnvVar("KIPPNEWARK_TITAN_SFTP_USERNAME"),
    password=EnvVar("KIPPNEWARK_TITAN_SFTP_PASSWORD"),
)

SSH_ADP_WORKFORCE_NOW = SSHResource(
    remote_host="sftp.kippnj.org",
    username=EnvVar("ADP_SFTP_USERNAME"),
    password=EnvVar("ADP_SFTP_PASSWORD"),
)

SSH_CLEVER_REPORTS = SSHResource(
    remote_host="reports-sftp.clever.com",
    username=EnvVar("CLEVER_REPORTS_SFTP_USERNAME"),
    password=EnvVar("CLEVER_REPORTS_SFTP_PASSWORD"),
)


def _test_asset(
    asset_key: list,
    remote_dir: str,
    remote_file_regex: str,
    asset_fields: dict,
    ssh_resource: dict,
    partitions_def=None,
    instance=None,
    **kwargs,
):
    asset_name = asset_key[-1]

    asset = build_sftp_asset(
        asset_key=["staging", *asset_key],
        remote_dir=remote_dir,
        remote_file_regex=remote_file_regex,
        ssh_resource_key=next(iter(ssh_resource.keys())),
        avro_schema=get_avro_record_schema(
            name=asset_name, fields=asset_fields[asset_name]
        ),
        partitions_def=partitions_def,
        **kwargs,
    )

    if partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys(
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
        instance=instance,
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": GCSIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME),
                gcs_bucket="teamster-staging",
                object_type="avro",
            ),
            **ssh_resource,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]
        .value
        > 0
    )


def test_asset_edplan():
    from teamster.core.edplan.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["edplan", "njsmart_powerschool"],
        remote_dir="Reports",
        remote_file_regex=r"NJSMART-Power[Ss]chool\.txt",
        asset_fields=ASSET_FIELDS,
        partitions_def=DailyPartitionsDefinition(
            start_date="2023-05-08",
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%d",
            end_offset=1,
        ),
        ssh_resource={
            "ssh_edplan": SSHResource(
                remote_host="secureftp.easyiep.com",
                # username=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_USERNAME"),
                # password=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_PASSWORD"),
                username=EnvVar("KIPPNEWARK_EDPLAN_SFTP_USERNAME"),
                password=EnvVar("KIPPNEWARK_EDPLAN_SFTP_PASSWORD"),
            )
        },
    )


def test_asset_pearson_njgpa():
    from teamster.core.pearson.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["pearson", "njgpa"],
        remote_dir="/teamster-kippnewark/couchdrop/pearson/njgpa",
        remote_file_regex=(
            r"pc(?P<administration>\w+)(?P<fiscal_year>\d+)_NJ-\d+_\w+GPA\w+\.csv"
        ),
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "fiscal_year": StaticPartitionsDefinition(["22", "23"]),
                "administration": StaticPartitionsDefinition(["spr", "fbk"]),
            }
        ),
        ssh_resource={"ssh_couchdrop": SSH_COUCHDROP},
    )


def test_asset_pearson_njsla():
    from teamster.core.pearson.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["pearson", "njsla"],
        remote_dir="/teamster-kippnewark/couchdrop/pearson/njsla",
        remote_file_regex=r"pcspr(?P<fiscal_year>\d+)_NJ-\d+(?:-\d+)?_\w+\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=StaticPartitionsDefinition(["19", "22", "23"]),
        ssh_resource={"ssh_couchdrop": SSH_COUCHDROP},
    )


def test_asset_pearson_njsla_science():
    from teamster.core.pearson.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["pearson", "njsla_science"],
        remote_dir="/teamster-kippnewark/couchdrop/pearson/njsla_science",
        remote_file_regex=r"njs(?P<fiscal_year>\d+)_NJ-\d+_\w+\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=StaticPartitionsDefinition(["19", "22", "23"]),
        ssh_resource={"ssh_couchdrop": SSH_COUCHDROP},
    )


def test_asset_pearson_parcc():
    from teamster.core.pearson.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["pearson", "parcc"],
        remote_dir="/teamster-kippnewark/couchdrop/pearson/parcc",
        remote_file_regex=r"PC_pcspr(?P<fiscal_year>\d+)_NJ-\d+(?:-\d+)?_\w+\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=StaticPartitionsDefinition(["16", "17", "18"]),
        ssh_resource={"ssh_couchdrop": SSH_COUCHDROP},
    )


def test_asset_renlearn_accelerated_reader():
    from teamster.core.renlearn.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["renlearn", "accelerated_reader"],
        remote_dir=".",
        # remote_file_regex=r"KIPP Miami\.zip",
        remote_file_regex=r"KIPP TEAM & Family\.zip",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["AR"]),
                "start_date": FiscalYearPartitionsDefinition(
                    start_date="2023-07-01", timezone=LOCAL_TIMEZONE.name, start_month=7
                ),
            }
        ),
        ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI},
        archive_filepath=r"(?P<subject>).csv",
        slugify_cols=False,
    )


def test_asset_renlearn_star():
    from teamster.core.renlearn.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["renlearn", "star"],
        remote_dir=".",
        remote_file_regex=r"KIPP Miami\.zip",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["SM", "SR", "SEL"]),
                "start_date": FiscalYearPartitionsDefinition(
                    start_date="2023-07-01", timezone=LOCAL_TIMEZONE.name, start_month=7
                ),
            }
        ),
        ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI},
        archive_filepath=r"(?P<subject>).csv",
        slugify_cols=False,
    )


def test_asset_renlearn_star_skill_area():
    from teamster.core.renlearn.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["renlearn", "star_skill_area"],
        remote_dir=".",
        remote_file_regex=r"KIPP Miami\.zip",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["SM", "SR", "SEL"]),
                "start_date": FiscalYearPartitionsDefinition(
                    start_date="2023-07-01", timezone=LOCAL_TIMEZONE.name, start_month=7
                ),
            }
        ),
        ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI},
        archive_filepath=r"(?P<subject>)_SkillArea_v1.csv",
        slugify_cols=False,
    )


def test_asset_renlearn_star_dashboard_standards():
    from teamster.core.renlearn.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["renlearn", "star_dashboard_standards"],
        remote_dir=".",
        remote_file_regex=r"KIPP Miami\.zip",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["SM", "SR", "SEL"]),
                "start_date": FiscalYearPartitionsDefinition(
                    start_date="2023-07-01", timezone=LOCAL_TIMEZONE.name, start_month=7
                ),
            }
        ),
        ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI},
        archive_filepath=r"(?P<subject>)_Dashboard_Standards_v2.csv",
        slugify_cols=False,
    )


def test_asset_renlearn_fast_star():
    from teamster.core.renlearn.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["renlearn", "fast_star"],
        remote_dir=".",
        remote_file_regex=r"KIPP Miami\.zip",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(
                    ["SM", "SR", "SEL", "SEL_Domains"]
                ),
                "start_date": FiscalYearPartitionsDefinition(
                    start_date="2023-07-01", timezone=LOCAL_TIMEZONE.name, start_month=7
                ),
            }
        ),
        ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI},
        archive_filepath=r"FL_FAST_(?P<subject>)_K-2.csv",
        slugify_cols=False,
    )


def test_asset_fldoe_fast():
    from teamster.kippmiami.fldoe.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["fldoe", "fast"],
        remote_dir="/teamster-kippmiami/couchdrop/fldoe/fast",
        remote_file_regex=r"(?P<school_year_term>)\/.*(?P<grade_level_subject>).*\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "school_year_term": StaticPartitionsDefinition(
                    [
                        "2022/PM1",
                        "2022/PM2",
                        "2022/PM3",
                        "2023/PM1",
                        "2023/PM2",
                        "2023/PM3",
                    ]
                ),
                "grade_level_subject": StaticPartitionsDefinition(
                    [
                        r"3\w*ELAReading",
                        r"3\w*Mathematics",
                        r"4\w*ELAReading",
                        r"4\w*Mathematics",
                        r"5\w*ELAReading",
                        r"5\w*Mathematics",
                        r"6\w*ELAReading",
                        r"6\w*Mathematics",
                        r"7\w*ELAReading",
                        r"7\w*Mathematics",
                        r"8\w*ELAReading",
                        r"8\w*Mathematics",
                    ]
                ),
            }
        ),
        ssh_resource={"ssh_couchdrop": SSH_COUCHDROP},
    )


def test_asset_fldoe_fsa():
    from teamster.kippmiami.fldoe.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["fldoe", "fsa"],
        remote_dir="/teamster-kippmiami/couchdrop/fldoe/fsa/student_scores",
        remote_file_regex=(
            r"FSA_(?P<school_year_term>)SPR_132332_SRS-E_(?P<grade_level_subject>)_SCHL\.csv"
        ),
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "school_year_term": StaticPartitionsDefinition(["22", "21"]),
                "grade_level_subject": StaticPartitionsDefinition(
                    ["ELA_GR03", "SCI", "MATH", "ELA_GR04_10"]
                ),
            }
        ),
        ssh_resource={"ssh_couchdrop": SSH_COUCHDROP},
    )


def test_asset_iready_diagnostic_results():
    from teamster.core.iready.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["iready", "diagnostic_results"],
        remote_dir="/exports/fl-kipp_miami",
        remote_file_regex=r"(?:(?P<academic_year>\w+)\/)?diagnostic_results_(?P<subject>\w+)\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["ela", "math"]),
                "academic_year": StaticPartitionsDefinition(["Current_Year", "2022"]),
            }
        ),
        ssh_resource={"ssh_iready": SSH_IREADY},
        slugify_replacements=[["%", "percent"]],
    )


def test_asset_iready_personalized_instruction_by_lesson():
    from teamster.core.iready.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["iready", "personalized_instruction_by_lesson"],
        remote_dir="/exports/fl-kipp_miami",
        remote_file_regex=r"(?:(?P<academic_year>\w+)\/)?personalized_instruction_by_lesson_(?P<subject>\w+)\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["ela", "math"]),
                "academic_year": StaticPartitionsDefinition(["Current_Year", "2022"]),
            }
        ),
        ssh_resource={"ssh_iready": SSH_IREADY},
        slugify_replacements=[["%", "percent"]],
    )


def test_asset_iready_instructional_usage_data():
    from teamster.core.iready.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["iready", "instructional_usage_data"],
        remote_dir="/exports/fl-kipp_miami",
        remote_file_regex=r"(?:(?P<academic_year>\w+)\/)?instructional_usage_data_(?P<subject>\w+)\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["ela", "math"]),
                "academic_year": StaticPartitionsDefinition(["Current_Year", "2022"]),
            }
        ),
        ssh_resource={"ssh_iready": SSH_IREADY},
        slugify_replacements=[["%", "percent"]],
    )


def test_asset_iready_diagnostic_and_instruction():
    from teamster.core.iready.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["iready", "diagnostic_and_instruction"],
        remote_dir="/exports/fl-kipp_miami",
        remote_file_regex=r"(?:(?P<academic_year>\w+)\/)?diagnostic_and_instruction_(?P<subject>\w+)_ytd_window\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["ela", "math"]),
                "academic_year": StaticPartitionsDefinition(["Current_Year", "2022"]),
            }
        ),
        ssh_resource={"ssh_iready": SSH_IREADY},
        slugify_replacements=[["%", "percent"]],
    )


def test_asset_titan_person_data():
    from teamster.core.titan.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["titan", "person_data"],
        remote_dir=".",
        remote_file_regex=r"persondata(?P<fiscal_year>\d{4})\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=StaticPartitionsDefinition(["2021", "2022", "2023"]),
        ssh_resource={"ssh_titan": SSH_TITAN_KIPPNEWARK},
    )


def test_asset_titan_income_form_data():
    from teamster.core.titan.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["titan", "income_form_data"],
        remote_dir=".",
        remote_file_regex=r"incomeformdata(?P<fiscal_year>\d{4})\.csv",
        asset_fields=ASSET_FIELDS,
        partitions_def=StaticPartitionsDefinition(["2021", "2022", "2023"]),
        ssh_resource={"ssh_titan": SSH_TITAN_KIPPNEWARK},
    )


def test_asset_achieve3k_students():
    from teamster.kipptaf.achieve3k.schema import ASSET_FIELDS

    partitions_def_name = "staging__achieve3k__students"

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=partitions_def_name, partition_keys=["2023-12-06"]
        )

        _test_asset(
            asset_key=["achieve3k", "students"],
            remote_dir="outgoing",
            remote_file_regex=r"(?P<date>\d{4}[-\d{2}]+)-\d+_D[\d+_]+(\w\d{4}[-\d{2}]+_){2}student\.\w+",
            asset_fields=ASSET_FIELDS,
            ssh_resource={
                "ssh_achieve3k": SSHResource(
                    remote_host="xfer.achieve3000.com",
                    username=EnvVar("ACHIEVE3K_SFTP_USERNAME"),
                    password=EnvVar("ACHIEVE3K_SFTP_PASSWORD"),
                )
            },
            partitions_def=DynamicPartitionsDefinition(name=partitions_def_name),
            instance=instance,
        )


def test_asset_clever_daily_participation():
    from teamster.kipptaf.clever.schema import ASSET_FIELDS

    remote_dir = "daily-participation"

    asset_name = remote_dir.replace("-", "_")

    partitions_def_name = f"staging__clever_reports__date__{asset_name}"

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=partitions_def_name, partition_keys=["2023-12-05"]
        )

        _test_asset(
            asset_key=["clever_reports", asset_name],
            remote_dir=remote_dir,
            remote_file_regex=rf"(?P<date>\d{4}-\d{2}-\d{2})-{remote_dir}-(?P<type>\w+)\.csv",
            asset_fields=ASSET_FIELDS,
            ssh_resource={"ssh_clever_reports": SSH_CLEVER_REPORTS},
            partitions_def=MultiPartitionsDefinition(
                {
                    "date": DynamicPartitionsDefinition(name=partitions_def_name),
                    "type": StaticPartitionsDefinition(
                        ["staff", "students", "teachers"]
                    ),
                }
            ),
            instance=instance,
        )


def test_asset_clever_resource_usage():
    from teamster.kipptaf.clever.schema import ASSET_FIELDS

    remote_dir = "resource-usage"

    asset_name = remote_dir.replace("-", "_")

    partitions_def_name = f"staging__clever_reports__date__{asset_name}"

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=partitions_def_name, partition_keys=["2023-12-05"]
        )

        _test_asset(
            asset_key=["clever_reports", asset_name],
            remote_dir=remote_dir,
            remote_file_regex=rf"(?P<date>\d{4}-\d{2}-\d{2})-{remote_dir}-(?P<type>\w+)\.csv",
            asset_fields=ASSET_FIELDS,
            ssh_resource={"ssh_clever_reports": SSH_CLEVER_REPORTS},
            partitions_def=MultiPartitionsDefinition(
                {
                    "date": DynamicPartitionsDefinition(name=partitions_def_name),
                    "type": StaticPartitionsDefinition(
                        ["staff", "students", "teachers"]
                    ),
                }
            ),
            instance=instance,
        )


""" cannot test in dev: IP filter
def test_asset_adp_workforce_now_pension_and_benefits_enrollments():
    from teamster.kipptaf.adp.workforce_now.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["adp_workforce_now", "pension_and_benefits_enrollments"],
        remote_dir=".",
        remote_file_regex=r"pension_and_benefits_enrollments\.csv",
        asset_fields=ASSET_FIELDS,
        ssh_resource={"ssh_adp_workforce_now": SSH_ADP_WORKFORCE_NOW},
    )


def test_asset_adp_workforce_now_comprehensive_benefits_report():
    from teamster.kipptaf.adp.workforce_now.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["adp_workforce_now", "comprehensive_benefits_report"],
        remote_dir=".",
        remote_file_regex=r"comprehensive_benefits_report\.csv",
        asset_fields=ASSET_FIELDS,
        ssh_resource={"ssh_adp_workforce_now": SSH_ADP_WORKFORCE_NOW},
    )


def test_asset_adp_workforce_now_additional_earnings_report():
    from teamster.kipptaf.adp.workforce_now.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["adp_workforce_now", "additional_earnings_report"],
        remote_dir=".",
        remote_file_regex=r"additional_earnings_report\.csv",
        asset_fields=ASSET_FIELDS,
        ssh_resource={"ssh_adp_workforce_now": SSH_ADP_WORKFORCE_NOW},
    )
"""
