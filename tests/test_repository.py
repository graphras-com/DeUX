"""Tests for deckui.dui.repository — DUI package repository and name-based resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from deckui.dui.card import DuiCard
from deckui.dui.key import DuiKey
from deckui.dui.loader import PackageError
from deckui.dui.repository import (
    DuiRepository,
    _get_repository,
    add_dui_path,
    clear_dui_cache,
    list_dui_packages,
    remove_dui_path,
    resolve_dui,
)
from deckui.dui.schema import PackageSpec, PackageType

# ── Minimal SVG templates (mirrors conftest but self-contained) ───────

_CARD_SVG = (
    '<svg id="TestCard" xmlns="http://www.w3.org/2000/svg" '
    'width="197" height="98">'
    '<rect id="background" width="197" height="98" fill="#1c1c1c"/>'
    '<text id="title" x="4" y="40" font-size="14" fill="#ffffff">Default</text>'
    "</svg>"
)

_KEY_SVG = (
    '<svg id="TestKey" xmlns="http://www.w3.org/2000/svg" '
    'width="120" height="120">'
    '<rect id="background" width="120" height="120" fill="#1c1c1c"/>'
    '<text id="label" x="60" y="100" font-size="14" fill="#ffffff" '
    'text-anchor="middle">Key</text>'
    "</svg>"
)


# ── Helpers ───────────────────────────────────────────────────────────


def _create_minimal_card(base_dir: Path, name: str = "TestCard") -> Path:
    """Create a minimal TouchStripCard .dui package on disk.

    Parameters
    ----------
    base_dir : Path
        Parent directory for the package.
    name : str
        Package name (directory will be ``<name>.dui``).

    Returns
    -------
    Path
        Path to the created ``.dui`` directory.
    """
    pkg_dir = base_dir / f"{name}.dui"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "layout.svg").write_text(_CARD_SVG, encoding="utf-8")
    manifest = f"""\
name: {name}
type: TouchStripCard
version: 1
layout: layout.svg

bindings:
  title:
    type: text
    node: title
    default: "Hello"
"""
    (pkg_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    return pkg_dir


def _create_minimal_key(base_dir: Path, name: str = "TestKey") -> Path:
    """Create a minimal Key .dui package on disk.

    Parameters
    ----------
    base_dir : Path
        Parent directory for the package.
    name : str
        Package name (directory will be ``<name>.dui``).

    Returns
    -------
    Path
        Path to the created ``.dui`` directory.
    """
    pkg_dir = base_dir / f"{name}.dui"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "layout.svg").write_text(_KEY_SVG, encoding="utf-8")
    manifest = f"""\
name: {name}
type: Key
version: 1
layout: layout.svg

bindings:
  label:
    type: text
    node: label
    default: "Key"
