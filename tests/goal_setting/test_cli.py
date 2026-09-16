"""End to end tests for the rollout CLI, against a fake warehouse client."""

import csv
import json
from pathlib import Path

from teamster.goal_setting.__main__ import main

from .fixtures.roster_small import student, untested

REPO = Path(__file__).resolve().parents[2]


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeClient:
    """Answers the three queries the rollout makes by matching a table name."""

    def __init__(self, roster_rows, target_rows, live_programs):
        self.roster_rows = roster_rows
        self.target_rows = target_rows
        self.live_programs = live_programs
        self.n_queries = 0

    def query(self, sql: str, job_config=None):
        self.n_queries += 1
        if "int_iready__diagnostic_results" in sql:
            return FakeResult(self.roster_rows)
        if "int_assessments__academic_goals" in sql:
            return FakeResult(self.target_rows)
        if "int_powerschool__spenrollments" in sql:
            return FakeResult(self.live_programs)
        raise AssertionError(f"unexpected query: {sql[:80]}")


def roster_rows():
    recs = (
        [student(projected_level=5, projected_score=430 + i) for i in range(3)]
        + [
            student(projected_level=4, projected_score=400 + i, stretch_level=4)
            for i in range(4)
        ]
        + [
            student(projected_level=3, projected_score=380, stretch_level=5),
            student(projected_level=2, projected_score=350, stretch_level=3),
        ]
        + [untested()]
    )
    return [
        dict(
            region=r.region,
            student_number=r.student_number,
            school=r.school,
            school_id=r.school_id,
            grade_level=r.grade_level,
            subject=r.subject,
            is_tested=r.is_tested,
            projected_level=r.projected_level,
            projected_score=r.projected_score,
            stretch_level=r.stretch_level,
        )
        for r in recs
    ]


def targets():
    return [
        {"region": r, "grade_level": g, "target": 0.5}
        for r in ("Newark", "Camden", "Paterson")
        for g in (1, 2)
    ]


def _live_matching_crosswalk():
    from teamster.goal_setting.config import load_crosswalk
    from teamster.goal_setting.verify_crosswalk import REGION_TO_PROJECT, expected_name

    xw = load_crosswalk(REPO / "config/goal_setting/ps_programs.yaml")
    return [
        {
            "project": REGION_TO_PROJECT[p.region],
            "programid": p.programid,
            "specprog_name": expected_name(p.subject, p.bucket),
        }
        for p in xw.programs
    ]


def _factory(rows, target_rows=None, live=None):
    """One client per call, but always over the SAME roster rows.

    Student numbers come from a module level counter in the fixture, so a
    second call to roster_rows() would renumber every student and make a
    replay or a diff meaningless.
    """

    return _Factory(rows, target_rows, live)


class _Factory:
    """Callable client factory that keeps every client it handed out."""

    def __init__(self, rows, target_rows, live):
        self._rows = rows
        self._target_rows = target_rows
        self._live = live
        self.clients: list[FakeClient] = []

    def __call__(self) -> FakeClient:
        client = FakeClient(
            self._rows,
            targets() if self._target_rows is None else self._target_rows,
            _live_matching_crosswalk() if self._live is None else self._live,
        )
        self.clients.append(client)
        return client


def _crosswalk_without(region: str, path: Path) -> Path:
    """Copy the committed crosswalk with one region's rows removed."""
    import yaml

    data = yaml.safe_load((REPO / "config/goal_setting/ps_programs.yaml").read_text())
    data["programs"] = [p for p in data["programs"] if p["region"] != region]
    path.write_text(yaml.safe_dump(data))
    return path


def run(argv, tmp_path, live=None):
    return main(argv, client_factory=_factory(roster_rows(), live=live))


def test_plan_mode_writes_no_files(tmp_path, capsys):
    out = tmp_path / "run"
    rc = run(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_1_2",
            "--out",
            str(out),
            "--plan",
            "--manifest-dir",
            str(tmp_path / "m"),
        ],
        tmp_path,
    )
    assert rc == 0
    assert not out.exists() or list(out.iterdir()) == []
    text = capsys.readouterr().out
    assert "TEAM" in text and "no prior run" in text


def test_rollout_writes_run_and_commits_manifest_copy(tmp_path):
    out = tmp_path / "run"
    manifests = tmp_path / "manifests"
    rc = main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_1_2",
            "--out",
            str(out),
            "--manifest-dir",
            str(manifests),
        ],
        client_factory=_factory(roster_rows()),
    )
    assert rc == 0
    assert (out / "inputs" / "iready_boy_nj_math_1_2.csv").exists()
    assert (out / "manifest.json").exists()
    committed = json.loads((manifests / "ay2026" / "nj_math_1_2.json").read_text())
    assert committed["inputs"][0]["row_count"] == 10
    assert committed["diff"]["verdict"] == "no prior run"


