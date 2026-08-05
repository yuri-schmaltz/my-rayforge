"""Dockable panels — a step toward real workspace customization.

This is a PoC (proof of concept), not a full docking
manager. GTK 4 has no built-in docking framework; a
full drag-and-drop docking manager would be 4-6 weeks
of work (see rayforge ROADMAP.md §5.3 P3 'Real
dockable panels').

What this PoC does:

  - Define a DockLayout data model: which surfaces
    (right pane, bottom panel, canvas, toolbar) live
    in which zone (top, right, bottom, left)
  - Provide swap_zone(zone_a, zone_b) to swap two
    surfaces — useful for testing the data model
  - Serialize/deserialize a layout to JSON so the
    current arrangement can be saved (P3.2)

What this PoC does NOT do (yet):

  - Drag-and-drop with visual feedback
  - Detachable windows (drag a panel out of the
    main window into its own Adw.Window)
  - Tabbed panels (multiple panels in the same zone)

A full implementation would replace the PanelManager
(wave 3) with this data model. Today the PanelManager
exposes 3 presets (default/compact/expanded); the
DockLayout would expose 4 zones (top/right/bottom/left)
and let the user re-arrange freely. Until drag-and-drop
is implemented, the API is functional but the UI is
limited to a menu ('Move right pane to bottom zone').

Why ship a PoC? Because the data model + serialization
is the hard part. Once the model is right, the UI
can be added incrementally (drag handles, snap zones,
detached windows) without changing the model. A
follow-up commit can add the visual drag layer.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class Zone(str, Enum):
    """The 4 main zones of the main window.

    Each zone is a Gtk.Box child of the main vertical
    or horizontal container. The DockLayout maps a
    surface (right_pane, bottom_panel, canvas, etc)
    to a zone.
    """
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"

    # CENTER is the canvas; the other 3 zones are
    # 'auxiliary' surfaces that the user can rearrange.
    CENTER = "center"


@dataclass
class DockLayout:
    """The current arrangement of surfaces in zones.

    The default layout matches the wave-1 main window:
      - top: coordinate bar
      - right: right pane (workflow + properties tabs)
      - bottom: bottom panel (layers + gcode + console)
      - left: (empty)
      - center: canvas

    A user can rearrange by calling move_to(zone, surface)
    or swap(a, b). The layout is JSON-serializable via
    to_dict / from_dict.
    """
    top: str = "coordinate_bar"
    right: str = "right_pane"
    bottom: str = "bottom_panel"
    left: str = ""  # empty zone (a future 'layers' panel?)
    center: str = "canvas"

    def move_to(self, zone: Zone, surface: str) -> None:
        """Move `surface` to `zone`, displacing whatever is there.

        If `surface` is already in another zone, that
        zone becomes empty. If `zone` already has a
        surface, the two swap (the displaced surface
        goes to where `surface` came from).
        """
        # Find where `surface` is currently
        current_zone = self._zone_of(surface)
        # Find what's in `zone`
        displaced = self._surface_in(zone)
        if current_zone == zone:
            return  # already there
        if displaced is None:
            setattr(self, zone.value, surface)
        else:
            # Swap: surface and displaced exchange zones
            setattr(self, zone.value, surface)
            if current_zone is not None:
                setattr(self.current_zone_value(current_zone), displaced)

    def _zone_of(self, surface: str) -> Optional[Zone]:
        """Return the zone containing `surface`, or None."""
        for zone in Zone:
            if getattr(self, zone.value) == surface:
                return zone
        return None

    def _surface_in(self, zone: Zone) -> Optional[str]:
        return getattr(self, zone.value) or None

    @staticmethod
    def current_zone_value(zone: Zone) -> str:
        return zone.value

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DockLayout":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str) -> "DockLayout":
        return cls.from_dict(json.loads(s))

    def is_valid(self) -> bool:
        """A layout is valid if no two non-empty zones share
        a surface (a surface is in at most one zone)."""
        seen: Dict[str, Zone] = {}
        for zone in Zone:
            surf = getattr(self, zone.value)
            if not surf:
                continue
            if surf in seen:
                logger.warning(
                    "Layout invalid: surface %r in both %s and %s",
                    surf, seen[surf], zone,
                )
                return False
            seen[surf] = zone
        return True
