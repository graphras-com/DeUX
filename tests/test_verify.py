"""Tests for deux.tools.verify — package verification and index generation."""

from __future__ import annotations

import json

import pytest

from deux.tools.verify import (
    main,
    verify_directory,
    verify_package,
)


class TestVerifyPackageValid:
    """Verify passes for well-formed packages with metadata."""

    def test_card_package_ok(self, card_dui_path):
        result = verify_package(card_dui_path)
        assert result.ok
        assert result.package_name == "TestCard"
        assert result.spec is not None
        assert len(result.errors) == 0

    def test_key_package_ok(self, key_dui_path):
        result = verify_package(key_dui_path)
        assert result.ok
        assert result.package_name == "TestKey"

    def test_no_diagnostics_for_complete_package(self, card_dui_path):
        result = verify_package(card_dui_path)
        assert result.diagnostics == []


class TestVerifyPackageMissingMetadata:
    """Verify warns (not errors) when optional metadata is missing."""

    _SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"/>'

    def _make_minimal(self, tmp_path):
        pkg = tmp_path / "Bare.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text(self._SVG, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bare\ntype: Key\nversion: 1\nlayout: layout.svg",
            encoding="utf-8",
        )
        return pkg

    def test_warns_missing_description(self, tmp_path):
        result = verify_package(self._make_minimal(tmp_path))
        assert result.ok  # warnings don't fail
        msgs = [d.message for d in result.warnings]
        assert any("description" in m for m in msgs)

    def test_warns_missing_author(self, tmp_path):
        result = verify_package(self._make_minimal(tmp_path))
        msgs = [d.message for d in result.warnings]
        assert any("author" in m for m in msgs)

    def test_strict_promotes_warnings(self, tmp_path):
        result = verify_package(self._make_minimal(tmp_path), strict=True)
        assert not result.ok
        assert len(result.errors) >= 2


class TestVerifyPackageChecks:
    """Test specific verification checks."""

    _SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"/>'

    def test_unknown_manifest_key(self, tmp_path):
        pkg = tmp_path / "Typo.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text(self._SVG, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Typo\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            'desciption: "typo"\nauthor: "A"',
            encoding="utf-8",
        )
        result = verify_package(pkg)
        msgs = [d.message for d in result.warnings]
        assert any("desciption" in m for m in msgs)

    def test_uppercase_tag_warning(self, tmp_path):
        pkg = tmp_path / "Tags.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text(self._SVG, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Tags\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            'description: "d"\nauthor: "a"\ntags: [Media, MUSIC]',
            encoding="utf-8",
        )
        result = verify_package(pkg)
        tag_warnings = [d for d in result.warnings if "lowercase" in d.message]
        assert len(tag_warnings) == 2

    def test_icon_not_found_warning(self, tmp_path):
        pkg = tmp_path / "Icon.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text(self._SVG, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Icon\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            'description: "d"\nauthor: "a"\nicon: "assets/missing.png"',
            encoding="utf-8",
        )
        result = verify_package(pkg)
        msgs = [d.message for d in result.warnings]
        assert any("missing.png" in m for m in msgs)

    def test_license_with_spaces_warning(self, tmp_path):
        pkg = tmp_path / "Lic.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text(self._SVG, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Lic\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            'description: "d"\nauthor: "a"\nlicense: "MIT License"',
            encoding="utf-8",
        )
        result = verify_package(pkg)
        msgs = [d.message for d in result.warnings]
        assert any("SPDX" in m for m in msgs)

    def test_load_failure_is_error(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text("name: Bad", encoding="utf-8")
        result = verify_package(pkg)
        assert not result.ok
        assert result.spec is None

    def test_large_package_warning(self, tmp_path):
        pkg = tmp_path / "Big.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text(self._SVG, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Big\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            'description: "d"\nauthor: "a"',
            encoding="utf-8",
        )
        assets = pkg / "assets"
        assets.mkdir()
        (assets / "huge.bin").write_bytes(b"\x00" * (3 * 1024 * 1024))
        result = verify_package(pkg)
        msgs = [d.message for d in result.warnings]
        assert any("2MB" in m for m in msgs)


class TestVerifyDirectory:
    """Test directory-level verification and index generation."""

    def test_verify_all_packages(self, dui_packages_dir):
        results, index = verify_directory(dui_packages_dir)
        assert len(results) == 2
        assert all(r.ok for r in results)
        assert len(index["packages"]) == 2

    def test_index_contains_metadata(self, dui_packages_dir):
        _, index = verify_directory(dui_packages_dir)
        names = {p["name"] for p in index["packages"]}
        assert "TestCard" in names
        assert "TestKey" in names
        card = next(p for p in index["packages"] if p["name"] == "TestCard")
        assert card["description"] == "A test card for audio playback"
        assert card["category"] == "media"
        assert card["tags"] == ["music", "test"]

    def test_not_a_directory(self, tmp_path):
        from deux.dui.loader import PackageError

        with pytest.raises(PackageError, match="Not a directory"):
            verify_directory(tmp_path / "nope")

    def test_empty_directory(self, tmp_path):
        results, index = verify_directory(tmp_path)
        assert results == []
        assert index["packages"] == []


class TestVerifyCLI:
    """Test the CLI entry point."""

    def test_verify_single_package(self, card_dui_path):
        assert main([str(card_dui_path)]) == 0

    def test_verify_strict_fails_without_metadata(self, tmp_path):
        pkg = tmp_path / "Bare.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bare\ntype: Key\nversion: 1\nlayout: layout.svg",
            encoding="utf-8",
        )
        assert main(["--strict", str(pkg)]) == 1

    def test_verify_index(self, dui_packages_dir, capsys):
        assert main(["--index", str(dui_packages_dir)]) == 0
        captured = capsys.readouterr()
        index = json.loads(captured.out)
        assert len(index["packages"]) == 2

    def test_verify_invalid_path(self, tmp_path):
        assert main([str(tmp_path / "nope.dui")]) == 1

    def test_verify_index_invalid_path(self, tmp_path):
        assert main(["--index", str(tmp_path / "nope")]) == 1
