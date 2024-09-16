import json
import pathlib

import fastavro
import py_avro_schema

from teamster.code_locations.kipptaf.schoolmint.grow.schema import assignments_record

fp = pathlib.Path(
    "env/dagster_kipptaf_schoolmint_grow_assignments__dagster_partition_archived=f__dagster_partition_fiscal_year=2024__dagster_partition_date=2023-08-01__dagster_partition_hour=00__dagster_partition_minute=00_data"
)

generated_schema = py_avro_schema.generate(py_type=assignments_record)

reader_schema = fastavro.parse_schema(json.loads(generated_schema))

avro_reader = fastavro.reader(fo=fp.open(mode="rb"))

record = next(avro_reader)

print(record)
