"""DUI package repository — name-based resolution with search paths and caching.

The repository maintains an ordered list of directories to search for
``.dui`` packages and an in-memory cache of loaded
:class:`~deux.dui.schema.PackageSpec` objects.  Packages bundled with
the library are always available as a lowest-priority fallback.

Typical usage::

    import deux

    # Bundled packages work out of the box
    card = deux.DuiCard("DashboardCard")
    key  = deux.DuiKey("IconKey")

    # Register a custom directory — overrides bundled if names collide
    deux.add_dui_path("~/my-dui-packages")

    # Introspect
    print(deux.list_dui_packages())
"""

from __future__ import annotations

import logging
from pathlib import Path

from .loader import PackageError, load_package
from .schema import PackageSpec

logger = logging.getLogger(__name__)

_BUNDLED_DIR = Path(__file__).resolve().parent / "packages"
"""Absolute path to the bundled packages shipped with the library."""


class DuiRepository:
    """Registry of .dui package search paths with in-memory caching.

    Directories are searched in *priority order* — the most recently
    added path wins when two directories contain a package with the
    same name.  The bundled packages directory is always present as
    the lowest-priority source and cannot be removed.

    Parameters
    ----------
    include_bundled : bool, default=True
        Whether to include the bundled packages directory.  Set to
        ``False`` only in tests that need a completely empty repo.

    Examples
    --------
    ::

        repo = DuiRepository()
        repo.add_path("/home/user/my-packages")
        spec = repo.resolve("IconKey")
    """

    def __init__(self, *, include_bundled: bool = True) -> None:
        self._paths: list[Path] = []
        self._cache: dict[str, PackageSpec] = {}
        self._include_bundled = include_bundled

    # ── Path management ───────────────────────────────────────────────

    def add_path(self, path: str | Path) -> None:
        """Register a directory as a DUI package source.

        The directory is inserted at the *highest* priority position.
        If it is already registered it is moved to the top.  The
        in-memory cache is cleared so that subsequent :meth:`resolve`
        calls pick up any overrides.

        Parameters
        ----------
        path : str or Path
            Directory containing ``.dui`` package subdirectories.

        Raises
        ------
        PackageError
            If *path* does not exist or is not a directory.
        """
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir():
            raise PackageError(f"DUI path is not a directory: {resolved}")

        # Move to top if already present, otherwise append
        if resolved in self._paths:
            self._paths.remove(resolved)
        self._paths.append(resolved)
        self._cache.clear()
        logger.info("Added DUI path: %s (priority %d)", resolved, len(self._paths))

    def remove_path(self, path: str | Path) -> None:
        """Unregister a directory.  Clears the cache.

        Parameters
        ----------
        path : str or Path
            Previously registered directory.

        Raises
        ------
        ValueError
            If *path* is not currently registered.
        """
        resolved = Path(path).expanduser().resolve()
        try:
            self._paths.remove(resolved)
        except ValueError:
            raise ValueError(f"Path not registered: {resolved}") from None
        self._cache.clear()
        logger.info("Removed DUI path: %s", resolved)

    def list_paths(self) -> list[Path]:
        """Return registered search paths in priority order (highest first).

        The bundled directory is included at the end when
        ``include_bundled`` is ``True``.

        Returns
        -------
        list[Path]
            Ordered list of directories.
        """
        # Reverse so that last-added (highest priority) comes first
        result = list(reversed(self._paths))
        if self._include_bundled and _BUNDLED_DIR.is_dir():
            result.append(_BUNDLED_DIR)
        return result

    # ── Resolution & caching ──────────────────────────────────────────

    def resolve(self, name: str) -> PackageSpec:
        """Look up a package by name and return a cached spec.

        Search order: user paths (most recently added first), then
        bundled packages.  The result is cached so that repeated calls
        with the same *name* return the identical :class:`PackageSpec`
        object without re-reading the filesystem.

        Parameters
        ----------
        name : str
            Package name **without** the ``.dui`` suffix
            (e.g. ``"IconKey"``, not ``"IconKey.dui"``).

        Returns
        -------
        PackageSpec
            A validated, frozen package specification.

        Raises
        ------
        PackageError
            If no package with that name exists in any registered path.
        """
        cached = self._cache.get(name)
        if cached is not None:
            return cached

        pkg_dir = self._find(name)
        if pkg_dir is None:
            paths_desc = ", ".join(str(p) for p in self.list_paths()) or "(none)"
            raise PackageError(
                f"DUI package '{name}' not found. "
                f"Searched paths: {paths_desc}"
            )

        spec = load_package(pkg_dir)
        self._cache[name] = spec
        logger.debug("Resolved DUI package '%s' from %s", name, pkg_dir)
        return spec

    def _find(self, name: str) -> Path | None:
        """Locate the directory for *name* across all search paths.

        Parameters
        ----------
        name : str
            Package name without the ``.dui`` suffix.

        Returns
        -------
        Path or None
            Absolute path to the ``.dui`` directory, or ``None`` if
            not found in any registered path.
        """
        dir_name = f"{name}.dui"

        # User paths in priority order (last-added first)
        for base in reversed(self._paths):
            candidate = base / dir_name
            if candidate.is_dir():
                return candidate

        # Bundled fallback
        if self._include_bundled and _BUNDLED_DIR.is_dir():
            candidate = _BUNDLED_DIR / dir_name
            if candidate.is_dir():
                return candidate

        return None

    # ── Cache management ──────────────────────────────────────────────

    def clear_cache(self) -> None:
        """Drop all cached :class:`PackageSpec` objects.

        Subsequent :meth:`resolve` calls will re-read packages from
        disk.
        """
        count = len(self._cache)
        self._cache.clear()
        if count:
            logger.debug("Cleared DUI package cache (%d entries)", count)

    def invalidate(self, name: str) -> None:
        """Remove a single package from the cache.

        Use this after editing a ``.dui`` package on disk to force
        :meth:`resolve` to reload it.

        Parameters
        ----------
        name : str
            Package name to invalidate.
        """
        removed = self._cache.pop(name, None)
        if removed is not None:
            logger.debug("Invalidated cached DUI package '%s'", name)

    # ── Introspection ─────────────────────────────────────────────────

    def list_packages(self) -> list[str]:
        """List all package names visible across all search paths.

        Packages are returned in alphabetical order.  If the same name
        exists in multiple paths only one entry is returned.

        Returns
        -------
        list[str]
            Sorted package names (without the ``.dui`` suffix).
        """
        names: set[str] = set()
        for base in self.list_paths():
            if base.is_dir():
                for entry in base.iterdir():
                    if entry.is_dir() and entry.suffix == ".dui":
                        names.add(entry.stem)
        return sorted(names)

    def __repr__(self) -> str:
        n_paths = len(self._paths) + (1 if self._include_bundled else 0)
        return (
            f"DuiRepository(paths={n_paths}, "
            f"cached={len(self._cache)}, "
            f"bundled={self._include_bundled})"
        )


