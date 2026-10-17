"""The package loads and its CLI rejects an unknown command."""

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers the package at runtime
from cube_validate import cli  # registered by conftest.py


def test_cli_rejects_an_unknown_command():
    with pytest.raises(SystemExit) as e:
        cli.main(["nope"])
    assert e.value.code == 2
