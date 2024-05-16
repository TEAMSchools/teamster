import json

import py_avro_schema

from teamster.adp.workforce_manager.schema import (
    AccrualReportingPeriodSummary,
    TimeDetail,
)


class accrual_reporting_period_summary_record(AccrualReportingPeriodSummary):
    """helper classes for backwards compatibility"""


class time_details_record(TimeDetail):
    """helper classes for backwards compatibility"""


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE


ASSET_SCHEMA = {
    "accrual_reporting_period_summary": json.loads(
        py_avro_schema.generate(
            py_type=accrual_reporting_period_summary_record, options=pas_options
        )
    ),
    "time_details": json.loads(
        py_avro_schema.generate(py_type=time_details_record, options=pas_options)
    ),
}
