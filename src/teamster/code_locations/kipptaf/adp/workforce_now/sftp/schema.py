import json

import py_avro_schema

from teamster.libraries.adp.workforce_now.sftp.schema import (
    AdditionalEarnings,
    ComprehensiveBenefits,
    PensionBenefitsEnrollments,
)

ADDITIONAL_EARNINGS_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=AdditionalEarnings, namespace="additional_earnings_report"
    )
)

COMPREHENSIVE_BENEFITS_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=ComprehensiveBenefits, namespace="comprehensive_benefits_report"
    )
)

PENSION_AND_BENEFITS_ENROLLMENTS_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=PensionBenefitsEnrollments, namespace="pension_and_benefits_enrollments"
    )
)
