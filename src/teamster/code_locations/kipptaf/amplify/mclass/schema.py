import json

import py_avro_schema

from teamster.libraries.amplify.mclass.schema import (
    BenchmarkStudentSummary,
    PMStudentSummary,
)


class benchmark_student_summary_record(BenchmarkStudentSummary):
    """helper classes for backwards compatibility"""


class pm_student_summary_record(PMStudentSummary):
    """helper classes for backwards compatibility"""


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

BENCHMARK_STUDENT_SUMMARY_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=benchmark_student_summary_record, options=pas_options
    )
)

PM_STUDENT_SUMMARY_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=pm_student_summary_record, options=pas_options)
)
