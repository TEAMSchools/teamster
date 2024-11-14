import re
from datetime import datetime
from typing import Mapping
from zoneinfo import ZoneInfo

from dagster import MultiPartitionKey, _check

from teamster.core.utils.classes import FiscalYear


def regex_pattern_replace(pattern: str, replacements: Mapping[str, str]):
    for group in re.findall(r"\(\?P<\w+>[\w\+\-\.\[\]\{\}\/\\\|]*\)", pattern):
        match = _check.not_none(
            value=re.search(pattern=r"(?<=<)(\w+)(?=>)", string=group)
        )

        group_value = replacements.get(match.group(0), "")

        pattern = pattern.replace(group, group_value)

    return pattern


def parse_partition_key(partition_key, dimension=None):
    try:
        date_formats = iter(
            [
                "%Y-%m-DDTHH:mm:ss.SSSSSSZ",
                "%Y-%m-DDTHH:mm:ssZ",
                "%Y-%m-DDTHH:mm:ss.SSSSSS[Z]",
                "%Y-%m-DDTHH:mm:ss[Z]",
                "%Y-%m-%d",
            ]
        )

        while True:
            try:
                partition_key_parsed = datetime.strptime(
                    partition_key, next(date_formats)
                )

                # save resync file with current timestamp
                if partition_key_parsed == datetime.fromtimestamp(
                    timestamp=0, tz=ZoneInfo("UTC")
                ):
                    partition_key_parsed = datetime.now(ZoneInfo("UTC"))

                break
            except ValueError:
                partition_key_parsed = None

        pk_fiscal_year = FiscalYear(datetime=partition_key_parsed, start_month=7)

        return [
            f"_dagster_partition_fiscal_year={pk_fiscal_year.fiscal_year}",
            f"_dagster_partition_date={partition_key_parsed.date().isoformat()}",
            f"_dagster_partition_hour={partition_key_parsed.strftime('%H')}",
            f"_dagster_partition_minute={partition_key_parsed.strftime('%M')}",
        ]
    except StopIteration:
        if dimension is not None:
            return [f"_dagster_partition_{dimension}={partition_key}"]
        else:
            return [f"_dagster_partition_key={partition_key}"]


def get_partition_key_path(partition_key, path):
    if isinstance(partition_key, MultiPartitionKey):
        for dimension, key in partition_key.keys_by_dimension.items():
            path.extend(parse_partition_key(partition_key=key, dimension=dimension))
    else:
        path.extend(parse_partition_key(partition_key=partition_key))

    path.append("data")

    return path


def partition_key_to_vars(partition_key):
    path = get_partition_key_path(partition_key=partition_key, path=[])
    return {"partition_path": "/".join(path)}
