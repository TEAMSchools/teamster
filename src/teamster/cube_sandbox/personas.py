"""Load the declared persona set.

Personas are hand-written because canaries.yml names them. The manifest
asserts the declared set covers every scope value access.js handles, so this
file cannot quietly fall behind the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

UNRESOLVABLE = "unresolvable@ktaf-sandbox.invalid"


@dataclass(frozen=True)
class Persona:
    email: str
    given_name: str
    surname: str
    purpose: str
    scopes: dict[str, str]
    reportees: list[str] = field(default_factory=list)


def load(path: Path) -> list[Persona]:
    doc = yaml.safe_load(path.read_text()) or {}
    return [Persona(**p) for p in doc.get("personas", [])]
