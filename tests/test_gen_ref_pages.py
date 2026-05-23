"""Tests for ``docs/gen_ref_pages.py``.

These tests execute the script with a stubbed ``mkdocs_gen_files`` module so
we can assert which virtual pages would be written during ``mkdocs build``.
The key guarantees verified here address the regression reported in
issue #351 — the API reference must surface nested sub-packages such as
``deux.runtime.hid`` and the CLI modules under ``deux.tools``.
"""

from __future__ import annotations

import runpy
import sys
import types
from collections.abc import Iterator
from io import StringIO
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "docs" / "gen_ref_pages.py"


class _FakeGenFiles:
    """Stand-in for the ``mkdocs_gen_files`` module used during tests.

    Captures every virtual file written by the script so tests can assert on
    the generated reference layout without touching the real filesystem.
    """

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.edit_paths: dict[str, str] = {}
        self._buffers: dict[str, StringIO] = {}

    def open(self, path: str, mode: str) -> StringIO:  # noqa: A003 - mimic real API
        assert mode == "w", "script should only write files"
        buf = _RecordingBuffer(self, path)
        self._buffers[path] = buf
        return buf

    def set_edit_path(self, doc_path: str, edit_path: str) -> None:
        self.edit_paths[doc_path] = edit_path


class _RecordingBuffer(StringIO):
    """``StringIO`` subclass that flushes its contents on context exit."""

    def __init__(self, parent: _FakeGenFiles, path: str) -> None:
        super().__init__()
        self._parent = parent
        self._path = path

    def __enter__(self) -> _RecordingBuffer:
        return self

    def __exit__(self, *exc: object) -> None:
        self._parent.files[self._path] = self.getvalue()


@pytest.fixture
def run_script(monkeypatch: pytest.MonkeyPatch) -> Iterator[_FakeGenFiles]:
    """Execute ``gen_ref_pages.py`` with a stubbed ``mkdocs_gen_files``.

    The script resolves ``src/deux`` relative to the current working
    directory, so the fixture also ``chdir``-s into the repo root.
    """
    fake = _FakeGenFiles()
    fake_module = types.ModuleType("mkdocs_gen_files")
    fake_module.open = fake.open  # type: ignore[attr-defined]
    fake_module.set_edit_path = fake.set_edit_path  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mkdocs_gen_files", fake_module)
    monkeypatch.chdir(REPO_ROOT)
    runpy.run_path(str(SCRIPT), run_name="__main__")
    yield fake


def test_emits_top_level_subpackages(run_script: _FakeGenFiles) -> None:
    """Top-level sub-packages keep getting their own reference page."""
    for name in ("runtime", "ui", "dui", "render", "tools"):
        assert f"reference/{name}.md" in run_script.files
        assert f"::: deux.{name}\n" in run_script.files[f"reference/{name}.md"]


def test_emits_nested_runtime_hid_page(run_script: _FakeGenFiles) -> None:
    """The nested ``runtime.hid`` package must be rendered (issue #351)."""
    page = "reference/runtime/hid.md"
    assert page in run_script.files
    assert "::: deux.runtime.hid\n" in run_script.files[page]
    assert run_script.edit_paths[page].endswith("src/deux/runtime/hid/__init__.py")


@pytest.mark.parametrize("module", ["verify", "preview", "splash"])
def test_emits_tools_cli_module_pages(run_script: _FakeGenFiles, module: str) -> None:
    """CLI modules under ``deux.tools`` must each have a reference page."""
    page = f"reference/tools/{module}.md"
    assert page in run_script.files
    assert f"::: deux.tools.{module}\n" in run_script.files[page]
    assert run_script.edit_paths[page].endswith(f"src/deux/tools/{module}.py")


def test_summary_is_hierarchical(run_script: _FakeGenFiles) -> None:
    """``SUMMARY.md`` must nest child entries beneath their parent package."""
    summary = run_script.files["reference/SUMMARY.md"]
    lines = summary.splitlines()

    # Top-level entries have no indentation.
    assert "- [Tools](tools.md)" in lines
    assert "- [Runtime](runtime.md)" in lines

    # Nested entries are indented two spaces per level so Python-markdown
    # treats them as a sub-list rather than parent paragraph continuation.
    assert "  - [Hid](runtime/hid.md)" in lines
    assert "  - [Verify](tools/verify.md)" in lines
    assert "  - [Preview](tools/preview.md)" in lines
    assert "  - [Splash](tools/splash.md)" in lines


def test_skips_private_modules(run_script: _FakeGenFiles) -> None:
    """Modules and packages starting with ``_`` must not appear."""
    for path in run_script.files:
        # Strip the leading ``reference/`` prefix and trailing ``.md``.
        stem = path[len("reference/") :].removesuffix(".md")
        for segment in stem.split("/"):
            assert not segment.startswith("_"), f"private segment leaked: {path}"


def test_suppresses_reexported_submodule_pages(run_script: _FakeGenFiles) -> None:
    """Submodules re-exported by their parent ``__init__`` get no page.

    Emitting them anyway produces duplicate mkdocstrings anchors for the
    same symbol (e.g. ``deux.dui.resolve_dui`` available on both
    ``reference/dui/`` and ``reference/dui/repository/``), which trips
    ``mkdocs --strict`` autoref warnings and fails the docs build.
    """
    # ``src/deux/dui/__init__.py`` re-exports from ``.repository``,
    # ``.card``, ``.key``, ``.loader``, ``.schema`` etc., so none of those
    # should produce a standalone page.
    for reexported in ("repository", "card", "key", "loader", "schema"):
        assert f"reference/dui/{reexported}.md" not in run_script.files

    # ``src/deux/render/__init__.py`` re-exports from ``.theme`` and
    # ``.metrics`` among others.
    for reexported in ("theme", "metrics", "context"):
        assert f"reference/render/{reexported}.md" not in run_script.files


def test_top_level_packages_emitted_even_when_root_reexports(
    run_script: _FakeGenFiles,
) -> None:
    """``src/deux/__init__.py`` re-exports from every top-level sub-package.

    The script must still emit landing pages for them — otherwise the
    re-export filter would erase the entire pre-existing API reference.
    """
    for name in ("runtime", "ui", "dui", "render"):
        assert f"reference/{name}.md" in run_script.files
