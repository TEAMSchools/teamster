from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SKILL_SCRIPTS = (
    Path(__file__).resolve().parents[2] / ".claude/skills/model-support/scripts"
)


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SKILL_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SOURCE = """---
name: demo
---

# Demo

Intro line.

## Goals

Goal text.

```sql
## not a heading (backtick fence)
```

### Sub of goals

~~~text
## not a heading (tilde fence)
~~~

## Gotchas

````markdown
```
## still not a heading (nested fence)
```
````

Last line.
"""


def test_split_routes_sections_and_keeps_fenced_hashes():
    split = _load("split_skill")
    out = split.split_sections(
        SOURCE,
        {"Goals": "references/goals.md", "Gotchas": "references/gotchas.md"},
        default="SKILL.md",
    )
    assert "Intro line.\n" in out["SKILL.md"]
    goals = "".join(out["references/goals.md"])
    assert "## not a heading (backtick fence)" in goals
    assert "## not a heading (tilde fence)" in goals
    assert "### Sub of goals" in goals
    gotchas = "".join(out["references/gotchas.md"])
    assert "## still not a heading (nested fence)" in gotchas
    assert "Last line." in gotchas


def test_split_accounts_for_every_line():
    split = _load("split_skill")
    out = split.split_sections(
        SOURCE,
        {"Goals": "references/goals.md", "Gotchas": "references/gotchas.md"},
        default="SKILL.md",
    )
    assert sum(len(v) for v in out.values()) == len(SOURCE.splitlines(keepends=True))


def test_split_rejects_unmapped_heading():
    split = _load("split_skill")
    with pytest.raises(KeyError, match="Gotchas"):
        split.split_sections(SOURCE, {"Goals": "g.md"}, default="SKILL.md")


def test_check_links_reports_only_broken_relative_links(tmp_path):
    links = _load("check_links")
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "goals.md").write_text("# Goals\n")
    (tmp_path / "SKILL.md").write_text(
        "[ok](references/goals.md)\n"
        "[ok anchor](references/goals.md#goals)\n"
        "[web](https://example.com/x)\n"
        "[self](#top)\n"
        "[broken](references/missing.md)\n"
        "```text\n[in fence](nowhere.md)\n```\n"
    )
    broken = links.find_broken_links([tmp_path])
    assert broken == [(tmp_path / "SKILL.md", 5, "references/missing.md")]


def test_check_links_titled_and_angle_bracket_links(tmp_path):
    links = _load("check_links")
    (tmp_path / "has space.md").write_text("# x\n")
    (tmp_path / "SKILL.md").write_text(
        '[titled ok](has%20space.md "Title")\n'
        "[angle ok](<has space.md>)\n"
        '[titled broken](missing.md "Title")\n'
        "[angle broken](<no such.md>)\n"
    )
    broken = links.find_broken_links([tmp_path])
    assert broken == [
        (tmp_path / "SKILL.md", 3, "missing.md"),
        (tmp_path / "SKILL.md", 4, "no such.md"),
    ]


def test_check_links_skips_inline_and_indented_code(tmp_path):
    links = _load("check_links")
    (tmp_path / "SKILL.md").write_text(
        "Use `[x](inline.md)` syntax.\n"
        "\n"
        "    [x](indented-code.md)\n"
        "\n"
        "1. A list item\n"
        "\n"
        "    [in list](list-broken.md)\n"
    )
    broken = links.find_broken_links([tmp_path])
    assert broken == [(tmp_path / "SKILL.md", 7, "list-broken.md")]


def test_bigquery_hash_comments_are_stripped():
    diff = _load("comment_only_diff")
    old = "select a, # old note\n    '#' as h\nfrom t\n"
    new = "select a,\n    '#' as h # new note\nfrom t\n"
    assert diff.is_comment_only(old, new)
    assert not diff.is_comment_only(old, "select a, '##' as h from t")


def test_comment_only_edit_is_detected():
    diff = _load("comment_only_diff")
    old = "select a, -- old note\n    b\nfrom t /* block */\n{# jinja note #}\n"
    new = "select a,\n    b -- new note\nfrom t\n"
    assert diff.is_comment_only(old, new)


def test_logic_edit_is_detected():
    diff = _load("comment_only_diff")
    assert not diff.is_comment_only("select a from t", "select b from t")


def test_dashes_inside_strings_are_not_comments():
    diff = _load("comment_only_diff")
    old = "select '--' as sep, \"a -- b\" as label from t"
    new = "select '-' as sep, \"a -- b\" as label from t"
    assert "'--'" in diff.strip_comments(old)
    assert not diff.is_comment_only(old, new)


def test_split_rejects_unclosed_fence():
    split = _load("split_skill")
    with pytest.raises(ValueError, match="unclosed fence"):
        split.split_sections("## A\n```\n## B\n", {"A": "a.md"}, default="S.md")


def test_split_rejects_unused_mapping_key():
    split = _load("split_skill")
    with pytest.raises(KeyError, match="Missing"):
        split.split_sections("## A\n", {"A": "a.md", "Missing": "m.md"}, "S.md")


def test_split_main_recounts_from_disk(tmp_path):
    split = _load("split_skill")
    source = tmp_path / "SKILL.md"
    source.write_text("intro\n## A\na\n## B\nb\n")
    mapping = tmp_path / "map.json"
    mapping.write_text('{"A": "references/x.md", "B": "./references/x.md"}')
    out = tmp_path / "out"
    assert split.main(["split_skill.py", str(source), str(mapping), str(out)]) == 1


