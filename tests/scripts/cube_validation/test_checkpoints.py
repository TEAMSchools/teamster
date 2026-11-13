from datetime import datetime, timedelta, timezone

import pytest
from cube_validation import checkpoints, report
from cube_validation.moment import Build

END = datetime(2026, 10, 28, 21, 35, tzinfo=timezone.utc)
BUILD = Build(END - timedelta(minutes=1), END, "job")
T0 = datetime(2026, 10, 29, 9, 0, tzinfo=timezone.utc)


def _folder(tmp_path, build=BUILD):
    folder = report.run_dir(tmp_path, "v", build)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def test_the_run_folder_is_the_one_save_local_writes(tmp_path):
    assert report.run_dir(tmp_path, "v", BUILD) == tmp_path / "v" / "2026-10-28T213500Z"


def test_a_checkpoint_round_trips_and_replaces_its_earlier_copy(tmp_path):
    folder = _folder(tmp_path)

    checkpoints.write(folder, "ada-region", "a", {"cells": [1]}, T0)
    checkpoints.write(folder, "ada-region", "b", {"cells": [2]}, T0)

    assert checkpoints.read_all(folder) == {"ada-region": ("b", {"cells": [2]})}
    assert len(list((folder / checkpoints.DIR).iterdir())) == 1


def test_an_unreadable_checkpoint_is_skipped_and_named(tmp_path, capsys):
    folder = _folder(tmp_path)
    checkpoints.write(folder, "ada-region", "a", {}, T0)
    (folder / checkpoints.DIR / "broken.json").write_text("{not json")

    assert set(checkpoints.read_all(folder)) == {"ada-region"}
    assert "broken.json" in capsys.readouterr().out


def test_an_unfinished_folder_is_found_by_its_latest_checkpoint(tmp_path):
    done = _folder(tmp_path, Build(BUILD.start, END - timedelta(days=1), "j0"))
    checkpoints.start(done, Build(BUILD.start, END - timedelta(days=1), "j0"), "p0")
    checkpoints.write(done, "c", "f", {}, T0 + timedelta(hours=5))
    checkpoints.finish(done)
    folder = _folder(tmp_path)
    checkpoints.start(folder, BUILD, "p1")
    checkpoints.write(folder, "a", "f", {}, T0)
    checkpoints.write(folder, "b", "f", {}, T0 + timedelta(hours=1))

    got = checkpoints.find_unfinished(tmp_path, "v")

    assert got == checkpoints.Unfinished(
        folder=folder, moment=BUILD, last_at=T0 + timedelta(hours=1), done=2
    )


def test_a_started_folder_without_a_checkpoint_is_not_unfinished(tmp_path):
    checkpoints.start(_folder(tmp_path), BUILD, "p1")

    assert checkpoints.find_unfinished(tmp_path, "v") is None


def test_spend_adds_up_across_processes(tmp_path):
    folder = _folder(tmp_path)
    checkpoints.start(folder, BUILD, "p1")
    checkpoints.record_spend(folder, "p1", 0.4)
    checkpoints.start(folder, BUILD, "p2")
    checkpoints.record_spend(folder, "p2", 0.3)

    assert checkpoints.total_spend(folder) == pytest.approx(0.7)


def test_clear_keeps_the_finished_results(tmp_path):
    folder = _folder(tmp_path)
    checkpoints.start(folder, BUILD, "p1")
    checkpoints.write(folder, "a", "f", {}, T0)
    for name in ("run.json", "triage.json", "triage-progress.json"):
        (folder / name).write_text("{}")

    checkpoints.clear(folder)

    assert sorted(p.name for p in folder.iterdir()) == ["run.json", "triage.json"]
