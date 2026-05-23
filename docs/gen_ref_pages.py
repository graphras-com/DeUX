"""Auto-generate API reference pages for mkdocstrings.

This script is executed by the mkdocs-gen-files plugin during ``mkdocs build``.
It walks the ``src/deux`` package tree and creates a virtual
``reference/<path>.md`` page for every public sub-package, and additionally
emits dedicated pages for nested sub-packages and modules **only when the
parent ``__init__.py`` does not already re-export them**. Each page contains
the appropriate ``::: deux.<dotted.path>`` directive so that *mkdocstrings*
renders the API docs from docstrings automatically.

A ``reference/SUMMARY.md`` file is also generated so that *mkdocs-literate-nav*
can build a hierarchical sidebar without manual ``nav:`` entries.

Why conditional recursion?
--------------------------
The previous implementation only walked the top-level sub-packages of
``src/deux`` and relied on each ``__init__.py`` re-exporting everything of
interest. That left several user-facing surfaces invisible in the rendered
reference (notably ``deux.runtime.hid`` and the CLI modules under
``deux.tools``, whose ``__init__.py`` is a stub).

Naively emitting a page for every nested module would instead produce
duplicate mkdocstrings anchors for symbols already documented on the parent
package page (e.g. ``deux.dui.resolve_dui`` re-exported from
``deux.dui.repository``). Those duplicates trip ``mkdocs --strict`` autoref
warnings. The recursion therefore descends only into child modules whose
symbols are *not* re-exported by their parent ``__init__.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import mkdocs_gen_files

SRC = Path("src")
PACKAGE = "deux"

# Matches ``from .<child>`` and ``from .<child>.<...>`` imports in an
# ``__init__.py``. The capture group yields the immediate child name.
_REEXPORT_RE = re.compile(r"^\s*from\s+\.([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)


def _reexported_children(init_path: Path) -> frozenset[str]:
    """Return the set of immediate children re-exported by an ``__init__.py``.

    A child ``foo`` is considered re-exported when the parent ``__init__``
    contains ``from .foo import ...`` or ``from .foo.bar import ...``.
    """
    if not init_path.is_file():
        return frozenset()
    text = init_path.read_text(encoding="utf-8")
    return frozenset(_REEXPORT_RE.findall(text))


def _is_public(path: Path) -> bool:
    """Return ``True`` if a path represents a public module or package.

    Public means the file/directory name does not start with an underscore
    and is not a ``__pycache__`` directory.
    """
    name = path.name
    if name.startswith("_"):
        return False
    return name != "__pycache__"


def _title(name: str) -> str:
    """Convert a module name like ``key_renderer`` to ``Key Renderer``."""
    return name.replace("_", " ").title()


# Each entry: (depth, title, doc_path_relative_to_reference)
# depth is used to indent the SUMMARY.md so mkdocs-literate-nav nests entries.
nav_entries: list[tuple[int, str, str]] = []


def _emit_module_page(dotted: str, doc_path: str, edit_path: str, title: str) -> None:
    """Write a single mkdocstrings page for ``dotted`` to ``doc_path``."""
    with mkdocs_gen_files.open(doc_path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(f"::: {dotted}\n")
    mkdocs_gen_files.set_edit_path(doc_path, edit_path)


def _walk_package(pkg_dir: Path, depth: int, dotted_prefix: str, rel_prefix: str) -> None:
    """Recursively emit reference pages for ``pkg_dir``.

    Children whose symbols are re-exported by ``pkg_dir/__init__.py`` are
    skipped so we do not produce duplicate mkdocstrings anchors that would
    break ``mkdocs --strict``.

    Parameters
    ----------
    pkg_dir : Path
        Directory on disk containing ``__init__.py``.
    depth : int
        Nesting depth used for SUMMARY indentation (0 = top-level under
        ``reference/``).
    dotted_prefix : str
        Dotted Python path of ``pkg_dir`` (e.g. ``deux.runtime``).
    rel_prefix : str
        Path under ``reference/`` matching ``dotted_prefix`` without the
        leading ``deux`` segment (e.g. ``runtime`` or ``runtime/hid``).
    """
    reexports = _reexported_children(pkg_dir / "__init__.py")
    # The reference root (``src/deux`` itself) is depth 0. Its immediate
    # children are the top-level sub-package landing pages and must always
    # be emitted regardless of how aggressively ``deux/__init__.py``
    # re-exports them, otherwise we would regress the existing reference
    # surface entirely.
    suppress_reexports = depth > 0

    # Collect sub-packages and public top-level modules.
    sub_packages: list[Path] = []
    sub_modules: list[Path] = []
    for child in sorted(pkg_dir.iterdir()):
        if not _is_public(child):
            continue
        if child.is_dir() and (child / "__init__.py").exists():
            sub_packages.append(child)
        elif child.is_file() and child.suffix == ".py" and child.stem != "__init__":
            sub_modules.append(child)

    for sub in sub_packages:
        name = sub.name
        # Always recurse — a re-exported child may itself contain non-
        # re-exported grandchildren that we still want to surface.
        if not suppress_reexports or name not in reexports:
            dotted = f"{dotted_prefix}.{name}"
            rel = f"{rel_prefix}/{name}" if rel_prefix else name
            doc_path = f"reference/{rel}.md"
            edit_path = f"../src/{PACKAGE}/{rel}/__init__.py"
            _emit_module_page(dotted, doc_path, edit_path, _title(name))
            nav_entries.append((depth, _title(name), f"{rel}.md"))
            _walk_package(sub, depth + 1, f"{dotted_prefix}.{name}", rel)
        else:
            # Re-exported sub-package: descend without emitting a page so
            # any non-re-exported grandchildren still appear, but skip
            # adding nav entries that would clutter the hierarchy.
            _walk_package(
                sub,
                depth + 1,
                f"{dotted_prefix}.{name}",
                f"{rel_prefix}/{name}" if rel_prefix else name,
            )

    for mod in sub_modules:
        name = mod.stem
        if suppress_reexports and name in reexports:
            continue
        dotted = f"{dotted_prefix}.{name}"
        rel = f"{rel_prefix}/{name}" if rel_prefix else name
        doc_path = f"reference/{rel}.md"
        edit_path = f"../src/{PACKAGE}/{rel}.py"
        _emit_module_page(dotted, doc_path, edit_path, _title(name))
        nav_entries.append((depth, _title(name), f"{rel}.md"))


_walk_package(SRC / PACKAGE, depth=0, dotted_prefix=PACKAGE, rel_prefix="")


# Write the SUMMARY consumed by mkdocs-literate-nav. Indentation drives nesting.
# Python-markdown's list parser requires each nested level to be indented by
# *two* spaces relative to the parent's bullet content; using four spaces
# would be interpreted as a paragraph continuation, not a sub-list.
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as f:
    for depth, title, href in nav_entries:
        indent = "  " * depth
        f.write(f"{indent}- [{title}]({href})\n")
