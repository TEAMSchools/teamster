import subprocess


def _test_definitions_validate(module_names: list[str]):
    module_args = []

    for m in module_names:
        module_args.extend(f"-m teamster.code_locations.{m}.definitions".split())

    subprocess.run(args=["dagster", "definitions", "validate", *module_args])


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
