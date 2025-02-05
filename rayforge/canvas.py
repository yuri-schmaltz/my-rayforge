from __future__ import annotations
import cairo
import gi
from copy import deepcopy
from dataclasses import dataclass, field

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Graphene  # noqa: E402


@dataclass
class CanvasItem:
    name: str
    x_mm: float  # Relative to parent (or canvas if top-level)
    y_mm: float  # Relative to parent (or canvas if top-level)
    width_mm: float  # Real-world width in mm
    height_mm: float  # Real-world height in mm
    selected: bool = False
    selectable: bool = True
    surface: cairo.Surface = None
    parent: object = None
    children: list = field(default_factory=list)
    background: (float, float, float, float) = 0, 0, 0, 0

    def get_canvas(self):
        if isinstance(self.parent, CanvasItem):
            return self.parent.get_canvas()
        return self.parent

    def get_pixels_per_mm(self):
        return self.get_canvas().pixels_per_mm_x, \
               self.get_canvas().pixels_per_mm_y

    def copy(self):
        return deepcopy(self)

    def add(self, item):
        self.children.append(item)
        item.parent = self
        item.allocate()

    def remove_selected(self):
        self.children = [i for i in self.children if not i.selected]

    def unselect_all(self):
        for child in self.children:
            child.unselect_all()
        self.selected = False

    def pos(self):
        return self.x_mm, self.y_mm

    def pos_px(self):
        pixels_per_mm_x, pixels_per_mm_y = self.get_pixels_per_mm()
        return self.x_mm*pixels_per_mm_x, self.y_mm*pixels_per_mm_y

    def pos_abs(self):
        parent_x, parent_y = 0, 0
        if isinstance(self.parent, CanvasItem):
            parent_x, parent_y = self.parent.pos_abs()
        return self.x_mm+parent_x, self.y_mm+parent_y

    def pos_abs_px(self):
        pixels_per_mm_x, pixels_per_mm_y = self.get_pixels_per_mm()
        x_mm, y_mm = self.pos_abs()
        return x_mm*pixels_per_mm_x, y_mm*pixels_per_mm_y

    def size(self):
        return self.width_mm, self.height_mm

    def size_px(self):
        pixels_per_mm_x, pixels_per_mm_y = self.get_pixels_per_mm()
        return (int(self.width_mm*pixels_per_mm_x),
                int(self.height_mm*pixels_per_mm_y))

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
        if not self.get_canvas():
            return  # cannot allocate if i don't know pixels per mm

        width, height = self.size_px()

        for child in self.children:
            child.allocate()

        # If the size didn't change, do nothing.
        if self.surface \
                and self.surface.get_width() == width \
                and self.surface.get_height() == height:
            return

        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)

    def render(self):
        # Paint background
        ctx = cairo.Context(self.surface)
        ctx.save()
        ctx.set_source_rgba(*self.background)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.paint()
        ctx.restore()

        # Paint children
        self.render_children(ctx)

    def render_children(self, ctx):
        for child in self.children:
            child.render()
            ctx.set_source_surface(child.surface, *child.pos_px())
            ctx.paint()

    def get_item_hit(self, x_mm, y_mm, selectable=False):
        """
        Check if the point (x_mm, y_mm) hits this item or any of its children.
        If selectable is True, only selectable items are considered.
        """
        # Check children (child-to-parent order)
        for child in reversed(self.children):
            # Translate the coordinates to the child's local coordinate system
            child_x_mm = x_mm - child.x_mm
            child_y_mm = y_mm - child.y_mm
            hit = child.get_item_hit(child_x_mm, child_y_mm, selectable)
            if hit:
                return hit

        if selectable and not self.selectable:
            return None

        # Check if the point is within the item's bounds
        if 0 <= x_mm <= self.width_mm and 0 <= y_mm <= self.height_mm:
            return self

        return None