"""
    (pkg_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    return pkg_dir


# ═════════════════════════════════════════════════════════════════════
# DuiRepository class tests
# ═════════════════════════════════════════════════════════════════════


class TestDuiRepositoryBundled:
    """Test the bundled packages that ship with the library."""

    def test_bundled_packages_available(self):
        repo = DuiRepository()
        packages = repo.list_packages()
        assert "IconKey" in packages
        assert "PictureKey" in packages
        assert "DashboardCard" in packages

    def test_resolve_bundled_icon_key(self):
        repo = DuiRepository()
        spec = repo.resolve("IconKey")
        assert isinstance(spec, PackageSpec)
        assert spec.name == "IconKey"
        assert spec.type == PackageType.KEY

    def test_resolve_bundled_picture_key(self):
        repo = DuiRepository()
        spec = repo.resolve("PictureKey")
        assert spec.name == "PictureKey"
        assert spec.type == PackageType.KEY

    def test_resolve_bundled_dashboard_card(self):
        repo = DuiRepository()
        spec = repo.resolve("DashboardCard")
        assert spec.name == "DashboardCard"
        assert spec.type == PackageType.TOUCH_STRIP_CARD

    def test_bundled_dir_is_lowest_priority(self):
        repo = DuiRepository()
        paths = repo.list_paths()
        # Bundled should be last
        assert len(paths) >= 1
        assert paths[-1].name == "packages"


class TestDuiRepositoryNoBundled:
    """Test repository without bundled packages."""

    def test_no_bundled_when_disabled(self):
        repo = DuiRepository(include_bundled=False)
        assert repo.list_packages() == []

    def test_resolve_fails_without_bundled(self):
        repo = DuiRepository(include_bundled=False)
        with pytest.raises(PackageError, match="not found"):
            repo.resolve("IconKey")


class TestDuiRepositoryAddPath:
    """Test adding search paths."""

    def test_add_path(self, tmp_path: Path):
        _create_minimal_card(tmp_path, "MyCard")
        repo = DuiRepository(include_bundled=False)
        repo.add_path(tmp_path)
        spec = repo.resolve("MyCard")
        assert spec.name == "MyCard"

    def test_add_path_validates_directory(self, tmp_path: Path):
        repo = DuiRepository(include_bundled=False)
        with pytest.raises(PackageError, match="not a directory"):
            repo.add_path(tmp_path / "nonexistent")

    def test_add_path_clears_cache(self, tmp_path: Path):
        _create_minimal_card(tmp_path, "MyCard")
        repo = DuiRepository(include_bundled=False)
        repo.add_path(tmp_path)
        spec1 = repo.resolve("MyCard")
        assert spec1 is repo.resolve("MyCard")  # cached

        # Add another path — cache should be cleared
        other = tmp_path / "other"
        other.mkdir()
        repo.add_path(other)
        spec2 = repo.resolve("MyCard")
        assert spec2 is not spec1  # freshly loaded

    def test_add_duplicate_path_moves_to_top(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        repo = DuiRepository(include_bundled=False)
        repo.add_path(dir_a)
        repo.add_path(dir_b)
        repo.add_path(dir_a)  # move a to top

        paths = repo.list_paths()
        assert paths[0] == dir_a.resolve()
        assert paths[1] == dir_b.resolve()


class TestDuiRepositoryRemovePath:
    """Test removing search paths."""

    def test_remove_path(self, tmp_path: Path):
        repo = DuiRepository(include_bundled=False)
        repo.add_path(tmp_path)
        repo.remove_path(tmp_path)
        assert repo.list_paths() == []

    def test_remove_unknown_path_raises(self, tmp_path: Path):
        repo = DuiRepository(include_bundled=False)
        with pytest.raises(ValueError, match="not registered"):
            repo.remove_path(tmp_path)

    def test_remove_path_clears_cache(self, tmp_path: Path):
        _create_minimal_card(tmp_path, "MyCard")
        dir2 = tmp_path / "second"
        dir2.mkdir()
        _create_minimal_card(dir2, "MyCard")

        repo = DuiRepository(include_bundled=False)
        repo.add_path(tmp_path)
        repo.add_path(dir2)
        spec_from_dir2 = repo.resolve("MyCard")

        repo.remove_path(dir2)
        spec_from_tmp = repo.resolve("MyCard")
        # After removing dir2, should resolve from tmp_path (different load)
        assert spec_from_tmp is not spec_from_dir2


class TestDuiRepositoryPriority:
    """Test search-path priority ordering."""

    def test_last_added_wins(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        _create_minimal_card(dir_a, "Shared")
        _create_minimal_card(dir_b, "Shared")

        repo = DuiRepository(include_bundled=False)
        repo.add_path(dir_a)
        repo.add_path(dir_b)

        # dir_b was added last, so it should win
        spec = repo.resolve("Shared")
        assert spec.name == "Shared"

        # Verify by checking the internal find path
        found = repo._find("Shared")
        assert found is not None
        assert found.parent == dir_b.resolve()

    def test_user_path_overrides_bundled(self, tmp_path: Path):
        # Create a package with the same name as a bundled one
        _create_minimal_key(tmp_path, "IconKey")
        repo = DuiRepository(include_bundled=True)
        repo.add_path(tmp_path)

        spec = repo.resolve("IconKey")
        # The user package has no bindings except "label"
        assert "label" in spec.bindings
        # Bundled IconKey has "icon", "background", "foreground" too
        assert "icon" not in spec.bindings

    def test_list_paths_order(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        repo = DuiRepository(include_bundled=False)
        repo.add_path(dir_a)
        repo.add_path(dir_b)

        paths = repo.list_paths()
        # Highest priority first
        assert paths[0] == dir_b.resolve()
        assert paths[1] == dir_a.resolve()


class TestDuiRepositoryCache:
    """Test caching behaviour."""

    def test_cache_returns_same_object(self, tmp_path: Path):
        _create_minimal_card(tmp_path, "Cached")
        repo = DuiRepository(include_bundled=False)
        repo.add_path(tmp_path)

        spec1 = repo.resolve("Cached")
        spec2 = repo.resolve("Cached")
        assert spec1 is spec2

    def test_clear_cache(self, tmp_path: Path):
        _create_minimal_card(tmp_path, "Cached")
        repo = DuiRepository(include_bundled=False)
        repo.add_path(tmp_path)

        spec1 = repo.resolve("Cached")
        repo.clear_cache()
        spec2 = repo.resolve("Cached")
        assert spec1 is not spec2
        assert spec1.name == spec2.name

    def test_invalidate_single(self, tmp_path: Path):
        _create_minimal_card(tmp_path, "Alpha")
        _create_minimal_card(tmp_path, "Beta")
        repo = DuiRepository(include_bundled=False)
        repo.add_path(tmp_path)

        alpha1 = repo.resolve("Alpha")
        beta1 = repo.resolve("Beta")

        repo.invalidate("Alpha")

        alpha2 = repo.resolve("Alpha")
        beta2 = repo.resolve("Beta")

        assert alpha1 is not alpha2  # was invalidated, reloaded
        assert beta1 is beta2  # was NOT invalidated, still cached

    def test_invalidate_nonexistent_is_noop(self):
        repo = DuiRepository(include_bundled=False)
        repo.invalidate("DoesNotExist")  # should not raise


class TestDuiRepositoryResolveErrors:
    """Test error cases in resolve()."""

    def test_not_found(self):
        repo = DuiRepository(include_bundled=False)
        with pytest.raises(PackageError, match="not found"):
            repo.resolve("NonExistent")

    def test_not_found_message_includes_paths(self, tmp_path: Path):
        repo = DuiRepository(include_bundled=False)
        repo.add_path(tmp_path)
        with pytest.raises(PackageError, match=str(tmp_path.resolve())):
            repo.resolve("Missing")


class TestDuiRepositoryListPackages:
    """Test listing available packages."""

    def test_list_across_paths(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        _create_minimal_card(dir_a, "Alpha")
        _create_minimal_key(dir_b, "Beta")

        repo = DuiRepository(include_bundled=False)
        repo.add_path(dir_a)
        repo.add_path(dir_b)

        packages = repo.list_packages()
        assert "Alpha" in packages
        assert "Beta" in packages

    def test_list_deduplicates(self, tmp_path: Path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        _create_minimal_card(dir_a, "Shared")
        _create_minimal_card(dir_b, "Shared")

        repo = DuiRepository(include_bundled=False)
        repo.add_path(dir_a)
        repo.add_path(dir_b)

        packages = repo.list_packages()
        assert packages.count("Shared") == 1

    def test_list_sorted(self, tmp_path: Path):
        _create_minimal_card(tmp_path, "Zebra")
        _create_minimal_card(tmp_path, "Alpha")
        _create_minimal_card(tmp_path, "Middle")

        repo = DuiRepository(include_bundled=False)
        repo.add_path(tmp_path)

        packages = repo.list_packages()
        assert packages == sorted(packages)


class TestDuiRepositoryRepr:
    """Test __repr__."""

    def test_repr_no_bundled(self):
        repo = DuiRepository(include_bundled=False)
        r = repr(repo)
        assert "DuiRepository" in r
        assert "bundled=False" in r

    def test_repr_with_bundled(self):
        repo = DuiRepository(include_bundled=True)
        r = repr(repo)
        assert "bundled=True" in r


# ═════════════════════════════════════════════════════════════════════
# Module-level convenience API tests
# ═════════════════════════════════════════════════════════════════════


class TestModuleLevelAPI:
    """Test the module-level convenience functions."""

    def test_get_repository_returns_singleton(self):
        repo1 = _get_repository()
        repo2 = _get_repository()
        assert repo1 is repo2

    def test_add_and_remove_dui_path(self, tmp_path: Path):
        add_dui_path(tmp_path)
        repo = _get_repository()
        assert tmp_path.resolve() in repo.list_paths()

        remove_dui_path(tmp_path)
        assert tmp_path.resolve() not in repo.list_paths()

    def test_resolve_dui_bundled(self):
        spec = resolve_dui("IconKey")
        assert spec.name == "IconKey"

    def test_resolve_dui_custom(self, tmp_path: Path):
        _create_minimal_card(tmp_path, "Custom")
        add_dui_path(tmp_path)
        spec = resolve_dui("Custom")
        assert spec.name == "Custom"

    def test_list_dui_packages_includes_bundled(self):
        packages = list_dui_packages()
        assert "IconKey" in packages
        assert "PictureKey" in packages
        assert "DashboardCard" in packages

    def test_clear_dui_cache(self):
        spec1 = resolve_dui("IconKey")
        clear_dui_cache()
        spec2 = resolve_dui("IconKey")
        assert spec1 is not spec2


# ═════════════════════════════════════════════════════════════════════
# DuiCard / DuiKey string-init tests
# ═════════════════════════════════════════════════════════════════════


class TestDuiCardStringInit:
    """Test DuiCard accepting a string name instead of a PackageSpec."""

    def test_string_init_bundled(self):
        card = DuiCard("DashboardCard")
        assert card.spec.name == "DashboardCard"

    def test_string_init_custom(self, tmp_path: Path):
        _create_minimal_card(tmp_path, "MyCard")
        add_dui_path(tmp_path)
        card = DuiCard("MyCard")
        assert card.spec.name == "MyCard"

    def test_string_init_not_found(self):
        with pytest.raises(PackageError, match="not found"):
            DuiCard("NonExistentPackage")

    def test_spec_init_still_works(self, card_package_spec: PackageSpec):
        card = DuiCard(card_package_spec)
        assert card.spec is card_package_spec

    def test_string_init_uses_cache(self):
        card1 = DuiCard("DashboardCard")
        card2 = DuiCard("DashboardCard")
        # Different card instances, same cached spec
        assert card1 is not card2
        assert card1.spec is card2.spec


class TestDuiKeyStringInit:
    """Test DuiKey accepting a string name instead of a PackageSpec."""

    def test_string_init_bundled(self):
        key = DuiKey("IconKey")
        assert key.spec.name == "IconKey"

    def test_string_init_custom(self, tmp_path: Path):
        _create_minimal_key(tmp_path, "MyKey")
        add_dui_path(tmp_path)
        key = DuiKey("MyKey")
        assert key.spec.name == "MyKey"

    def test_string_init_not_found(self):
        with pytest.raises(PackageError, match="not found"):
            DuiKey("NonExistentKey")

    def test_spec_init_still_works(self, key_package_spec: PackageSpec):
        key = DuiKey(key_package_spec)
        assert key.spec is key_package_spec

    def test_string_init_uses_cache(self):
        key1 = DuiKey("IconKey")
        key2 = DuiKey("IconKey")
        assert key1 is not key2
        assert key1.spec is key2.spec

    def test_multiple_instances_from_same_name(self):
        """Multiple DuiKey instances from one name share the spec."""
        keys = [DuiKey("IconKey") for _ in range(5)]
        specs = {id(k.spec) for k in keys}
        assert len(specs) == 1  # all share the same cached spec
