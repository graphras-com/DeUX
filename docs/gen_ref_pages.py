"""Auto-generate API reference pages for mkdocstrings.

This script is executed by the mkdocs-gen-files plugin during ``mkdocs build``.
It walks the ``src/deux`` package tree and creates a virtual
``reference/<module>.md`` page for every public sub-package, each containing
the appropriate ``::: deux.<module>`` directive so that *mkdocstrings*
renders the API docs from docstrings automatically.

A ``reference/SUMMARY.md`` file is also generated so that *mkdocs-literate-nav*
can build the sidebar navigation without manual ``nav:`` entries.
"""

from pathlib import Path

import mkdocs_gen_files

SRC = Path("src")
PACKAGE = "deux"

nav_lines: list[str] = []

# Generate one page per top-level sub-package (runtime, ui, dui, render, tools)
for child in sorted((SRC / PACKAGE).iterdir()):
    if not child.is_dir() or child.name.startswith("_"):
        continue
    if not (child / "__init__.py").exists():
        continue

    module_path = f"{PACKAGE}.{child.name}"
    doc_path = f"reference/{child.name}.md"

    with mkdocs_gen_files.open(doc_path, "w") as f:
        f.write(f"# {child.name.replace('_', ' ').title()}\n\n")
        f.write(f"::: {module_path}\n")

    mkdocs_gen_files.set_edit_path(doc_path, f"../src/{PACKAGE}/{child.name}/__init__.py")
    nav_lines.append(f"- [{child.name.replace('_', ' ').title()}]({child.name}.md)")

# Write the SUMMARY consumed by literate-nav
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as f:
    f.write("\n".join(nav_lines) + "\n")