def test_replay_from_inputs_is_byte_identical(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    manifests = tmp_path / "manifests"
    factory = _factory(roster_rows())
    base = ["rollout", "--year", "2026", "--group", "nj_math_1_2"]
    assert (
        main(
            [*base, "--out", str(first), "--manifest-dir", str(manifests)],
            client_factory=factory,
        )
        == 0
    )
    assert (
        main(
            [
                *base,
                "--out",
                str(second),
                "--manifest-dir",
                str(manifests),
                "--input",
                str(first),
            ],
            client_factory=factory,
        )
        == 0
    )
    for name in ("school_goals.csv", "ps_programs.csv", "explain.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def _first_run_then_replay(tmp_path, replay_targets):
    """Run once against the sheet, then replay with a different sheet answer."""
    first, second, manifests = tmp_path / "first", tmp_path / "second", tmp_path / "m"
    rows = roster_rows()
    base = ["rollout", "--year", "2026", "--group", "nj_math_1_2"]
    assert (
        main(
            [*base, "--out", str(first), "--manifest-dir", str(manifests)],
            client_factory=_factory(rows),
        )
        == 0
    )
    committed = manifests / "ay2026" / "nj_math_1_2.json"
    before = committed.read_bytes()
    rc = main(
        [
            *base,
            "--out",
            str(second),
            "--manifest-dir",
            str(manifests),
            "--input",
            str(first),
        ],
        client_factory=_factory(rows, target_rows=replay_targets),
    )
    return rc, first, second, committed, before


def _moved_targets():
    return [
        {"region": r, "grade_level": g, "target": 0.9}
        for r in ("Newark", "Camden", "Paterson")
        for g in (1, 2)
    ]


def test_replay_uses_prior_targets_not_the_sheet(tmp_path):
    rc, first, second, _, _ = _first_run_then_replay(tmp_path, _moved_targets())
    assert rc == 0
    for name in ("school_goals.csv", "ps_programs.csv", "explain.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_replay_does_not_touch_committed_manifest(tmp_path, capsys):
    rc, _, second, committed, before = _first_run_then_replay(
        tmp_path, _moved_targets()
    )
    assert rc == 0
    assert committed.read_bytes() == before
    # the replay still produced its own run folder
    assert (second / "manifest.json").exists()
    assert "replay: committed manifest left unchanged" in capsys.readouterr().out


def test_replay_from_wrong_group_folder_is_a_clear_error(tmp_path, capsys):
    first, manifests = tmp_path / "first", tmp_path / "manifests"
    factory = _factory(roster_rows())
    main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_1_2",
            "--out",
            str(first),
            "--manifest-dir",
            str(manifests),
        ],
        client_factory=factory,
    )
    capsys.readouterr()
    rc = main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_k",
            "--out",
            str(tmp_path / "k"),
            "--manifest-dir",
            str(manifests),
            "--input",
            str(first),
            "--plan",
        ],
        client_factory=factory,
    )
    assert rc == 1 and "no input entry" in capsys.readouterr().err


def _k_group_targets():
    # grade 0 satisfies nj_math_k's own missing-target check; grade 1 is what
    # the FakeClient's fixed roster rows (all grade_level=1) actually need at
    # the school_goal step.
    return [
        {"region": r, "grade_level": g, "target": 0.5}
        for r in ("Newark", "Camden", "Paterson")
        for g in (0, 1)
    ]


def test_against_folder_from_another_group_is_a_clear_error(tmp_path, capsys):
    first, manifests = tmp_path / "first", tmp_path / "manifests"
    main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_1_2",
            "--out",
            str(first),
            "--manifest-dir",
            str(manifests),
        ],
        client_factory=_factory(roster_rows()),
    )
    capsys.readouterr()
    rc = main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_k",
            "--out",
            str(tmp_path / "k"),
            "--manifest-dir",
            str(manifests),
            "--against",
            str(first),
            "--plan",
        ],
        client_factory=_factory(roster_rows(), target_rows=_k_group_targets()),
    )
    err = capsys.readouterr().err
    assert rc == 1
    assert "nj_math_1_2" in err and "nj_math_k" in err


def test_second_run_diffs_against_committed_manifest(tmp_path, capsys):
    first, second, manifests = tmp_path / "a", tmp_path / "b", tmp_path / "m"
    factory = _factory(roster_rows())
    base = ["rollout", "--year", "2026", "--group", "nj_math_1_2"]
    main(
        [*base, "--out", str(first), "--manifest-dir", str(manifests)],
        client_factory=factory,
    )
    capsys.readouterr()
    rc = main(
        [
            *base,
            "--out",
            str(second),
            "--manifest-dir",
            str(manifests),
            "--against",
            str(first),
        ],
        client_factory=factory,
    )
    assert rc == 0
    assert "verdict: no change" in capsys.readouterr().out


