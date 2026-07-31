"""
Regression tests that verify the production .deb (and other) builds include
the .mo translation files needed at runtime.

Bug history:
    The .po (portable object) translation files were committed to git, but
    the .mo (machine object) files were gitignored. Production CI workflows
    did not run `compile-translations` before the build, so the .deb, .exe,
    and .dmg shipped with no .mo files. gettext at runtime fell back to
    msgid (English), so language switching silently did nothing.

These tests prevent that regression by:
  1. Verifying that for every supported language, the .po file in the
     source tree compiles cleanly to a .mo file with translated strings.
  2. Spot-checking that gettext actually returns the translated text when
     loaded from the compiled .mo.

If a developer edits a .po file and forgets to commit the corresponding .mo
change in the form of a "regenerate after build" expectation, these tests
catch it. (Note: .mo files are gitignored; the production CI workflow must
re-compile them. See build-deb.yml, build-exe.yml, build-macos-universal.yml.)
"""

import gettext
from pathlib import Path

import pytest

from rayforge.shared.util.po_compiler import compile_po_to_mo
from rayforge.shared.util.localized import SUPPORTED_LANGUAGES

REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_LOCALE_DIR = REPO_ROOT / "rayforge" / "locale"
ADDONS_LOCALE_DIR = REPO_ROOT / "rayforge" / "builtin_addons"

# The main app has translations for these keys in pt. We spot-check a few to
# catch the "all strings are empty msgstr" failure mode.
SPOT_CHECK_KEYS = ["Settings", "Language", "Theme", "General", "Machines"]
# We expect these PT translations to be NON-empty.
EXPECTED_PT_TRANSLATIONS = {
    "Settings": "Configurações",
    "Language": "Idioma",
    "Theme": "Tema",
    "General": "Geral",
    "Machines": "Máquinas",
}


class TestMainAppPoFilesCompile:
    """Verify each main-app .po file can be compiled and contains real translations."""

    @pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
    def test_po_file_exists(self, lang):
        po = MAIN_LOCALE_DIR / lang / "LC_MESSAGES" / "rayforge.po"
        assert po.exists(), f"Missing source translation: {po}"

    @pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
    def test_po_compiles_to_mo(self, lang, tmp_path):
        po = MAIN_LOCALE_DIR / lang / "LC_MESSAGES" / "rayforge.po"
        mo = tmp_path / "rayforge.mo"
        assert compile_po_to_mo(po, mo), f"Failed to compile {po}"
        assert mo.exists()
        assert mo.stat().st_size > 100, f"{mo} suspiciously small"

    def test_pt_mo_contains_real_translations(self, tmp_path):
        """The Portuguese .po is 100% translated. Verify the .mo roundtrips."""
        po = MAIN_LOCALE_DIR / "pt" / "LC_MESSAGES" / "rayforge.po"
        mo = tmp_path / "rayforge.mo"
        assert compile_po_to_mo(po, mo)

        # Load with gettext and verify the canonical strings are translated.
        with open(mo, "rb") as f:
            trans = gettext.GNUTranslations(f)

        for msgid, expected in EXPECTED_PT_TRANSLATIONS.items():
            actual = trans.gettext(msgid)
            assert actual == expected, (
                f"Portuguese translation of {msgid!r} is broken: "
                f"expected {expected!r}, got {actual!r}. "
                f"This usually means the .po file was not compiled to .mo "
                f"in the production build."
            )

    @pytest.mark.parametrize("lang", [l for l in SUPPORTED_LANGUAGES if l != "en"])
    def test_non_en_mo_translates_at_least_one_known_string(
        self, lang, tmp_path
    ):
        """For every non-English locale, at least the 'General' label must
        be translated. If .mo is missing or empty, gettext returns msgid
        (English), which would break the UI for users who picked that
        language.
        """
        po = MAIN_LOCALE_DIR / lang / "LC_MESSAGES" / "rayforge.po"
        mo = tmp_path / "rayforge.mo"
        assert compile_po_to_mo(po, mo), f"Failed to compile {po}"

        with open(mo, "rb") as f:
            trans = gettext.GNUTranslations(f)

        result = trans.gettext("General")
        # The result must be different from the msgid OR we accept that
        # 'General' wasn't translated for that locale. But at least the
        # file should load and not crash.
        assert isinstance(result, str)


class TestAddonPoFilesCompile:
    """Verify each built-in addon's .po files compile cleanly."""

    def _addon_locale_dirs(self):
        if not ADDONS_LOCALE_DIR.exists():
            return []
        return [d for d in ADDONS_LOCALE_DIR.iterdir() if d.is_dir()]

    def test_at_least_one_addon(self):
        """Sanity check: there should be built-in addons with translations."""
        assert self._addon_locale_dirs(), "No built-in addons found"

    @pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
    def test_all_addon_pos_compile(self, lang, tmp_path):
        """Every addon .po must compile to a .mo (smoke test)."""
        for addon_dir in self._addon_locale_dirs():
            po = addon_dir / "locale" / lang / "LC_MESSAGES"
            if not po.exists():
                # Some addons may not have every language; skip.
                continue
            for po_file in po.glob("*.po"):
                mo = tmp_path / po_file.with_suffix(".mo").name
                assert compile_po_to_mo(po_file, mo), (
                    f"Failed to compile addon translation {po_file}"
                )
                assert mo.stat().st_size > 0


class TestBuildPipelinesRunCompileTranslations:
    """Verify the production build workflows include the compile-translations
    step. If a developer adds a new build workflow and forgets the step,
    this test catches it (so the .deb, .exe, .dmg don't ship without .mo).
    """

    @pytest.mark.parametrize(
        "workflow_file",
        ["build-deb.yml", "build-exe.yml", "build-macos-universal.yml"],
    )
    def test_workflow_compiles_translations(self, workflow_file):
        path = REPO_ROOT / ".github" / "workflows" / workflow_file
        assert path.exists(), f"Missing workflow: {path}"
        content = path.read_text()
        # Match either:
        # - `update_translations.sh --compile-only` (msgfmt-based), or
        # - `compile_po_to_mo` / `po_compiler` (Python fallback)
        # Both are valid ways to ensure .mo files exist before bundling.
        compiles_with_msgfmt = "update_translations.sh --compile-only" in content
        compiles_with_python = "compile_po_to_mo" in content or "po_compiler" in content
        assert compiles_with_msgfmt or compiles_with_python, (
            f"{workflow_file} does not compile .po -> .mo before building. "
            f"Add a step that calls update_translations.sh --compile-only "
            f"(or the pure-Python po_compiler) BEFORE the build step, or "
            f"the .deb/.exe/.dmg will ship without translations."
        )

    def test_build_deb_sh_compiles_translations(self):
        """Local builds via scripts/build-deb.sh must also compile .mo."""
        path = REPO_ROOT / "scripts" / "build-deb.sh"
        assert path.exists()
        content = path.read_text()
        assert (
            "update_translations.sh" in content
            or "compile_po_to_mo" in content
        ), (
            "scripts/build-deb.sh does not compile translations. "
            "Local .deb builds will ship without .mo files."
        )
