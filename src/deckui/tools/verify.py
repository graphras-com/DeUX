"""Verify .dui packages for correctness and repository readiness.

Usage::

    python -m deckui.tools.verify path/to/MyPackage.dui
    python -m deckui.tools.verify --strict path/to/MyPackage.dui
    python -m deckui.tools.verify --index path/to/packages/

"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

from deckui.dui.loader import PackageError, load_package
from deckui.dui.schema import KNOWN_MANIFEST_KEYS, VALID_CATEGORIES, PackageSpec

logger = logging.getLogger(__name__)

MAX_PACKAGE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


class Severity(Enum):
    """Diagnostic severity level."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A single verification finding."""

    severity: Severity
    message: str


@dataclass(slots=True)
class VerifyResult:
    """Aggregated verification result for a single package."""

    path: Path
    package_name: str | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    spec: PackageSpec | None = None

    @property
    def errors(self) -> list[Diagnostic]:
        """Diagnostics with :attr:`Severity.ERROR` severity."""
        return [d for d in self.diagnostics if d.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        """Diagnostics with :attr:`Severity.WARNING` severity."""
        return [d for d in self.diagnostics if d.severity == Severity.WARNING]

    @property
    def ok(self) -> bool:
        """``True`` if there are no error-level diagnostics."""
        return len(self.errors) == 0


def verify_package(path: str | Path, *, strict: bool = False) -> VerifyResult:
    """Verify a .dui package directory.

    Parameters
    ----------
    path
        Path to the ``.dui`` directory.
    strict
        When ``True``, warnings are promoted to errors. Use this for
        repository submission gates.

    Returns
    -------
    VerifyResult
        Contains all diagnostics and the loaded spec (if loading succeeded).
    """
    pkg_dir = Path(path)
    result = VerifyResult(path=pkg_dir)

    # 1. Try loading the package (validates structure, bindings, events, regions)
    try:
        spec = load_package(pkg_dir)
    except PackageError as exc:
        result.diagnostics.append(Diagnostic(Severity.ERROR, f"Load failed: {exc}"))
        return result

    result.spec = spec
    result.package_name = spec.name

    def _add(severity: Severity, message: str) -> None:
        if strict and severity == Severity.WARNING:
            severity = Severity.ERROR
        result.diagnostics.append(Diagnostic(severity, message))

    # 2. Required metadata for repository
    if not spec.description:
        _add(Severity.WARNING, "Missing 'description' — required for repository listing")
    if not spec.author:
        _add(Severity.WARNING, "Missing 'author' — required for repository listing")

    # 3. Category validation (already validated in loader, but check presence)
    if spec.category is not None and spec.category not in VALID_CATEGORIES:
        _add(Severity.ERROR, f"Invalid category '{spec.category}'")

    # 4. Tags validation
    for tag in spec.tags:
        if tag != tag.lower():
            _add(Severity.WARNING, f"Tag '{tag}' should be lowercase")

    # 5. Icon exists if declared
    if spec.icon:
        icon_name = spec.icon.removeprefix("assets/")
        if icon_name not in spec.assets:
            _add(Severity.WARNING, f"Declared icon '{spec.icon}' not found in assets/")

    # 6. Unknown manifest keys (typo detection)
    manifest_path = pkg_dir / "manifest.yaml"
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as f:
            raw_manifest = yaml.safe_load(f)
        if isinstance(raw_manifest, dict):
            unknown = set(raw_manifest.keys()) - KNOWN_MANIFEST_KEYS
            for key in sorted(unknown):
                _add(Severity.WARNING, f"Unknown manifest key '{key}' — possible typo?")

    # 7. Package size budget
    total_size = 0
    for asset_bytes in spec.assets.values():
        total_size += len(asset_bytes)
    total_size += len(spec.svg_source.encode("utf-8"))
    if total_size > MAX_PACKAGE_SIZE_BYTES:
        size_mb = total_size / (1024 * 1024)
        _add(Severity.WARNING, f"Package size {size_mb:.1f}MB exceeds 2MB budget")

    # 8. License SPDX hint
    if spec.license and " " in spec.license:
        _add(
            Severity.WARNING,
            f"License '{spec.license}' contains spaces — use an SPDX identifier "
            "(e.g. 'MIT', 'Apache-2.0', 'CC-BY-4.0')",
        )

    return result


def _spec_to_index_entry(spec: PackageSpec) -> dict[str, object]:
    """Convert a PackageSpec to a JSON-serializable index entry.

    Parameters
    ----------
    spec : PackageSpec
        Loaded and validated package specification.

    Returns
    -------
    dict[str, object]
        Dictionary suitable for inclusion in a repository index JSON file.
    """
    return {
        "name": spec.name,
        "type": spec.type.value,
        "version": spec.version,
        "description": spec.description,
        "author": spec.author,
        "license": spec.license,
        "tags": list(spec.tags),
        "category": spec.category,
        "url": spec.url,
        "icon": spec.icon,
        "min_deckui": spec.min_deckui,
        "device": list(spec.device),
        "bindings": sorted(spec.bindings.keys()),
        "events": [e.name for e in spec.events],
    }


def verify_directory(
    directory: str | Path, *, strict: bool = False
) -> tuple[list[VerifyResult], dict[str, object]]:
    """Verify all .dui packages in a directory and build a repository index.

    Returns
    -------
    tuple[list[VerifyResult], dict]
        A list of per-package results and a JSON-serializable index dict.
    """
    base = Path(directory)
    if not base.is_dir():
        msg = f"Not a directory: {base}"
        raise PackageError(msg)

    results: list[VerifyResult] = []
    index_entries: list[dict[str, object]] = []

    for entry in sorted(base.iterdir()):
        if entry.is_dir() and entry.suffix == ".dui":
            result = verify_package(entry, strict=strict)
            results.append(result)
            if result.spec:
                index_entries.append(_spec_to_index_entry(result.spec))

    return results, {"packages": index_entries}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for package verification."""
    parser = argparse.ArgumentParser(
        prog="deckui-verify",
        description="Verify .dui packages for correctness and repository readiness.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a .dui package directory, or a parent directory with --index",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Promote warnings to errors (use for repository submission gates)",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Verify all packages in the directory and emit a JSON index to stdout",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    if args.index:
        try:
            results, index = verify_directory(args.path, strict=args.strict)
        except PackageError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        any_errors = False
        for result in results:
            _print_result(result)
            if not result.ok:
                any_errors = True

        if not any_errors:
            json.dump(index, sys.stdout, indent=2)
            print()  # trailing newline

        return 1 if any_errors else 0

    result = verify_package(args.path, strict=args.strict)
    _print_result(result)
    return 0 if result.ok else 1


def _print_result(result: VerifyResult) -> None:
    """Print verification diagnostics to stderr.

    Parameters
    ----------
    result : VerifyResult
        Verification result for a single package.
    """
    label = result.package_name or str(result.path)
    if not result.diagnostics:
        print(f"  {label}: OK", file=sys.stderr)
        return
    for diag in result.diagnostics:
        prefix = diag.severity.value.upper()
        print(f"  {label}: {prefix}: {diag.message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
