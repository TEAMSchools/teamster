import json

import py_avro_schema

from teamster.libraries.adp.workforce_now.api.schema import Worker

WORKER_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=Worker,
        namespace="worker",
        options=py_avro_schema.Option.USE_FIELD_ALIAS,
    )
)
