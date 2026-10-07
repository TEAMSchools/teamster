"""The hook is thin, so this checks wiring rather than behaviour."""

import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"


def load_hooks():
    sys.path.insert(0, str(DOCS))
    import hooks

    return hooks


def test_hooks_exposes_on_files():
    # trunk-ignore(pyright/reportAttributeAccessIssue): hooks is imported dynamically at runtime
    assert callable(load_hooks().on_files)


def test_hooks_still_hides_nav_on_the_homepage():
    # trunk-ignore(pyright/reportAttributeAccessIssue): hooks is imported dynamically at runtime
    assert callable(load_hooks().on_page_markdown)


def test_generated_page_lands_in_the_file_set():
    from mkdocs.config.defaults import MkDocsConfig

    config = MkDocsConfig()
    config.load_dict({"site_name": "t", "docs_dir": str(DOCS)})
    assert config.validate()[0] == []

    # A real `mkdocs build` always runs an earlier plugin event (on_startup)
    # before on_files, and mkdocs.plugins.PluginCollection.run_event sets
    # this attribute as a side effect of running ANY event, even with zero
    # plugins registered for it. Calling on_files() directly here skips that
    # earlier event, so File.generated()'s `config.plugins._current_plugin`
    # read raises AttributeError on mkdocs 1.6.1 (the version uv.lock pins)
    # unless it is primed first, exactly as a real build would have done by
    # this point.
    # trunk-ignore(pyright/reportAttributeAccessIssue): plugins exists on the real MkDocsConfig, just not the base Config stub
    config.plugins._current_plugin = None

    from mkdocs.structure.files import Files

    # Sibling test files in this directory import `launch.build` directly
    # (`from launch.build import Catalog`, etc.) at collection time, so it is
    # already in sys.modules by the time this test runs. hooks.on_files()
    # then takes its importlib.reload branch -- correct behaviour for
    # mkdocs serve, a long-running process where that is the only way to see
    # a build.py edit without a restart. But reload() mutates the shared
    # module object's classes in place, which would silently invalidate the
    # Catalog/CatalogError references those sibling files already bound at
    # collection time. That collision is specific to running the whole
    # directory's tests in one process; in real usage the hook is the only
    # importer of launch.build, so there is nothing else to invalidate.
    # Snapshot and restore the module dict so this test stays isolated.
    build_module = sys.modules.get("launch.build")
    snapshot = dict(build_module.__dict__) if build_module is not None else None

    # trunk-ignore(pyright/reportAttributeAccessIssue): hooks is imported dynamically at runtime
    files = load_hooks().on_files(Files([]), config)
    assert any(f.src_uri == "launch/index.html" for f in files)

    if snapshot is not None:
        sys.modules["launch.build"].__dict__.clear()
        sys.modules["launch.build"].__dict__.update(snapshot)
