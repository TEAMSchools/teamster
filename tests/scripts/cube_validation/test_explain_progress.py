from cube_validation import explain_progress

FPS = {"cube": "1", "dashboard": "2"}


def test_a_key_ignores_the_order_of_open_keys():
    assert explain_progress.key(
        "p", "c", "cube_only", FPS, ["a", "b"]
    ) == explain_progress.key("p", "c", "cube_only", FPS, ["b", "a"])


def test_a_key_changes_with_each_of_its_parts():
    base = explain_progress.key("p", "c", "cube_only", FPS, ["a"])

    assert {
        explain_progress.key("q", "c", "cube_only", FPS, ["a"]),
        explain_progress.key("p", "d", "cube_only", FPS, ["a"]),
        explain_progress.key("p", "c", "dashboard_only", FPS, ["a"]),
        explain_progress.key("p", "c", "cube_only", {**FPS, "cube": "9"}, ["a"]),
        explain_progress.key("p", "c", "cube_only", FPS, ["a", "b"]),
    }.isdisjoint({base})


def test_saved_outcomes_load_back(tmp_path):
    explain_progress.save(tmp_path, "k1", {"found": {}, "students": []})
    explain_progress.save(
        tmp_path, "k2", {"found": {"g": {"n_rows": 1}}, "students": []}
    )

    assert explain_progress.load(tmp_path) == {
        "k1": {"found": {}, "students": []},
        "k2": {"found": {"g": {"n_rows": 1}}, "students": []},
    }


def test_nothing_saved_loads_empty(tmp_path):
    assert explain_progress.load(tmp_path) == {}
