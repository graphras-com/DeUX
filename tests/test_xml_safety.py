"""Tests for the safe XML parsing module (``deux._xml``)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from deux._xml import safe_fromstring


class TestSafeFromstring:
    """Verify that ``safe_fromstring`` rejects dangerous XML payloads."""

    def test_valid_svg_parsed(self) -> None:
        """A simple well-formed SVG should parse successfully."""
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
        root = safe_fromstring(svg)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert root.get("width") == "10"

    def test_billion_laughs_rejected(self) -> None:
        """A billion-laughs payload must be rejected by ``defusedxml``.

        This is the primary threat described in issue #188.  The payload
        uses recursive entity expansion to exhaust CPU / memory.
        """
        payload = (
            '<?xml version="1.0"?>\n'
            "<!DOCTYPE lolz [\n"
            '  <!ENTITY lol "lol">\n'
            '  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">\n'
            '  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">\n'  # noqa: E501
            '  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">\n'  # noqa: E501
            "]>\n"
            "<root>&lol4;</root>"
        )
        with pytest.raises(Exception):  # noqa: B017 — DTDForbidden or EntitiesForbidden
            safe_fromstring(payload)

    def test_external_entity_rejected(self) -> None:
        """External entity references must be rejected."""
        payload = (
            '<?xml version="1.0"?>\n'
            "<!DOCTYPE foo [\n"
            '  <!ENTITY xxe SYSTEM "file:///etc/passwd">\n'
            "]>\n"
            "<root>&xxe;</root>"
        )
        with pytest.raises(Exception):  # noqa: B017
            safe_fromstring(payload)

    def test_malformed_xml_raises(self) -> None:
        """Non-XML input must raise ``ParseError``."""
        with pytest.raises(ET.ParseError):
            safe_fromstring("not xml at all")

    def test_accepts_bytes_input(self) -> None:
        """``safe_fromstring`` should accept ``bytes`` as well as ``str``."""
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        root = safe_fromstring(svg)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
