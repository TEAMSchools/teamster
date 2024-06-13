import json

import py_avro_schema

from teamster.libraries.smartrecruiters.schema import Applicant, Application, Rating

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

APPLICANTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Applicant, namespace="applicant")
)

APPLICATIONS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Application, namespace="application")
)

RATINGS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Rating, options=pas_options)
)
