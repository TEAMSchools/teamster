import re
import subprocess


def _test_definitions_validate(module_names: list[str]):
    module_args = []

    for m in module_names:
        module_args.extend(f"-m teamster.code_locations.{m}.definitions".split())

    output = subprocess.check_output(
        args=["dagster", "definitions", "validate", *module_args]
    )

    for m in module_names:
        match = re.search(
            pattern=(
                r"Validation successful for code location teamster\.code_locations\."
                rf"(?P<code_location>{m})\.definitions"
            ),
            string=output.decode(),
        )

        assert match is not None
        assert match.groupdict()["code_location"] == m


def test_definitions_kipptaf():
    _test_definitions_validate(["kipptaf"])


def test_definitions_kippcamden():
    _test_definitions_validate(["kippcamden"])


def test_definitions_kippmiami():
    _test_definitions_validate(["kippmiami"])


def test_definitions_kippnewark():
    _test_definitions_validate(["kippnewark"])


def test_definitions_all():
    _test_definitions_validate(["kippcamden", "kippmiami", "kippnewark", "kipptaf"])
