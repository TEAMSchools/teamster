from teamster.goal_setting.rules.assign import finalize

from .fixtures.roster_small import student, untested


def test_proficient_becomes_bucket_1_with_reason():
    (r,) = finalize(
        [student(is_proficient=True, projected_level=5, projected_score=420)]
    )
    assert r.bucket == "Bucket 1" and r.reason == "proficient, projected 420 at level 5"


def test_unassigned_tested_becomes_bucket_4_below():
    (r,) = finalize([student(is_below=True, projected_level=2)])
    assert (r.bucket, r.bucket4_outcome) == ("Bucket 4", "below")


def test_untested_becomes_bucket_4_untested():
    (r,) = finalize([untested()])
    assert (r.bucket, r.bucket4_outcome) == ("Bucket 4", "untested")
    assert r.reason == "untested"


def test_existing_bucket_2_and_3_are_kept():
    recs = [
        student(bucket="Bucket 2", reason="x"),
        student(bucket="Bucket 3", reason="y"),
    ]
    out = finalize(recs)
    assert [r.bucket for r in out] == ["Bucket 2", "Bucket 3"]
    assert [r.bucket4_outcome for r in out] == [None, None]


def test_left_out_approaching_becomes_bucket_4_below_with_rank_reason():
    (r,) = finalize(
        [
            student(
                is_approaching=True,
                rank=9,
                reason="approaching, projected 400, rank 9 of 5 to move",
            )
        ]
    )
    assert (r.bucket, r.bucket4_outcome) == ("Bucket 4", "below")
    assert r.reason.startswith("approaching, projected 400, rank 9 of 5")
