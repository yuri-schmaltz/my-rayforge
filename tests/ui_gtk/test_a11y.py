# flake8: noqa: E402
"""Tests for accessibility helpers (rayforge.ui_gtk.shared.a11y).

Covers the pure-Python paths of the a11y module so the suite can
run on bare CI without PyGObject / Gtk installed. When gi is not
available, every test in this module is skipped — the real
exercises happen on workstations with GTK present.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest


# Try the real import first; on bare CI this will fail and the
# whole module will be skipped.
try:
    import rayforge.ui_gtk.shared.a11y as a11y_module
    HAS_A11Y = True
except Exception as exc:  # pragma: no cover - environment-dependent
    HAS_A11Y = False
    _SKIP_REASON = f"a11y module not importable: {exc}"


pytestmark = pytest.mark.skipif(
    not HAS_A11Y,
    reason=locals().get("_SKIP_REASON", "a11y module not importable"),
)


# A small fake Gtk namespace to back the helper functions when
# the real one is present but we want to control its return
# values. Each test installs a fresh MagicMock on a11y_module.Gtk
# so tests don't leak state.
@pytest.fixture
def fake_gtk(monkeypatch):
    """Replace a11y_module.Gtk with a MagicMock for this test."""
    fake = MagicMock()
    # Make the enum lookups that a11y does (getattr) return
    # distinct sentinel values so we can assert they were used.
    fake.StackTransitionType.CROSSFADE = "STACK_CROSSFADE"
    fake.RevealerTransitionType.NONE = "REVEALER_NONE"
    monkeypatch.setattr(a11y_module, "Gtk", fake)
    return fake


# ---- prefers_reduced_motion ----


def test_prefers_reduced_motion_false_when_animations_enabled(fake_gtk):
    """gtk-enable-animations=True -> prefers_reduced_motion() is False."""
    settings = MagicMock(get_property=MagicMock(return_value=True))
    fake_gtk.Settings.get_default.return_value = settings
    assert a11y_module.prefers_reduced_motion() is False


def test_prefers_reduced_motion_true_when_animations_disabled(fake_gtk):
    """gtk-enable-animations=False -> prefers_reduced_motion() is True."""
    settings = MagicMock(get_property=MagicMock(return_value=False))
    fake_gtk.Settings.get_default.return_value = settings
    assert a11y_module.prefers_reduced_motion() is True


def test_prefers_reduced_motion_handles_no_settings(fake_gtk):
    """When Settings.get_default() returns None, helper returns False
    (no display or running headless)."""
    fake_gtk.Settings.get_default.return_value = None
    assert a11y_module.prefers_reduced_motion() is False


def test_prefers_reduced_motion_handles_missing_property(fake_gtk):
    """Older Gtk builds may not expose 'gtk-enable-animations'.
    Helper should catch and return False rather than raise."""
    settings = MagicMock()
    settings.get_property.side_effect = TypeError("no such property")
    fake_gtk.Settings.get_default.return_value = settings
    assert a11y_module.prefers_reduced_motion() is False


# ---- apply_motion_preference_recursive ----


def test_apply_motion_noop_when_motion_not_reduced(fake_gtk):
    """When prefers_reduced_motion() is False, the walker is a
    no-op. The Stack in the tree should not be touched."""
    fake_gtk.Settings.get_default.return_value = MagicMock(
        get_property=MagicMock(return_value=True)  # animations enabled
    )
    stack = MagicMock(spec=fake_gtk.Stack)
    a11y_module.apply_motion_preference_recursive(stack)
    # No set_transition_* calls when the user wants animations.
    assert not stack.set_transition_type.called
    assert not stack.set_transition_duration.called


def test_apply_motion_zeroes_stack_transitions(fake_gtk):
    """When prefers_reduced_motion() is True, every Gtk.Stack in
    the tree has its transition type set to CROSSFADE and its
    duration set to 0."""
    fake_gtk.Settings.get_default.return_value = MagicMock(
        get_property=MagicMock(return_value=False)  # animations off
    )
    # is_stack_type check: instance(stack, Gtk.Stack) is True
    # for our MagicMock(spec=Gtk.Stack). Mock the isinst check
    # via the a11y module's own isinstance usage by patching
    # Gtk.Stack/StackTransitionType/...
    stack = MagicMock()
    # Make isinstance(stack, Gtk.Stack) return True. Easiest
    # way: assign the spec class explicitly.
    stack.__class__ = fake_gtk.Stack
    child = MagicMock()
    stack.get_first_child.return_value = None
    a11y_module.apply_motion_preference_recursive(stack)
    # The helper should have set CROSSFADE + 0 duration on the stack.
    # (Calls may be split across _kill_motion_on; we just verify
    # both were invoked at least once.)
    assert stack.set_transition_type.called
    assert stack.set_transition_duration.called
    # And the duration should be 0 (the actual value we want).
    _, kwargs = stack.set_transition_duration.call_args
    assert stack.set_transition_duration.call_args.args == (0,)


def test_apply_motion_walks_tree_recursively(fake_gtk):
    """The helper visits every descendant, not just the root."""
    fake_gtk.Settings.get_default.return_value = MagicMock(
        get_property=MagicMock(return_value=False)
    )
    # Build a 2-level tree: root -> child_a, child_b; child_a -> grandchild.
    root = MagicMock()
    child_a = MagicMock()
    child_b = MagicMock()
    grandchild = MagicMock()
    # Wire the tree.
    root.get_first_child.return_value = child_a
    child_a.get_next_sibling.return_value = child_b
    child_b.get_next_sibling.return_value = None
    child_a.get_first_child.return_value = grandchild
    grandchild.get_next_sibling.return_value = None
    child_b.get_first_child.return_value = None
    # None of them are Stack/Revealer (spec set to a plain MagicMock).
    a11y_module.apply_motion_preference_recursive(root)
    # The walker should have visited every node (get_first_child
    # is called on each).
    assert root.get_first_child.called
    assert child_a.get_first_child.called
    assert child_b.get_first_child.called
    assert grandchild.get_next_sibling.called


# ---- install_motion_preference_listener ----


def test_install_listener_is_idempotent(fake_gtk):
    """Calling install_motion_preference_listener twice on the same
    window must not register a second Gtk.Settings callback."""
    settings = MagicMock()
    fake_gtk.Settings.get_default.return_value = settings
    window = MagicMock()
    # Simulate a prior install by pre-marking the marker.
    window._motion_listener_installed = True
    a11y_module.install_motion_preference_listener(window)
    # The second call must NOT have connected to Settings.
    assert not settings.connect.called


def test_install_listener_connects_and_applies(fake_gtk):
    """First call connects to 'notify::gtk-enable-animations' on
    Gtk.Settings and runs the initial pass over the window's
    widget tree."""
    settings = MagicMock()
    fake_gtk.Settings.get_default.return_value = settings
    window = MagicMock()
    # Make sure the window has no prior marker.
    del window._motion_listener_installed  # safe-delete via try/except
    a11y_module.install_motion_preference_listener(window)
    assert settings.connect.called
    # The connect call's first arg should be the property name.
    args, _ = settings.connect.call_args
    assert args[0] == "notify::gtk-enable-animations"
    # And the marker should be set so a second call is a no-op.
    assert getattr(window, "_motion_listener_installed", False) is True
    # And the window's children should have been walked once
    # during the initial pass.
    assert window.get_first_child.called


def test_install_listener_handles_no_settings(fake_gtk):
    """When Gtk.Settings.get_default() returns None, the helper
    logs a debug message and returns without raising."""
    fake_gtk.Settings.get_default.return_value = None
    window = MagicMock()
    a11y_module.install_motion_preference_listener(window)
    # No crash, no connect call, no marker set on the window.
    assert not getattr(window, "_motion_listener_installed", False)
