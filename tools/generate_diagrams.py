#!/usr/bin/env python3
"""Generate architecture diagrams from DeUX source code.

Uses pyreverse to extract class and package relationships, then renders
them to SVG via Graphviz. The resulting files are placed in
``docs/architecture/`` for inclusion in the MkDocs site.

Requirements
------------
- ``pylint`` (provides ``pyreverse``)
- ``graphviz`` (provides the ``dot`` CLI)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_NAME = "deux"
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_PATH = SRC_ROOT / PROJECT_NAME
OUTPUT_DIR = REPO_ROOT / "docs" / "architecture"

DOT_FILES = {
    f"classes_{PROJECT_NAME}.dot": "classes.svg",
    f"packages_{PROJECT_NAME}.dot": "packages.svg",
}


def _check_prerequisites() -> None:
    """Verify that required external tools are available.

    Raises
    ------
    SystemExit
        Raised when Graphviz ``dot`` is not available on ``PATH``.
    """
    if shutil.which("dot") is None:
        print("ERROR: 'dot' (graphviz) not found on PATH", file=sys.stderr)
        raise SystemExit(1)


def _run(cmd: list[str], **kwargs: object) -> None:
    """Run a subprocess and fail loudly if it exits non-zero.

    Parameters
    ----------
    cmd : list[str]
        Command and arguments to execute.
    **kwargs : object
        Additional keyword arguments passed to ``subprocess.run``.
    """
    print(f"  > {' '.join(cmd)}")
    subprocess.run(cmd, check=True, **kwargs)  # noqa: S603


def main() -> None:
    """Generate class and package diagrams as SVG files.

    Raises
    ------
    SystemExit
        Raised when Graphviz is unavailable or when expected pyreverse
        output files are not produced.
    """
    _check_prerequisites()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        print("Running pyreverse ...")
        _run(
            [
                sys.executable,
                "-m",
                "pylint.pyreverse.main",
                "--output",
                "dot",
                "--project",
                PROJECT_NAME,
                "--source-roots",
                str(SRC_ROOT),
                str(PACKAGE_PATH),
            ],
            cwd=tmp,
        )

        for dot_name, svg_name in DOT_FILES.items():
            dot_file = tmp_path / dot_name
            if not dot_file.exists():
                print(f"ERROR: expected {dot_name} not found", file=sys.stderr)
                raise SystemExit(1)

            svg_dest = OUTPUT_DIR / svg_name
            print(f"Rendering {dot_name} -> {svg_dest}")
            _run(["dot", "-Tsvg", str(dot_file), "-o", str(svg_dest)])

    print("Done. Diagrams written to", OUTPUT_DIR)


if __name__ == "__main__":
    main()