# ── Module-level convenience API ──────────────────────────────────────

_default_repository: DuiRepository | None = None


def _get_repository() -> DuiRepository:
    """Return (and lazily create) the default global repository.

    Returns
    -------
    DuiRepository
        The singleton repository instance.
    """
    global _default_repository
    if _default_repository is None:
        _default_repository = DuiRepository()
    return _default_repository


def add_dui_path(path: str | Path) -> None:
    """Register a directory as a DUI package source.

    The directory is inserted at the highest priority position.
    Packages in this directory will override bundled packages and
    packages from previously added directories when names collide.

    Parameters
    ----------
    path : str or Path
        Directory containing ``.dui`` package subdirectories.

    Raises
    ------
    PackageError
        If *path* does not exist or is not a directory.

    Examples
    --------
    ::

        import deux

        deux.add_dui_path("/home/user/my-packages")
        card = deux.DuiCard("MyCustomCard")
    """
    _get_repository().add_path(path)


def remove_dui_path(path: str | Path) -> None:
    """Unregister a previously added DUI package directory.

    Parameters
    ----------
    path : str or Path
        Previously registered directory.

    Raises
    ------
    ValueError
        If *path* is not currently registered.
    """
    _get_repository().remove_path(path)


def resolve_dui(name: str) -> PackageSpec:
    """Look up a DUI package by name and return its spec.

    This is the function called internally when ``DuiCard("name")``
    or ``DuiKey("name")`` receive a string argument.

    Parameters
    ----------
    name : str
        Package name without the ``.dui`` suffix.

    Returns
    -------
    PackageSpec
        A validated, frozen package specification.

    Raises
    ------
    PackageError
        If no package with that name exists in any registered path.
    """
    return _get_repository().resolve(name)


def list_dui_packages() -> list[str]:
    """List all DUI package names visible across all search paths.

    Returns
    -------
    list[str]
        Sorted package names (without the ``.dui`` suffix).
    """
    return _get_repository().list_packages()


def clear_dui_cache() -> None:
    """Drop all cached package specs from the default repository.

    Subsequent ``DuiCard("name")`` / ``DuiKey("name")`` calls will
    re-read packages from disk.
    """
    _get_repository().clear_cache()
