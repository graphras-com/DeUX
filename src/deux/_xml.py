"""Safe XML parsing utilities.

Routes untrusted XML (user-supplied ``.dui`` packages, network responses)
through ``defusedxml`` to prevent billion-laughs and other entity-expansion
attacks.  Bundled SVGs shipped with the library may use the standard
``xml.etree.ElementTree`` parser directly.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import defusedxml.ElementTree as SafeET


def safe_fromstring(xml_data: str | bytes) -> ET.Element:
    """Parse XML from an untrusted source.

    Uses ``defusedxml.ElementTree.fromstring`` which rejects entity
    expansion, external entity references, and DTD processing.

    Parameters
    ----------
    xml_data : str | bytes
        Raw XML content from an untrusted source such as a user-supplied
        ``.dui`` package or a network response.

    Returns
    -------
    ET.Element
        Parsed XML root element.

    Raises
    ------
    defusedxml.DefusedXmlException
        If the document contains a dangerous construct (e.g. entity
        expansion).
    xml.etree.ElementTree.ParseError
        If the document is not well-formed XML.
    """
    return SafeET.fromstring(xml_data)
