import copy

from teamster.goal_setting.diff import add_student_depth, diff_manifests

from .fixtures.roster_small import student

BASE = {
    "group": "nj_math_1_2",
    "school_goals": [
        {
            "region": "Newark",
            "school": "TEAM",
            "school_id": 1,
            "grade_level": 1,
            "subject": "Math",
            "bubble_parameter": 0.52,
            "n_to_move": 12,
            "goal": 0.41,
        },
    ],
    "bucket_counts": [
        {
            "region": "Newark",
            "school": "TEAM",
            "grade_level": 1,
            "subject": "Math",
            "bucket": "Bucket 1",
            "bucket4_outcome": None,
            "n": 20,
        },
        {
            "region": "Newark",
            "school": "TEAM",
            "grade_level": 1,
            "subject": "Math",
            "bucket": "Bucket 2",
            "bucket4_outcome": None,
            "n": 12,
        },
    ],
}


def test_no_prior_run():
    rep = diff_manifests(None, BASE)
    assert rep.verdict == "no prior run" and "no prior" in rep.render()


def test_identical_manifests_is_no_change():
    rep = diff_manifests(BASE, copy.deepcopy(BASE))
    assert (
        rep.verdict == "no change"
        and rep.goal_changes == []
        and rep.count_changes == []
    )


def test_goal_and_count_changes_are_listed():
    cur = copy.deepcopy(BASE)
    cur["school_goals"][0].update(bubble_parameter=0.48, n_to_move=11, goal=0.40)
    cur["bucket_counts"][1]["n"] = 11
    rep = diff_manifests(BASE, cur)
    assert rep.goal_changes[0]["school"] == "TEAM"
    assert (
        rep.goal_changes[0]["old"]["bubble_parameter"] == 0.52
        and rep.goal_changes[0]["new"]["bubble_parameter"] == 0.48
    )
    assert rep.count_changes[0] == {
        "region": "Newark",
        "school": "TEAM",
        "grade_level": 1,
        "subject": "Math",
        "bucket": "Bucket 2",
        "bucket4_outcome": None,
        "old": 12,
        "new": 11,
    }
    text = rep.render()
    assert "0.52" in text and "0.48" in text and "Bucket 2" in text


def test_student_depth_additive_only():
    prior = [
        {
            "region": "Newark",
            "student_number": "1",
            "subject": "Math",
            "bucket": "Bucket 1",
        }
    ]
    cur = [
        student(student_number=1, bucket="Bucket 1"),
        student(student_number=2, bucket="Bucket 4", bucket4_outcome="untested"),
    ]
    rep = add_student_depth(diff_manifests(BASE, copy.deepcopy(BASE)), prior, cur)
    assert rep.verdict == "additive only" and rep.roster_churn == {"new": 1, "gone": 0}
    assert rep.transitions == []


def test_student_depth_reclassification_is_named_and_counted():
    prior = [
        {
            "region": "Newark",
            "student_number": "1",
            "subject": "Math",
            "bucket": "Bucket 2",
        },
        {
            "region": "Newark",
            "student_number": "2",
            "subject": "Math",
            "bucket": "Bucket 2",
        },
    ]
    cur = [
        student(student_number=1, bucket="Bucket 4", bucket4_outcome="below"),
        student(student_number=2, bucket="Bucket 2"),
    ]
    rep = add_student_depth(diff_manifests(BASE, copy.deepcopy(BASE)), prior, cur)
    assert rep.verdict == "reclassifies" and rep.n_reclassified == 1
    assert rep.transitions == [
        {
            "region": "Newark",
            "school": "TEAM",
            "grade_level": 1,
            "subject": "Math",
            "from": "Bucket 2",
            "to": "Bucket 4",
            "n": 1,
        }
    ]
    assert "RECLASSIFIES 1" in rep.render()


def test_student_depth_keys_on_region_and_student_number():
    prior = [
        {
            "region": "Camden",
            "student_number": "1",
            "subject": "Math",
            "bucket": "Bucket 2",
        }
    ]
    cur = [
        student(
            student_number=1,
            region="Newark",
            bucket="Bucket 4",
            bucket4_outcome="below",
        )
    ]
    rep = add_student_depth(diff_manifests(BASE, copy.deepcopy(BASE)), prior, cur)
    assert rep.transitions == [] and rep.roster_churn == {"new": 1, "gone": 1}
