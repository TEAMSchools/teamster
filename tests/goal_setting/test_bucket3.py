from teamster.goal_setting.config import Levels
from teamster.goal_setting.rules.bucket3 import (
    none,
    remaining_approaching,
    remaining_approaching_or_stretch,
    stretch_reachers,
)

from .fixtures.roster_small import student, untested

LEVELS = Levels(proficient=[5], approaching=[4])


def appr_left_out(**kw):
    return student(is_approaching=True, rank=9, bucket=None, **kw)


def appr_in_b2(**kw):
    return student(is_approaching=True, rank=1, bucket="Bucket 2", **kw)


def below(stretch: int, **kw):
    return student(is_below=True, projected_level=3, stretch_level=stretch, **kw)


def test_remaining_approaching_takes_only_left_out_approaching():
    out = remaining_approaching([appr_left_out(), appr_in_b2(), below(5)], LEVELS)
    assert [r.bucket for r in out] == ["Bucket 3", "Bucket 2", None]


def test_stretch_reachers_takes_anyone_unplaced_whose_stretch_level_is_proficient():
    out = stretch_reachers(
        [
            appr_left_out(stretch_level=5),
            appr_left_out(stretch_level=4),
            below(5),
            below(4),
        ],
        LEVELS,
    )
    assert [r.bucket for r in out] == ["Bucket 3", None, "Bucket 3", None]


def test_stretch_reacher_below_approaching_enters():
    (r,) = stretch_reachers([below(5)], LEVELS)
    assert r.bucket == "Bucket 3" and "stretch" in r.reason


def test_remaining_or_stretch_is_the_union():
    recs = [appr_left_out(stretch_level=4), below(5), below(4), appr_in_b2()]
    out = remaining_approaching_or_stretch(recs, LEVELS)
    assert [r.bucket for r in out] == ["Bucket 3", "Bucket 3", None, "Bucket 2"]


def test_untested_never_enters_bucket_3():
    for fn in (
        remaining_approaching,
        stretch_reachers,
        remaining_approaching_or_stretch,
    ):
        (r,) = fn([untested()], LEVELS)
        assert r.bucket is None


def test_none_is_identity():
    recs = [appr_left_out()]
    assert none(recs, LEVELS) == recs
