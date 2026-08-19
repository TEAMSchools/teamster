"""MkDocs hooks.

Two jobs: hide the nav on the homepage, and generate the staff launch
page from the catalog in `launch/`.

The generated page is registered with `File.generated` rather than
written into `docs_dir`. Writing there during a build makes the dev
server re-detect its own write and rebuild about twice a second forever.
"""

import importlib
import sys
from pathlib import Path

from mkdocs.structure.files import File

# `launch` is a PEP 420 namespace package under docs/. Anchored on
# __file__ rather than cwd, because `mkdocs build -f <path>` is supported.
_DOCS_DIR = str(Path(__file__).resolve().parent)


def on_page_markdown(markdown, page, config, files):
    if page.file.src_path == "README.md":
        page.meta["hide"] = ["navigation", "toc"]
    return markdown


def on_files(files, config):
    # Insert here, not at module level: mkdocs.config.config_options.Hooks
    # loads this file via exec_module with docs/ temporarily on sys.path,
    # then restores the ORIGINAL sys.path in a `finally` clause the moment
    # loading finishes -- wiping out a module-level insert before on_files
    # ever runs. Doing it per-call survives, since nothing unwinds sys.path
    # between calls. The guard keeps sys.path from growing every rebuild
    # under mkdocs serve.
    if _DOCS_DIR not in sys.path:
        sys.path.insert(0, _DOCS_DIR)

    # Reload when already imported: the dev server is a long-running
    # process, so an edit to build.py would otherwise be invisible until
    # restart. load() re-reads the YAML every call, so catalog edits are
    # picked up regardless.
    if "launch.build" in sys.modules:
        launch_build = importlib.reload(sys.modules["launch.build"])
    else:
        # trunk-ignore(pyright/reportAttributeAccessIssue): sys.path.insert above puts docs/ on the path at runtime
        from launch import build as launch_build

    html = launch_build.build()
    if html is None:
        return files

    # docs/launch/README.md is a deliberately published page (see mkdocs.yml
    # exclude_docs, which excludes the catalog's other source files but not
    # this one), but MkDocs maps a `README.md` stem to `index.html` the same
    # way it does `index.md` -- so it independently targets this exact
    # destination too. Files.append() only dedupes by src_uri (ours is
    # "launch/index.html"; README's own src_uri is "launch/README.md"), so
    # the clash is otherwise silent: whichever gets WRITTEN last wins on
    # disk, and it was winning. Evict it first so the generated catalog
    # always owns this destination.
    readme = files.get_file_from_path("launch/README.md")
    if readme is not None:
        files.remove(readme)

    files.append(File.generated(config, "launch/index.html", content=html))
    return files
