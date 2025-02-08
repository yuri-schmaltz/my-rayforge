from __future__ import annotations
import cairo
import gi
from copy import deepcopy
from dataclasses import dataclass, field
from blinker import Signal

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Graphene  # noqa: E402


@dataclass
class CanvasElement:
    x_mm: float  # Relative to parent (or canvas if top-level)
    y_mm: float  # Relative to parent (or canvas if top-level)
    width_mm: float  # Real-world width in mm
    height_mm: float  # Real-world height in mm
    selected: bool = False
    selectable: bool = True
    visible: bool = True
    crop_region_mm: tuple[float, float, float, float|None] = 0, 0, None, None
    surface: cairo.Surface = None
    canvas: object = None
    parent: object = None
    children: list = field(default_factory=list)
    background: (float, float, float, float) = 0, 0, 0, 0
    data: object = None

    def get_pixels_per_mm(self):
        return self.canvas.pixels_per_mm_x, \
               self.canvas.pixels_per_mm_y

    def copy(self):
        return deepcopy(self)

    def add(self, elem):
        self.children.append(elem)
        elem.canvas = self.canvas
        elem.parent = self
        elem.allocate()

    def find_by_data(self, data):
        if data == self.data:
            return self
        for child in self.children:
            result = child.find_by_data(data)
            if result:
                return result
        return None

    def clear(self):
        children = self.children
        self.children = []
        for child in children:
            self.canvas.elem_removed.send(self, child=child)

    def remove(self):
        assert self.parent is not None
        self.parent.remove_child(self)

    def remove_child(self, elem):
        """
        Not recursive.
        """
        for child in self.children[:]:
            if child == elem:
                self.children.remove(child)
                self.canvas.elem_removed.send(self, child=child)

    def remove_selected(self):
        for child in self.children[:]:
            if child.selected:
                self.children.remove(child)
                self.canvas.elem_removed.send(self, child=child)
            child.remove_selected()

    def unselect_all(self):
        for child in self.children:
            child.unselect_all()
        self.selected = False

    def get_max_child_size(self, aspect_ratio):
        """
        Returns the maximum size for a child with the given
        aspect ratio.
        """
        width_mm = self.width_mm
        height_mm = width_mm/aspect_ratio
        if height_mm > self.height_mm:
            height_mm = self.height_mm
            width_mm = height_mm*aspect_ratio
        return width_mm, height_mm

    def pos(self):
        return self.x_mm, self.y_mm

    def pos_px(self):
        pixels_per_mm_x, pixels_per_mm_y = self.get_pixels_per_mm()
        return self.x_mm*pixels_per_mm_x, self.y_mm*pixels_per_mm_y

    def pos_abs(self):
        parent_x, parent_y = 0, 0
        if isinstance(self.parent, CanvasElement):
            parent_x, parent_y = self.parent.pos_abs()
        return self.x_mm+parent_x, self.y_mm+parent_y

    def pos_abs_px(self):
        pixels_per_mm_x, pixels_per_mm_y = self.get_pixels_per_mm()
        x_mm, y_mm = self.pos_abs()
        return x_mm*pixels_per_mm_x, y_mm*pixels_per_mm_y

    def size(self):
        return self.width_mm, self.height_mm

    def set_size(self, width_mm, height_mm):
        self.width_mm, self.height_mm = width_mm, height_mm

    def crop(self, x_mm, y_mm, width_mm, height_mm):
        x_mm = 0 if x_mm is None or x_mm <= 0 else x_mm
        y_mm = 0 if y_mm is None or y_mm <= 0 else y_mm
        width_mm = None if width_mm is None or width_mm >= self.width_mm \
                        else width_mm
        height_mm = None if height_mm is None or height_mm >= self.height_mm \
                        else height_mm

        self.crop_region_mm = x_mm, y_mm, width_mm, height_mm
        width_mm = self.width_mm if width_mm is None else width_mm
        height_mm = self.height_mm if height_mm is None else height_mm

    def size_px(self):
        pixels_per_mm_x, pixels_per_mm_y = self.get_pixels_per_mm()
        return (int(self.width_mm*pixels_per_mm_x),
                int(self.height_mm*pixels_per_mm_y))

    def crop_region_px(self):
        pixels_per_mm_x, pixels_per_mm_y = self.get_pixels_per_mm()
        x_mm, y_mm, width_mm, height_mm = self.crop_region_mm
        width_mm = width_mm if width_mm is not None else self.width_mm
        height_mm = height_mm if height_mm is not None else self.height_mm
        return (int(x_mm*pixels_per_mm_x),
                int(y_mm*pixels_per_mm_y),
                int(width_mm*pixels_per_mm_x),
                int(height_mm*pixels_per_mm_y))

    def rect(self):
        return self.x_mm, self.y_mm, self.width_mm, self.height_mm

    def rect_abs(self):
        x_mm, y_mm = self.pos_abs()
        return x_mm, y_mm, self.width_mm, self.height_mm

    def rect_px(self):
        px_mm_x, px_mm_y = self.get_pixels_per_mm()
        return (self.x_mm*px_mm_x,
                self.y_mm*px_mm_y,
                self.width_mm*px_mm_x,
                self.height_mm*px_mm_y)

    def get_aspect_ratio(self):
        return self.width_mm / self.height_mm

    def allocate(self):
        if not self.canvas:
            return  # cannot allocate if i don't know pixels per mm

        _, _, width, height = self.crop_region_px()

        for child in self.children:
            child.allocate()

        # If the size didn't change, do nothing.
        if self.surface \
                and self.surface.get_width() == width \
                and self.surface.get_height() == height:
            return

        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)

    def _rect_to_child_coords_px(self, child, rect_px):
        x, y, w, h = rect_px
        child_x, child_y, child_w, child_h = child.rect_px()
        return x-child_x, y-child_y, w, h

    def render(self, clip=None):
        """
        clip: x, y, w, h. the region to render
        """
        if clip is None:
            clip = self.rect_px()

        # Paint background
        x, y, w, h = clip
        ctx = cairo.Context(self.surface)
        ctx.rectangle(0, 0, x+w, y+h)
        ctx.clip()
        ctx.save()
        ctx.set_source_rgba(*self.background)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.paint()
        ctx.restore()

        # Paint children
        for child in self.children:
            child.render(self._rect_to_child_coords_px(child, clip))
            if child.visible:
                ctx.set_source_surface(child.surface, *child.pos_px())
                ctx.paint()

    def get_elem_hit(self, x_mm, y_mm, selectable=False):
        """
        Check if the point (x_mm, y_mm) hits this elem or any of its children.
        If selectable is True, only selectable elems are considered.
        """
        # Check children (child-to-parent order)
        for child in reversed(self.children):
            # Translate the coordinates to the child's local coordinate system
            child_x_mm = x_mm - child.x_mm
            child_y_mm = y_mm - child.y_mm
            hit = child.get_elem_hit(child_x_mm, child_y_mm, selectable)
            if hit:
                return hit

        if selectable and not self.selectable:
            return None

        # Check if the point is within the elem's bounds
        if 0 <= x_mm <= self.width_mm and 0 <= y_mm <= self.height_mm:
            return self

        return None

    def dump(self, indent=0):
        print("  "*indent,
              self.__class__.__name__,
              "SIZE", self.rect(),
              "CROP", self.crop_region_mm)
        print("  "*indent,
              " "*len(self.__class__.__name__),
              "SIZEPX", self.rect_px(),
              "CROPPX", self.crop_region_px())
        for child in self.children:
            child.dump(indent+1)


