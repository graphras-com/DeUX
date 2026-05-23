"""Auto-generate API reference pages for mkdocstrings.

This script is executed by the mkdocs-gen-files plugin during ``mkdocs build``.
It recursively walks the ``src/deux`` package tree and creates a virtual
``reference/<path>.md`` page for every public sub-package **and** every public
top-level module within those sub-packages. Each page contains the appropriate
``::: deux.<dotted.path>`` directive so that *mkdocstrings* renders the API
docs from docstrings automatically.

A ``reference/SUMMARY.md`` file is also generated so that *mkdocs-literate-nav*
can build a hierarchical sidebar without manual ``nav:`` entries.

Why recursive?
--------------
The previous implementation only walked the top-level sub-packages of
``src/deux`` and relied on each ``__init__.py`` re-exporting everything of
interest. That left several user-facing surfaces invisible in the rendered
reference (notably ``deux.runtime.hid`` and the CLI modules under
``deux.tools``). Walking recursively and emitting one page per public package
**and** per public module guarantees full coverage regardless of how
aggressively a parent ``__init__`` re-exports.
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

SRC = Path("src")
PACKAGE = "deux"


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
        dotted = f"{dotted_prefix}.{name}"
        rel = f"{rel_prefix}/{name}" if rel_prefix else name
        doc_path = f"reference/{rel}.md"
        edit_path = f"../src/{PACKAGE}/{rel}/__init__.py"
        _emit_module_page(dotted, doc_path, edit_path, _title(name))
        nav_entries.append((depth, _title(name), f"{rel}.md"))
        _walk_package(sub, depth + 1, dotted, rel)

    for mod in sub_modules:
        name = mod.stem
        dotted = f"{dotted_prefix}.{name}"
        rel = f"{rel_prefix}/{name}" if rel_prefix else name
        doc_path = f"reference/{rel}.md"
        edit_path = f"../src/{PACKAGE}/{rel}.py"
        _emit_module_page(dotted, doc_path, edit_path, _title(name))
        nav_entries.append((depth, _title(name), f"{rel}.md"))


_walk_package(SRC / PACKAGE, depth=0, dotted_prefix=PACKAGE, rel_prefix="")


# Write the SUMMARY consumed by mkdocs-literate-nav. Indentation drives nesting.
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as f:
    for depth, title, href in nav_entries:
        indent = "    " * depth
        f.write(f"{indent}- [{title}]({href})\n")
