# Architecture

Diagrams showing the structure of the DeUX codebase.

These SVGs are produced from source by `tools/generate_diagrams.py` (invoked
automatically via `docs/gen_diagrams.py` during `mkdocs build`). They are
**not** committed to the repository — they are written into
`docs/architecture/` (which is listed in `.gitignore`) at build time and
require both [Graphviz](https://graphviz.org/) (`dot` on `PATH`) and
[`pylint`](https://pypi.org/project/pylint/) (which ships `pyreverse`).

To refresh them locally outside of a docs build, run:

```bash
python tools/generate_diagrams.py
```

## Class Diagram

![Class Diagram](architecture/classes.svg)

## Package Diagram

![Package Diagram](architecture/packages.svg)
