from teamster.goal_setting.config import Levels
from teamster.goal_setting.rules.classify import classify

from .fixtures.roster_small import student, untested

LEVELS = Levels(proficient=[5], approaching=[4])


def test_level_5_is_proficient():
    (r,) = classify([student(projected_level=5)], LEVELS)
    assert (r.is_proficient, r.is_approaching, r.is_below) == (True, False, False)


def test_level_4_is_approaching():
    (r,) = classify([student(projected_level=4)], LEVELS)
    assert (r.is_proficient, r.is_approaching, r.is_below) == (False, True, False)


def test_level_3_is_below():
    (r,) = classify([student(projected_level=3)], LEVELS)
    assert (r.is_proficient, r.is_approaching, r.is_below) == (False, False, True)


def test_untested_is_none_of_the_three():
    (r,) = classify([untested()], LEVELS)
    assert (r.is_proficient, r.is_approaching, r.is_below) == (False, False, False)


def test_classify_does_not_mutate_input():
    src = student(projected_level=5)
    classify([src], LEVELS)
    assert src.is_proficient is False


def test_old_early_on_or_better_rule_is_just_different_levels():
    old = Levels(proficient=[4, 5], approaching=[3])
    (r,) = classify([student(projected_level=4)], old)
    assert r.is_proficient is True
