from pathlib import Path

# trunk-ignore(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
import publish_article
import pytest
import yaml

# trunk-ignore(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from publish_article import (
    DEFAULT_PERMISSION_GROUP,
    DEFAULT_USER_SEGMENT,
    PublishError,
    check_workdir,
    load_article,
    save_html,
    save_state,
)


def write_article(tmp_path: Path, meta: dict, html: str = "<p>hi</p>") -> Path:
    (tmp_path / "article.yml").write_text(yaml.safe_dump(meta))
    (tmp_path / "article.html").write_text(html)
    return tmp_path


def test_load_applies_visibility_defaults(tmp_path):
    d = write_article(tmp_path, {"title": "T", "section_id": 1, "author_id": 2})
    a = load_article(d)
    assert a.user_segment == DEFAULT_USER_SEGMENT
    assert a.permission_group == DEFAULT_PERMISSION_GROUP
    assert a.labels == []
    assert a.article_id is None
    assert a.html == "<p>hi</p>"


def test_load_refuses_without_author_id(tmp_path):
    d = write_article(tmp_path, {"title": "T", "section_id": 1})
    with pytest.raises(PublishError, match="author_id"):
        load_article(d)


def test_load_refuses_without_section_id(tmp_path):
    d = write_article(tmp_path, {"title": "T", "author_id": 2})
    with pytest.raises(PublishError, match="section_id"):
        load_article(d)


def test_load_refuses_without_html(tmp_path):
    (tmp_path / "article.yml").write_text(
        yaml.safe_dump({"title": "T", "section_id": 1, "author_id": 2})
    )
    with pytest.raises(PublishError, match="article.html"):
        load_article(tmp_path)


def test_save_state_round_trips_and_keeps_user_fields(tmp_path):
    d = write_article(
        tmp_path,
        {"title": "T", "section_id": 1, "author_id": 2, "labels": ["x"]},
    )
    a = load_article(d)
    a.article_id = 99
    a.last_known_updated_at = "2026-09-29T00:00:00Z"
    save_state(a)
    raw = yaml.safe_load((d / "article.yml").read_text())
    assert raw["labels"] == ["x"]
    assert raw["article_id"] == 99
    assert raw["last_known_updated_at"] == "2026-09-29T00:00:00Z"
    assert "attachments" not in raw
    again = load_article(d)
    assert again.article_id == 99


def test_save_html_writes_the_body(tmp_path):
    d = write_article(tmp_path, {"title": "T", "section_id": 1, "author_id": 2})
    a = load_article(d)
    a.html = "<p>changed</p>"
    save_html(a)
    assert (d / "article.html").read_text() == "<p>changed</p>"


def test_repo_root_is_the_checkout():
    root = publish_article.REPO_ROOT
    assert (root / "pyproject.toml").is_file()
    assert (root / ".claude" / "skills" / "zendesk-help-articles").is_dir()


def test_check_workdir_refuses_a_folder_inside_the_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_article, "REPO_ROOT", tmp_path.resolve())
    with pytest.raises(PublishError, match="inside the checkout"):
        check_workdir(tmp_path / "zendesk" / "42")


def test_check_workdir_resolves_dotdot_before_comparing(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    monkeypatch.setattr(publish_article, "REPO_ROOT", repo.resolve())
    with pytest.raises(PublishError, match="inside the checkout"):
        check_workdir(outside / ".." / "repo" / "zendesk")
    check_workdir(outside / "zendesk")


def test_check_workdir_refuses_the_main_checkout_from_a_worktree(tmp_path, monkeypatch):
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    worktree = main / ".claude" / "worktrees" / "branch"
    worktree.mkdir(parents=True)
    monkeypatch.setattr(publish_article, "REPO_ROOT", worktree.resolve())
    with pytest.raises(PublishError, match="inside the checkout"):
        check_workdir(main / "docs" / "article")
    check_workdir(tmp_path / "scratch")
