"""Run architecture diagram generation during MkDocs builds.

This script is executed by the ``mkdocs-gen-files`` plugin during
``mkdocs build`` so local docs builds regenerate architecture diagrams
without relying on a separate manual pre-build step.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Generate docs architecture diagrams from the repository root."""
    repo_root = Path(__file__).resolve().parent.parent
    subprocess.run(  # noqa: S603
        [sys.executable, "tools/generate_diagrams.py"],
        check=True,
        cwd=repo_root,
    )


main()
