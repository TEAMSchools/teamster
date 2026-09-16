import csv

from teamster.goal_setting.show import explain

FIELDS = ["student_number", "region", "subject", "bucket", "reason"]


def _write(run_dir, rows):
    path = run_dir / "explain.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_show_explain_survives_a_malformed_row(tmp_path):
    _write(
        tmp_path,
        [
            {
                "student_number": "",
                "region": "Newark",
                "subject": "Math",
                "bucket": "Bucket 2",
                "reason": "malformed row",
            },
            {
                "student_number": "12345",
                "region": "Newark",
                "subject": "Math",
                "bucket": "Bucket 3",
                "reason": "top approaching",
            },
        ],
    )
    lines = explain(tmp_path, 12345)
    assert lines == ["Newark Math: Bucket 3 because top approaching"]