class Canvas(Gtk.DrawingArea):
    def __init__(self, width_mm=100, height_mm=100, **kwargs):
        super().__init__(**kwargs)
        self.root = CanvasElement(0,
                                  0,
                                  width_mm,
                                  height_mm,
                                  canvas=self,
                                  parent=self)
        self.pixels_per_mm_x = 1  # Updated in do_size_allocate()
        self.pixels_per_mm_y = 1  # Updated in do_size_allocate()
        self.handle_size = 10   # Resize handle size
        self.active_elem = None
        self.active_rect = None, None, None, None
        self._setup_interactions()

    def add(self, elem):
        self.root.add(elem)

    def remove(self, elem):
        self.root.remove(elem)

    def find_by_data(self, data):
        """
        Returns the CanvasElement with the given data, or None if none
        was found.
        """
        return self.root.find_by_data(data)

    def _setup_interactions(self):
        self.click_gesture = Gtk.GestureClick()
        self.click_gesture.connect("pressed", self.on_button_press)
        self.add_controller(self.click_gesture)

        self.drag_gesture = Gtk.GestureDrag()
        self.drag_gesture.connect("drag-update", self.on_mouse_drag)
        self.drag_gesture.connect("drag-end", self.on_button_release)
        self.add_controller(self.drag_gesture)
        self.resizing = False
        self.moving = False

        self.key_controller = Gtk.EventControllerKey.new()
        self.key_controller.connect("key-pressed", self.on_key_pressed)
        self.key_controller.connect("key-released", self.on_key_released)
        self.add_controller(self.key_controller)
        self.shift_pressed = False
        self.set_focusable(True)
        self.grab_focus()

        self.elem_removed = Signal()

    def do_size_allocate(self, width: int, height: int, baseline: int):
        self.pixels_per_mm_x = width/self.root.width_mm
        self.pixels_per_mm_y = height/self.root.height_mm
        self.root.allocate()

    def do_snapshot(self, snapshot):
        width, height = self.get_width(), self.get_height()
        bounds = Graphene.Rect().init(0, 0, width, height)

        self.root.render()
        ctx = snapshot.append_cairo(bounds)
        ctx.set_source_surface(self.root.surface, *self.root.pos_px())
        ctx.paint()

        self._render_selection(ctx, self.root, 0, 0)

    def _render_selection(self, ctx, elem, parent_x_mm, parent_y_mm):
        # Calculate absolute position of the elem
        absolute_x_mm = parent_x_mm + elem.x_mm
        absolute_y_mm = parent_y_mm + elem.y_mm
        elem_x = absolute_x_mm * self.pixels_per_mm_x
        elem_y = absolute_y_mm * self.pixels_per_mm_y
        target_width = elem.width_mm * self.pixels_per_mm_x
        target_height = elem.height_mm * self.pixels_per_mm_y

        # Draw rectangle around selected elems
        if elem.selected:
            ctx.save()
            ctx.set_source_rgb(.4, .4, .4)
            ctx.set_dash((5, 5))
            ctx.rectangle(elem_x, elem_y, target_width, target_height)
            ctx.stroke()
            ctx.restore()

        # Draw resize handle
        if elem == self.active_elem:
            ctx.save()
            ctx.set_source_rgb(.4, .4, .4)
            ctx.set_line_width(1)
            handle_x = elem_x + target_width
            handle_y = elem_y + target_height
            ctx.rectangle(handle_x-self.handle_size/2,
                          handle_y-self.handle_size/2,
                          self.handle_size,
                          self.handle_size)
            ctx.stroke()
            ctx.restore()

        # Recursively render children
        for child in elem.children:
            self._render_selection(ctx, child, absolute_x_mm, absolute_y_mm)

    def get_elem_handle_hit(self, elem, x_mm, y_mm, selectable=True):
        for child in elem.children:
            child_x_mm = x_mm-elem.x_mm
            child_y_mm = y_mm-elem.y_mm
            hit = self.get_elem_handle_hit(child,
                                           child_x_mm,
                                           child_y_mm,
                                           selectable=True)
            if hit:
                return hit
        if selectable and not elem.selectable:
            return
        if not elem.selected:
            return None
        handle_x1 = elem.x_mm+elem.width_mm-self.handle_size/2
        handle_x2 = handle_x1+self.handle_size
        handle_y1 = elem.y_mm+elem.height_mm-self.handle_size/2
        handle_y2 = handle_y1+self.handle_size
        if handle_x1 <= x_mm <= handle_x2 and handle_y1 <= y_mm <= handle_y2:
            return elem
        return None

    def on_button_press(self, gesture, n_press, x, y):
        self.grab_focus()

        x_mm = x/self.pixels_per_mm_x
        y_mm = y/self.pixels_per_mm_y

        hit = self.get_elem_handle_hit(self.root, x_mm, y_mm, selectable=True)

        self.root.unselect_all()

        if hit and hit != self.root:
            hit.selected = True
            self.resizing = True
            self.active_elem = hit
            self.active_origin = hit.rect()
            self.queue_draw()
            return

        hit = self.root.get_elem_hit(x_mm, y_mm, selectable=True)
        if hit and hit != self.root:
            hit.selected = True
            self.moving = True
            self.active_elem = hit
            self.active_origin = hit.rect()
            self.queue_draw()
            return

        self.active_elem = None
        self.queue_draw()

    def on_mouse_drag(self, gesture, x, y):
        if not self.active_elem:
            return

        start_x_mm, start_y_mm, start_w_mm, start_h_mm = self.active_origin
        delta_x_mm = x/self.pixels_per_mm_x
        delta_y_mm = y/self.pixels_per_mm_y

        if self.moving:
            self.active_elem.x_mm = start_x_mm+delta_x_mm
            self.active_elem.y_mm = start_y_mm+delta_y_mm

        if self.resizing:
            new_w_mm = max(self.handle_size, start_w_mm+delta_x_mm)
            new_w_mm = min(new_w_mm, self.active_elem.parent.width_mm)
            self.active_elem.width_mm = new_w_mm
            if self.shift_pressed:
                aspect = start_w_mm/start_h_mm
                self.active_elem.height_mm = new_w_mm/aspect
            else:
                new_h_mm = max(self.handle_size, start_h_mm+delta_y_mm)
                new_h_mm = min(new_h_mm, self.active_elem.parent.height_mm)
                self.active_elem.height_mm = new_h_mm
            self.active_elem.allocate()

        self.queue_draw()

    def on_button_release(self, gesture, x, y):
        self.resizing = False
        self.moving = False

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Shift_L or keyval == Gdk.KEY_Shift_R:
            self.shift_pressed = True
        elif keyval == Gdk.KEY_Delete:
            self.root.remove_selected()
            self.active_elem = None
            self.active_rect = None, None, None, None
            self.queue_draw()

    def on_key_released(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Shift_L or keyval == Gdk.KEY_Shift_R:
            self.shift_pressed = False


if __name__ == "__main__":
    class CanvasApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="com.example.CanvasApp")

        def do_activate(self):
            win = Gtk.ApplicationWindow(application=self)
            win.set_default_size(800, 800)
            canvas = Canvas(200, 200)
            win.set_child(canvas)
            group = CanvasElement(50, 50, 140, 130,
                                  background=(0, 1, 1, 1))
            group.add(CanvasElement(50, 50, 40, 30,
                                    background=(0, 0, 1, 1),
                                    selectable=False))
            group.add(CanvasElement(100, 100, 30, 30,
                                    background=(0, 1, 0, 1)))
            group.add(CanvasElement(50, 100, 50, 50,
                                    background=(1, 0, 1, 1)))
            canvas.add(group)
            win.present()

    app = CanvasApp()
    app.run([])
