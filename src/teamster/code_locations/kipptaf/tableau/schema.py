import json

import py_avro_schema

from teamster.libraries.tableau.schema import ViewCountPerView

VIEW_COUNT_PER_VIEW = json.loads(
    py_avro_schema.generate(
        py_type=ViewCountPerView,
        options=(
            py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE
        ),
    )
)
