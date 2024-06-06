import json

import py_avro_schema

from teamster.libraries.adp.workforce_now.sftp.schema import (
    AdditionalEarnings,
    ComprehensiveBenefits,
    PensionBenefitsEnrollments,
)

ASSET_SCHEMA = {
    "additional_earnings_report": json.loads(
        py_avro_schema.generate(
            py_type=AdditionalEarnings, namespace="additional_earnings_report"
        )
    ),
    "comprehensive_benefits_report": json.loads(
        py_avro_schema.generate(
            py_type=ComprehensiveBenefits, namespace="comprehensive_benefits_report"
        )
    ),
    "pension_and_benefits_enrollments": json.loads(
        py_avro_schema.generate(
            py_type=PensionBenefitsEnrollments,
            namespace="pension_and_benefits_enrollments",
        )
    ),
}
