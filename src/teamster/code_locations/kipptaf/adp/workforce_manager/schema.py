import json

import py_avro_schema

from teamster.libraries.adp.workforce_manager.schema import (
    AccrualReportingPeriodSummary,
    TimeDetail,
)


class accrual_reporting_period_summary_record(AccrualReportingPeriodSummary):
    """helper classes for backwards compatibility"""


class time_details_record(TimeDetail):
    """helper classes for backwards compatibility"""


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE


ACCRUAL_REPORTING_PERIOD_SUMMARY_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=accrual_reporting_period_summary_record, options=pas_options
    )
)

TIME_DETAILS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=time_details_record, options=pas_options)
)
