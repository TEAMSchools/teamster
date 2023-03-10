import pendulum
from dagster import MultiPartitionKey

from teamster.core.utils.classes import FiscalYear


def parse_partition_key(partition_key, dimension=None):
    try:
        date_formats = iter(
            ["YYYY-MM-DDTHH:mm:ss.SSSSSSZ", "YYYY-MM-DDTHH:mm:ssZ", "YYYY-MM-DD"]
        )

        while True:
            try:
                partition_key_parsed = pendulum.from_format(
                    string=partition_key, fmt=next(date_formats)
                )

                break
            except ValueError:
                partition_key_parsed = None

        fiscal_year = FiscalYear(
            datetime=partition_key_parsed, start_month=7
        ).fiscal_year

        return [
            f"_dagster_partition_fiscal_year={fiscal_year}",
            f"_dagster_partition_date={partition_key_parsed.to_date_string()}",
            f"_dagster_partition_hour={partition_key_parsed.format('HH')}",
            f"_dagster_partition_minute={partition_key_parsed.format('mm')}",
        ]
    except StopIteration:
        if dimension is not None:
            return [f"_dagster_partition_{dimension}={partition_key}"]
        else:
            return [f"_dagster_partition_key={partition_key}"]


def partition_key_to_vars(partition_key):
    path = []

    if isinstance(partition_key, MultiPartitionKey):
        for (
            dimension,
            key,
        ) in partition_key.keys_by_dimension.items():
            path.extend(parse_partition_key(partition_key=key, dimension=dimension))
    else:
        path.append(parse_partition_key(partition_key=key))

    path.append("data")

    return {"partition_path": "/".join(path)}


def get_avro_type(value):
    if isinstance(value, bool):
        return ["boolean"]
    elif isinstance(value, int):
        return ["int", "long"]
    elif isinstance(value, float):
        return ["float", "double"]
    elif isinstance(value, bytes):
        return ["bytes"]
    elif isinstance(value, list):
        return infer_avro_schema_fields(value)
    elif isinstance(value, dict):
        return infer_avro_schema_fields([value])
    elif isinstance(value, str):
        return ["string"]


def infer_avro_schema_fields(list_of_dicts):
    all_keys = set().union(*(d.keys() for d in list_of_dicts))

    types = {}
    while all_keys:
        d = next(iter(list_of_dicts))

        for k in all_keys.copy():
            v = d.get(k)
            print(k, v)

            avro_type = get_avro_type(v)
            if avro_type:
                types[k] = avro_type
                all_keys.remove(k)

    fields = []
    for k, v in types.items():
        v.insert(0, "null")
        fields.append({"name": k, "type": v})

    return fields