class CanvasWidget(Gtk.DrawingArea):
    def __init__(self, width_mm=100, height_mm=100, **kwargs):
        super().__init__(**kwargs)
        self.root = CanvasItem("root",
                               0,
                               0,
                               width_mm,
                               height_mm,
                               parent=self)
        self.pixels_per_mm_x = 1  # Updated in do_size_allocate()
        self.pixels_per_mm_y = 1  # Updated in do_size_allocate()
        self.handle_size = 10   # Resize handle size
        self.active_item = None
        self.active_rect = None, None, None, None
        self._setup_interactions()

    def add(self, item):
        self.root.add(item)

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

    def do_size_allocate(self, width: int, height: int, baseline: int):
        self.pixels_per_mm_x = width/self.root.width_mm
        self.pixels_per_mm_y = width/self.root.height_mm
        self.root.allocate()

    def do_snapshot(self, snapshot):
        width, height = self.get_width(), self.get_height()
        bounds = Graphene.Rect().init(0, 0, width, height)

        self.root.render()
        ctx = snapshot.append_cairo(bounds)
        ctx.set_source_surface(self.root.surface, *self.root.pos_px())
        ctx.paint()

        self._render_selection(ctx, self.root, 0, 0)

    def _render_selection(self, ctx, item, parent_x_mm, parent_y_mm):
        # Calculate absolute position of the item
        absolute_x_mm = parent_x_mm + item.x_mm
        absolute_y_mm = parent_y_mm + item.y_mm
        item_x = absolute_x_mm * self.pixels_per_mm_x
        item_y = absolute_y_mm * self.pixels_per_mm_y
        target_width = item.width_mm * self.pixels_per_mm_x
        target_height = item.height_mm * self.pixels_per_mm_y

        # Draw rectangle around selected items
        if item.selected:
            ctx.save()
            ctx.set_source_rgb(.4, .4, .4)
            ctx.set_dash((5, 5))
            ctx.rectangle(item_x, item_y, target_width, target_height)
            ctx.stroke()
            ctx.restore()

        # Draw resize handle
        if item == self.active_item:
            ctx.save()
            ctx.set_source_rgb(.4, .4, .4)
            ctx.set_line_width(1)
            handle_x = item_x + target_width
            handle_y = item_y + target_height
            ctx.rectangle(handle_x-self.handle_size/2,
                          handle_y-self.handle_size/2,
                          self.handle_size,
                          self.handle_size)
            ctx.stroke()
            ctx.restore()

        # Recursively render children
        for child in item.children:
            self._render_selection(ctx, child, absolute_x_mm, absolute_y_mm)

    def get_item_handle_hit(self, item, x_mm, y_mm, selectable=True):
        for child in item.children:
            child_x_mm = x_mm-item.x_mm
            child_y_mm = y_mm-item.y_mm
            hit = self.get_item_handle_hit(child,
                                           child_x_mm,
                                           child_y_mm,
                                           selectable=True)
            if hit:
                return hit
        if selectable and not item.selectable:
            return
        if not item.selected:
            return None
        handle_x1 = item.x_mm+item.width_mm-self.handle_size/2
        handle_x2 = handle_x1+self.handle_size
        handle_y1 = item.y_mm+item.height_mm-self.handle_size/2
        handle_y2 = handle_y1+self.handle_size
        if handle_x1 <= x_mm <= handle_x2 and handle_y1 <= y_mm <= handle_y2:
            return item
        return None

    def on_button_press(self, gesture, n_press, x, y):
        self.grab_focus()

        x_mm = x/self.pixels_per_mm_x
        y_mm = y/self.pixels_per_mm_y

        hit = self.get_item_handle_hit(self.root, x_mm, y_mm, selectable=True)

        self.root.unselect_all()

        if hit and hit != self.root:
            hit.selected = True
            self.resizing = True
            self.active_item = hit
            self.active_origin = hit.rect()
            self.queue_draw()
            return

        hit = self.root.get_item_hit(x_mm, y_mm, selectable=True)
        if hit and hit != self.root:
            hit.selected = True
            self.moving = True
            self.active_item = hit
            self.active_origin = hit.rect()
            self.queue_draw()
            return

        self.active_item = None
        self.queue_draw()

    def on_mouse_drag(self, gesture, x, y):
        if not self.active_item:
            return

        start_x_mm, start_y_mm, start_w_mm, start_h_mm = self.active_origin
        delta_x_mm = x/self.pixels_per_mm_x
        delta_y_mm = y/self.pixels_per_mm_y

        if self.moving:
            self.active_item.x_mm = start_x_mm+delta_x_mm
            self.active_item.y_mm = start_y_mm+delta_y_mm

        if self.resizing:
            new_w_mm = max(self.handle_size, start_w_mm+delta_x_mm)
            new_w_mm = min(new_w_mm, self.active_item.parent.width_mm)
            self.active_item.width_mm = new_w_mm
            if self.shift_pressed:
                aspect = start_w_mm/start_h_mm
                self.active_item.height_mm = new_w_mm/aspect
            else:
                new_h_mm = max(self.handle_size, start_h_mm+delta_y_mm)
                new_h_mm = min(new_h_mm, self.active_item.parent.height_mm)
                self.active_item.height_mm = new_h_mm
            self.active_item.allocate()

        self.queue_draw()

    def on_button_release(self, gesture, x, y):
        self.resizing = False
        self.moving = False

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Shift_L or keyval == Gdk.KEY_Shift_R:
            self.shift_pressed = True
        elif keyval == Gdk.KEY_Delete:
            self.root.remove_selected()
            self.active_item = None
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
            canvas = CanvasWidget(200, 200)
            win.set_child(canvas)
            group = CanvasItem("GROUP", 50, 50, 140, 130,
                               background=(0, 1, 1, 1))
            group.add(CanvasItem("one", 50, 50, 40, 30,
                                 background=(0, 0, 1, 1),
                                 selectable=False))
            group.add(CanvasItem("two", 100, 100, 30, 30,
                                 background=(0, 1, 0, 1)))
            group.add(CanvasItem("three", 50, 100, 50, 50,
                                 background=(1, 0, 1, 1)))
            canvas.add(group)
            win.present()

    app = CanvasApp()
    app.run([])
