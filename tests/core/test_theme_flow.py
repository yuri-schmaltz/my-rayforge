# flake8: noqa: E402
"""Tests for the theme configuration flow.

The end-to-end flow is:
  1. Config.set_theme(value) updates self.theme and emits 'changed'.
  2. The 'changed' signal is wired to MainWindow.on_config_changed.
  3. on_config_changed calls apply_theme, which maps the
     config string to an Adw.ColorScheme and applies it.

These tests exercise step 1 and the config persistence side of
the flow. Step 2-3 require a live MainWindow and a Gtk display
and is covered by manual smoke testing on a workstation.

The to_dict / from_dict round-trip is also tested, because it's
the public persistence contract the user relies on for the
'light theme persists across restarts' guarantee made in PR4.
"""
import logging

import pytest


logger = logging.getLogger(__name__)


def test_theme_default_is_system():
    """A fresh Config has theme='system' so the UI follows the
    OS preference out of the box."""
    from rayforge.core.config import Config

    cfg = Config()
    assert cfg.theme == "system"


def test_set_theme_updates_value_and_emits_signal():
    """Config.set_theme(value) updates self.theme and emits
    exactly one 'changed' signal (when the value actually changes).
    """
    from rayforge.core.config import Config
    from blinker import Signal

    cfg = Config()
    cfg.theme = "dark"  # Start from a non-default to detect no-op.

    received = []

    def on_changed(sender):
        received.append(sender.theme)

    cfg.changed.connect(on_changed)
    cfg.set_theme("light")
    assert cfg.theme == "light"
    assert received == ["light"], (
        f"Expected one 'changed' signal with new value, got {received!r}"
    )


def test_set_theme_same_value_does_not_emit():
    """Calling set_theme with the current value is a no-op:
    self.theme stays the same AND no 'changed' signal fires.

    This matters because the wiring in on_config_changed would
    call apply_theme() on every 'changed', which is wasteful
    for redundant updates (e.g. a UI control fires 'selected'
    on every render even when the value didn't change).
    """
    from rayforge.core.config import Config

    cfg = Config()
    cfg.theme = "light"

    received = []

    def on_changed(sender):
        received.append(sender.theme)

    cfg.changed.connect(on_changed)
    cfg.set_theme("light")  # same value
    assert cfg.theme == "light"
    assert received == [], (
        f"Expected no 'changed' signal, got {received!r}"
    )


def test_theme_to_dict_roundtrip():
    """Config.to_dict includes 'theme' and the round-trip
    via from_dict preserves it. This is the persistence path
    that survives a restart.
    """
    from rayforge.core.config import Config

    cfg = Config()
    cfg.theme = "light"
    data = cfg.to_dict()
    assert data["theme"] == "light"

    # Round-trip: build a new Config from the dict and verify
    # theme is restored. from_dict also requires a machine
    # lookup callable; we pass a stub that returns None since
    # this test doesn't exercise machine loading.
    cfg2 = Config.from_dict(data, get_machine_by_id=lambda _id: None)
    assert cfg2.theme == "light"


def test_theme_from_dict_defaults_to_system_when_missing():
    """Old config.yaml files written before the theme feature
    existed don't have a 'theme' key. from_dict must default
    to 'system' in that case, not raise.
    """
    from rayforge.core.config import Config

    data = {}  # No 'theme' key.
    cfg = Config.from_dict(data, get_machine_by_id=lambda _id: None)
    assert cfg.theme == "system"


def test_theme_supported_values_accepted():
    """set_theme must accept the three documented values: 'system',
    'light', 'dark'. Anything else is stored as-is (the runtime
    apply_theme() is defensive and falls back to DEFAULT for any
    unknown value, see MainWindow.apply_theme).
    """
    from rayforge.core.config import Config

    cfg = Config()
    for value in ("system", "light", "dark"):
        cfg.set_theme(value)
        assert cfg.theme == value

    # Unknown value: stored verbatim. The apply layer is the one
    # that decides what to do with it.
    cfg.set_theme("high-contrast")
    assert cfg.theme == "high-contrast"
