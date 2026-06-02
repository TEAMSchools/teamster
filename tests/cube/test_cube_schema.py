from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CUBE_MODEL_DIR = Path(__file__).resolve().parents[2] / "src" / "cube" / "model"


@pytest.mark.parametrize(
    "yaml_file",
    list((CUBE_MODEL_DIR / "cubes").rglob("*.yml")),
    ids=lambda p: str(p.relative_to(CUBE_MODEL_DIR)),
)
def test_cube_name_no_dim_or_fct_prefix(yaml_file: Path) -> None:
    """Cube names must not start with dim_ or fct_.

    The naming convention drives queryRewrite security — see
    docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md#cube-naming-convention.
    """
    data = yaml.safe_load(yaml_file.read_text())
    for cube in data.get("cubes", []):
        name = cube["name"]
        assert not name.startswith("dim_"), (
            f"{yaml_file.name}: cube '{name}' uses reserved dim_ prefix"
        )
        assert not name.startswith("fct_"), (
            f"{yaml_file.name}: cube '{name}' uses reserved fct_ prefix"
        )