def test_forced_prior_run_is_not_used_as_baseline(tmp_path, capsys):
    manifests = tmp_path / "m"
    prior = manifests / "ay2026" / "nj_math_1_2.json"
    prior.parent.mkdir(parents=True)
    prior.write_text(
        json.dumps(
            {
                "gate_overridden": True,
                "school_goals": [],
                "bucket_counts": [],
                # a truncated read: one school, two students
                "inputs": [
                    {
                        "file": "iready_boy_nj_math_1_2.csv",
                        "counts_by_school_grade": [
                            {
                                "region": "Newark",
                                "school": "TEAM",
                                "grade_level": 1,
                                "n": 2,
                            }
                        ],
                    }
                ],
            }
        )
    )
    out = tmp_path / "run"
    rc = main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_1_2",
            "--out",
            str(out),
            "--manifest-dir",
            str(manifests),
        ],
        client_factory=_factory(roster_rows()),
    )
    assert rc == 0
    printed = capsys.readouterr().out
    assert "was forced past the freshness gate" in printed
    assert "--baseline-date" in printed
    m = json.loads((out / "manifest.json").read_text())
    assert (
        "no baseline available; roster counts were not compared to a prior run"
        in m["gate_warnings"]
    )


def test_missing_against_prints_reclassification_warning(tmp_path, capsys):
    first, second, manifests = tmp_path / "a", tmp_path / "b", tmp_path / "m"
    factory = _factory(roster_rows())
    base = ["rollout", "--year", "2026", "--group", "nj_math_1_2"]
    main(
        [*base, "--out", str(first), "--manifest-dir", str(manifests)],
        client_factory=factory,
    )
    assert "reclassification was NOT checked" not in capsys.readouterr().out
    rc = main(
        [*base, "--out", str(second), "--manifest-dir", str(manifests)],
        client_factory=factory,
    )
    printed = capsys.readouterr().out
    assert rc == 0
    assert "student-level reclassification was NOT checked" in printed
    assert printed.index("NOT checked") < printed.index("region | school | gr |")


def test_reclassification_exits_nonzero_without_flag(tmp_path, capsys):
    first, second, manifests = tmp_path / "a", tmp_path / "b", tmp_path / "m"
    rows = roster_rows()
    base = ["rollout", "--year", "2026", "--group", "nj_math_1_2"]
    main(
        [*base, "--out", str(first), "--manifest-dir", str(manifests)],
        client_factory=_factory(rows),
    )
    # add a new top approaching student: tested 10, bp = (5 - 3) / 5 = 0.4,
    # n_to_move = 2, so Bucket 2 becomes {404, 403} and 402 moves to Bucket 3
    newcomer = student(projected_level=4, projected_score=404.0, stretch_level=4)
    changed = rows + [
        dict(
            region=newcomer.region,
            student_number=newcomer.student_number,
            school=newcomer.school,
            school_id=newcomer.school_id,
            grade_level=newcomer.grade_level,
            subject=newcomer.subject,
            is_tested=True,
            projected_level=4,
            projected_score=404.0,
            stretch_level=4,
        )
    ]
    rc = main(
        [
            *base,
            "--out",
            str(second),
            "--manifest-dir",
            str(manifests),
            "--against",
            str(first),
        ],
        client_factory=_factory(changed),
    )
    out = capsys.readouterr().out
    assert rc == 2 and "RECLASSIFIES" in out
    assert not (second / "manifest.json").exists()


def test_missing_targets_is_a_clear_error(tmp_path, capsys):
    rc = main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_1_2",
            "--out",
            str(tmp_path / "r"),
            "--plan",
        ],
        client_factory=_factory(roster_rows(), target_rows=[]),
    )
    assert rc == 1 and "Camden grade 1" in capsys.readouterr().err


def test_crosswalk_problem_aborts_rollout(tmp_path, capsys):
    live = _live_matching_crosswalk()[1:]
    rc = main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_1_2",
            "--out",
            str(tmp_path / "r"),
            "--plan",
        ],
        client_factory=_factory(roster_rows(), live=live),
    )
    assert rc == 1 and "not found in PowerSchool" in capsys.readouterr().err


def test_group_region_without_crosswalk_rows_aborts_before_querying(tmp_path, capsys):
    xw = _crosswalk_without("Paterson", tmp_path / "ps_programs.yaml")
    factory = _factory(roster_rows())
    rc = main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_1_2",
            "--out",
            str(tmp_path / "r"),
            "--crosswalk",
            str(xw),
            "--plan",
        ],
        client_factory=factory,
    )
    err = capsys.readouterr().err
    assert rc == 1
    assert "Paterson Math Bucket 1" in err and "Paterson Math Bucket 3" in err
    assert sum(c.n_queries for c in factory.clients) == 0


def test_show_replays_a_student(tmp_path, capsys):
    out = tmp_path / "run"
    main(
        [
            "rollout",
            "--year",
            "2026",
            "--group",
            "nj_math_1_2",
            "--out",
            str(out),
            "--manifest-dir",
            str(tmp_path / "m"),
        ],
        client_factory=_factory(roster_rows()),
    )
    sn = list(csv.DictReader((out / "explain.csv").open()))[0]["student_number"]
    capsys.readouterr()
    assert main(["show", "--run", str(out), "--student", sn]) == 0
    assert "because" in capsys.readouterr().out
