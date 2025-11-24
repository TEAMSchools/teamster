import json

import py_avro_schema

from teamster.libraries.amplify.mclass.sftp.schema import (
    BenchmarkStudentSummary,
    PMStudentSummary,
)

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

BENCHMARK_STUDENT_SUMMARY_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=BenchmarkStudentSummary, options=pas_options)
)

PM_STUDENT_SUMMARY_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=PMStudentSummary, options=pas_options)
)
