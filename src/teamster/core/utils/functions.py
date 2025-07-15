import csv
import re
from datetime import datetime, timezone
from io import StringIO
from typing import Mapping

from dagster import MultiPartitionKey
from dagster_shared import check
from slugify import slugify

from teamster.core.utils.classes import FiscalYear


def regex_pattern_replace(pattern: str, replacements: Mapping[str, str]):
    for group in re.findall(r"\(\?P<\w+>[\w\+\-\.\[\]\{\}\/\\\|]*\)", pattern):
        match = check.not_none(
            value=re.search(pattern=r"(?<=<)(\w+)(?=>)", string=group)
        )

        group_value = replacements.get(match.group(0), "")

        pattern = pattern.replace(group, group_value)

    return pattern


def parse_partition_key(partition_key, dimension=None):
    try:
        date_formats = iter(
            [
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
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
                    timestamp=0, tz=timezone.utc
                ):
                    partition_key_parsed = datetime.now(timezone.utc)

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


def chunk(obj: list, size: int):
    """https://stackoverflow.com/a/312464
    Yield successive chunks from list object.
    """

    for i in range(0, len(obj), size):
        yield obj[i : i + size]


def dict_reader_to_records(
    dict_reader: csv.DictReader,
    slugify_cols: bool = True,
    slugify_replacements: list[list[str]] | None = None,
) -> list[dict[str, str]]:
    if slugify_replacements is None:
        slugify_replacements = []

    if slugify_cols:
        dict_reader.fieldnames = [
            slugify(text=text, separator="_", replacements=slugify_replacements)
            for text in check.not_none(value=dict_reader.fieldnames)
        ]

    records = [
        {key: value for key, value in row.items() if value != ""} for row in dict_reader
    ]

    return records


def csv_string_to_records(
    csv_string: str,
    slugify_cols: bool = True,
    slugify_replacements: list[list[str]] | None = None,
) -> list[dict[str, str]]:
    return dict_reader_to_records(
        dict_reader=csv.DictReader(f=StringIO(csv_string)),
        slugify_cols=slugify_cols,
        slugify_replacements=slugify_replacements,
    )


def file_to_records(
    file: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    slugify_cols: bool = True,
    slugify_replacements: list[list[str]] | None = None,
) -> list[dict[str, str]]:
    with open(file=file, encoding=encoding, mode="r") as f:
        dict_reader = csv.DictReader(f=f, delimiter=delimiter)

    records = dict_reader_to_records(
        dict_reader=dict_reader,
        slugify_cols=slugify_cols,
        slugify_replacements=slugify_replacements,
    )

    return records
