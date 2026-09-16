"""Rules must be pure: no warehouse client anywhere under rules/."""

import ast
from pathlib import Path

RULES = Path(__file__).resolve().parents[2] / "src/teamster/goal_setting/rules"
BANNED = ("google.cloud", "bigquery", "teamster.goal_setting.adapters")


def test_rules_modules_import_no_warehouse_client():
    offenders = []
    for path in RULES.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if n.startswith(BANNED):
                    offenders.append(f"{path.name}: {n}")
    assert offenders == []
