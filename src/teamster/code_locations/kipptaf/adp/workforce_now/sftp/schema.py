import json

import py_avro_schema

from teamster.libraries.adp.workforce_now.sftp.schema import (
    AdditionalEarnings,
    PensionBenefitsEnrollments,
    TimeAndAttendance,
)

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

ADDITIONAL_EARNINGS_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=AdditionalEarnings, options=pas_options)
)

PENSION_AND_BENEFITS_ENROLLMENTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=PensionBenefitsEnrollments, options=pas_options)
)

TIME_AND_ATTENDANCE_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=TimeAndAttendance, options=pas_options)
)