def test_check_links_mixed_and_nested_fences(tmp_path):
    links = _load("check_links")
    (tmp_path / "SKILL.md").write_text(
        "```markdown\n~~~\n[in fence](a.md)\n~~~\n```\n"
        "````text\n```\n[in fence](b.md)\n```\n````\n"
        "[broken](c.md)\n"
    )
    broken = links.find_broken_links([tmp_path])
    assert broken == [(tmp_path / "SKILL.md", 11, "c.md")]


def test_whitespace_inside_strings_is_logic():
    diff = _load("comment_only_diff")
    assert not diff.is_comment_only("select 'a  b' from t", "select 'a b' from t")


def test_triple_quoted_string_is_one_literal():
    diff = _load("comment_only_diff")
    old = "select '''it's -- x''' as s from t"
    new = "select '''it's -- y''' as s from t"
    assert not diff.is_comment_only(old, new)


YAML_OLD = """version: 2
models:
  - name: m
    description: Old words.
    columns:
      - name: k
        description: Key.
        data_tests:
          - not_null
      - name: s
        data_tests:
          - accepted_values:
              arguments:
                values: [a, b]
"""


def test_yaml_description_edit_is_clean():
    ydiff = _load("yaml_description_diff")
    new = YAML_OLD.replace("Old words.", "New words.").replace("Key.", "The key.")
    assert ydiff.non_description_changes(YAML_OLD, new) == []


def test_yaml_dropped_test_is_flagged():
    ydiff = _load("yaml_description_diff")
    new = YAML_OLD.replace("        data_tests:\n          - not_null\n", "")
    assert ydiff.non_description_changes(YAML_OLD, new)


def test_yaml_trimmed_accepted_values_is_flagged():
    ydiff = _load("yaml_description_diff")
    new = YAML_OLD.replace("values: [a, b]", "values: [a]")
    assert ydiff.non_description_changes(YAML_OLD, new)


def test_split_keeps_heading_inside_indented_fence():
    split = _load("split_skill")
    text = (
        "## Steps\n"
        "1. Run this:\n"
        "\n"
        "   ```bash\n"
        "## not a heading (fence indented under a list item)\n"
        "   ```\n"
        "\n"
        "## Next\n"
    )
    out = split.split_sections(
        text, {"Steps": "steps.md", "Next": "next.md"}, default="S.md"
    )
    assert "## not a heading (fence indented under a list item)\n" in out["steps.md"]
    assert out["next.md"] == ["## Next\n"]


WORKBOOK = """<?xml version='1.0' encoding='utf-8' ?>
<workbook>
  <datasources>
    <datasource caption='ds' name='federated.x'>
      <column caption='Used' name='[Calculation_1]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='[Calculation_2] + 1' />
      </column>
      <column caption='Read By Used' name='[Calculation_2]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='SUM([x])' />
      </column>
      <column caption='Dead Top' name='[Calculation_3]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='[Calculation_4] * 2' />
      </column>
      <column caption='Dead Base' name='[Calculation_4]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='SUM([y])' />
      </column>
      <column caption='Windows Only' name='[Calculation_5]' role='dimension' type='nominal'>
        <calculation class='tableau' formula='[z]' />
      </column>
      <column caption='Leftover Instance' name='[Calculation_6]' role='dimension' type='nominal'>
        <calculation class='tableau' formula='[z]' />
      </column>
      <column caption='Kept Copy' name='[Dead Base (copy)_7]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='SUM([y])' />
      </column>
      <column-instance column='[Calculation_6]' derivation='None' name='[none:Calculation_6:nk]' />
      <style><style-rule element='mark'><encoding attr='color' field='[none:Calculation_6:nk]' /></style-rule></style>
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Sheet'>
      <table><rows>[federated.x].[sum:Calculation_1:qk]</rows>
      <cols>[federated.x].[usr:Dead Base (copy)_7:qk]</cols></table>
    </worksheet>
  </worksheets>
  <windows>
    <window class='worksheet' name='Hidden'>[federated.x].[none:Calculation_5:nk]</window>
  </windows>
</workbook>
"""


def _unused(tmp_path):
    mod = _load("tableau_unused_calcs")
    twb = tmp_path / "wb.twb"
    twb.write_text(WORKBOOK)
    calcs, order, lookalikes, _ = mod.analyse(mod.load_root(str(twb)))
    return [calcs[k]["caption"] for k in order], lookalikes


def test_tableau_calc_read_by_a_used_calc_is_kept(tmp_path):
    order, _ = _unused(tmp_path)
    assert "Used" not in order and "Read By Used" not in order


def test_tableau_windows_and_leftover_instances_do_not_count(tmp_path):
    order, _ = _unused(tmp_path)
    assert "Windows Only" in order and "Leftover Instance" in order


def test_tableau_delete_order_puts_readers_first(tmp_path):
    order, _ = _unused(tmp_path)
    assert order.index("Dead Top") < order.index("Dead Base")


def test_tableau_kept_copy_is_flagged(tmp_path):
    order, lookalikes = _unused(tmp_path)
    assert "Kept Copy" not in order
    assert lookalikes == ["Dead Base (copy)_7"]
