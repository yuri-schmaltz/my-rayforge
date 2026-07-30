"""
Security regression tests for XML parsing in LightBurn files.

LightBurn ``.lbrn`` files are XML. A malicious file could carry:
- Billion-laughs / quadratic blowup (DoS via entity expansion)
- External entity (XXE) attacks that exfiltrate local files
- DTD-based network fetches (SSRF)

``defusedxml.ElementTree`` blocks all of these by default. These
tests pin that behaviour: an attack-vector ``.lbrn`` must either be
rejected outright at parse time, or — when surfaced through the
``LightBurnImporter`` public API — produce a user-friendly error
in the import manifest rather than a stack trace.
"""

from pathlib import Path

import defusedxml.common
import defusedxml.ElementTree
import pytest

from rayforge.image.lightburn.importer import LightBurnImporter


# A billion-laughs attack: nested entity expansion that consumes
# exponential memory. With defusedxml, this is rejected at parse
# time; without it, this would allocate gigabytes of memory.
BILLION_LAUGHS_XML = """\
<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
<LightBurnLibrary>&lol4;</LightBurnLibrary>
"""


# An XXE attack that tries to read a local file via external entity.
# The DTD declares ``SYSTEM "file:///etc/passwd"`` and references it.
XXE_FILE_READ_XML = """\
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ELEMENT foo ANY>
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<LightBurnLibrary>&xxe;</LightBurnLibrary>
"""


class TestLightBurnXmlHardening:
    """
    These tests verify that the LightBurn importer rejects XML
    attack vectors. With stdlib ``xml.etree.ElementTree``, the
    billion-laughs attack would hang the process and the XXE attack
    would embed ``/etc/passwd`` in the parsed document.
    """

    def test_billion_laughs_blocked_by_defusedxml(self):
        # defusedxml raises ``EntitiesForbidden`` (a subclass of
        # ``ParseError``) when entity expansion is attempted.
        with pytest.raises(defusedxml.common.EntitiesForbidden):
            defusedxml.ElementTree.fromstring(BILLION_LAUGHS_XML)

    def test_xxe_file_read_blocked_by_defusedxml(self):
        # defusedxml also raises ``EntitiesForbidden`` for SYSTEM
        # external entities pointing to local files.
        with pytest.raises(defusedxml.common.EntitiesForbidden):
            defusedxml.ElementTree.fromstring(XXE_FILE_READ_XML)

    def test_lbrn_importer_scan_rejects_billion_laughs_gracefully(self):
        """
        End-to-end: the ``LightBurnImporter.scan()`` method must
        catch the ``DefusedXmlError`` raised by ``defusedxml`` and
        return a manifest with a user-friendly error message — not
        propagate the exception.
        """
        importer = LightBurnImporter(
            data=BILLION_LAUGHS_XML.encode("utf-8"),
            source_file=Path("attack.lbrn"),
        )
        # ``scan()`` must NOT raise — it should report the error
        # in the manifest.
        manifest = importer.scan()
        assert manifest is not None
        assert any(
            "invalid xml" in e.lower() or "defused" in e.lower()
            for e in manifest.errors
        ), f"Expected invalid-XML error, got: {manifest.errors}"

    def test_lbrn_importer_parse_rejects_xxe_gracefully(self):
        importer = LightBurnImporter(
            data=XXE_FILE_READ_XML.encode("utf-8"),
            source_file=Path("attack.lbrn"),
        )
        # ``parse()`` must NOT raise — it should return None and
        # record the error in ``_errors``.
        result = importer.parse()
        assert result is None
        assert any(
            "corrupt" in e.lower() or "invalid" in e.lower()
            for e in importer._errors
        ), f"Expected corrupt error, got: {importer._errors}"

    def test_lbrn_importer_uses_defusedxml_not_stdlib(self):
        """
        Regression guard: a future refactor must not silently
        regress to the stdlib ``xml.etree.ElementTree``.

        We import both modules and check that the importer does
        NOT use the stdlib parser. The check is on the parser
        class identity.
        """
        from rayforge.image.lightburn import importer as lb_importer

        # The defusedxml ``ElementTree`` is a different module
        # from stdlib ``xml.etree.ElementTree``. We confirm the
        # import that ``importer.py`` did is the defused one.
        assert lb_importer.ET.__name__ in (
            "defusedxml.ElementTree",
            "defusedxml",
        ), (
            f"importer.py uses {lb_importer.ET.__name__!r} — must "
            "be defusedxml.ElementTree to protect against XML attacks"
        )
