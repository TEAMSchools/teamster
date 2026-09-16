"""Rules file and crosswalk loading.

Every strategy name is checked against STRATEGIES at load time. A None value
means the strategy is a known name that a later PR implements; the pipeline
raises NotImplementedError when it is selected.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


class ConfigError(ValueError):
    """A rules or crosswalk file is invalid. The message says what and where."""


STRATEGIES: dict[str, dict[str, str | None]] = {
    "source": {
        "iready_boy": "teamster.goal_setting.adapters.iready_boy",
        "njsla_prior_year": None,
        "fast_pm3_prior_year": None,
        "fast_pm1": None,
        "star_boy": None,
        "star_spring_prior": None,
        "psat": None,
    },
    "school_goal": {
        "bubble_parameter": "teamster.goal_setting.rules.school_goal:bubble_parameter",
        "blanket": "teamster.goal_setting.rules.school_goal:blanket",
        "flat": None,
    },
    "bucket2": {
        "top_approaching_to_move": (
            "teamster.goal_setting.rules.bucket2:top_approaching_to_move"
        ),
        "none": "teamster.goal_setting.rules.bucket2:none",
    },
    "bucket3": {
        "remaining_approaching": (
            "teamster.goal_setting.rules.bucket3:remaining_approaching"
        ),
        "stretch_reachers": "teamster.goal_setting.rules.bucket3:stretch_reachers",
        "remaining_approaching_or_stretch": (
            "teamster.goal_setting.rules.bucket3:remaining_approaching_or_stretch"
        ),
        "bottom_pct_rank": None,
        "none": "teamster.goal_setting.rules.bucket3:none",
    },
}


def _check_strategy(slot: str, name: str) -> None:
    valid = sorted(STRATEGIES[slot])
    if name not in valid:
        raise ConfigError(
            f"{slot}: unknown strategy '{name}'. Valid names: {', '.join(valid)}"
        )


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Levels(Strict):
    proficient: list[int]
    approaching: list[int]


class Target(Strict):
    from_: Literal["goals_sheet", "inline"]
    column: str | None = None
    values: dict[str, dict[int, float]] | None = None  # region -> grade -> target

    # A subclass model_config REPLACES the parent's rather than merging with
    # it, so extra="forbid" must be restated here even though Strict already
    # sets it.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _alias_from(cls, data):
        if isinstance(data, dict) and "from" in data:
            data = dict(data)
            data["from_"] = data.pop("from")
        return data

    @model_validator(mode="after")
    def _shape(self):
        if self.from_ == "goals_sheet" and not self.column:
            raise ValueError("target.from goals_sheet needs column")
        if self.from_ == "inline" and not self.values:
            raise ValueError("target.from inline needs values")
        return self


class Bucket2(Strict):
    strategy: str
    ties: Literal["admit", "strict"] = "admit"

    @model_validator(mode="after")
    def _known(self):
        _check_strategy("bucket2", self.strategy)
        return self


class Bucket3(Strict):
    strategy: str

    @model_validator(mode="after")
    def _known(self):
        _check_strategy("bucket3", self.strategy)
        return self


class Amendments(Strict):
    max_per_school_grade_subject: int
    to_buckets: list[int]


class Freshness(Strict):
    min_tested_share: float
    roster_tolerance: float


class Group(Strict):
    name: str
    regions: list[str]
    grades: list[int]
    subject: Literal["Math", "Reading"]
    rollout_date: date
    source: str
    levels: Levels
    target: Target
    school_goal: str
    bucket2: Bucket2
    bucket3: Bucket3
    amendments: Amendments
    freshness: Freshness

    @model_validator(mode="after")
    def _known(self):
        _check_strategy("source", self.source)
        _check_strategy("school_goal", self.school_goal)
        return self


class RulesFile(Strict):
    academic_year: int
    groups: list[Group]

    @model_validator(mode="after")
    def _no_overlap(self):
        seen: dict[tuple[str, str, int], str] = {}
        for g in self.groups:
            for region in g.regions:
                for grade in g.grades:
                    key = (region, g.subject, grade)
                    if key in seen:
                        raise ValueError(
                            f"{region} {g.subject} grade {grade} appears in both "
                            f"'{seen[key]}' and '{g.name}'"
                        )
                    seen[key] = g.name
        return self

    def group(self, name: str) -> Group:
        for g in self.groups:
            if g.name == name:
                return g
        raise ConfigError(
            f"no group named '{name}'. Groups: {', '.join(g.name for g in self.groups)}"
        )


class Program(Strict):
    region: str
    subject: Literal["Math", "Reading"]
    bucket: Literal["Bucket 1", "Bucket 2", "Bucket 3"]
    programid: int


class Crosswalk(Strict):
    programs: list[Program]

    @model_validator(mode="after")
    def _unique(self):
        by_id: dict[tuple[str, int], list[Program]] = {}
        by_key: dict[tuple[str, str, str], Program] = {}
        for p in self.programs:
            by_id.setdefault((p.region, p.programid), []).append(p)
            key = (p.region, p.subject, p.bucket)
            if key in by_key:
                raise ValueError(f"duplicate crosswalk row for {key}")
            by_key[key] = p
        for (region, pid), rows in by_id.items():
            if len(rows) > 1:
                names = "; ".join(f"{r.subject} {r.bucket} ({pid})" for r in rows)
                raise ValueError(
                    f"{region}: program id {pid} appears {len(rows)} times: {names}"
                )
        return self

    def program_id(self, region: str, subject: str, bucket: str) -> int:
        for p in self.programs:
            if (p.region, p.subject, p.bucket) == (region, subject, bucket):
                return p.programid
        raise ConfigError(f"no program id for {region} {subject} {bucket}")


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def _validate[M: BaseModel](model: type[M], data: dict, path: Path) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as e:
        lines = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            lines.append(f"  {loc}: {err['msg']}")
        raise ConfigError(f"{path}:\n" + "\n".join(lines)) from e


def load_rules(path: Path) -> RulesFile:
    return _validate(RulesFile, _load_yaml(path), path)


def load_crosswalk(path: Path) -> Crosswalk:
    return _validate(Crosswalk, _load_yaml(path), path)
