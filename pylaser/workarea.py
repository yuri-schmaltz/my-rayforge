import cairo
from copy import copy
from dataclasses import dataclass, field
from pathdom import PathDOM
from render import Renderer, SVGRenderer, PNGRenderer
from processor import Processor, MakeTransparent, ToGrayscale, OutlineTracer
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Graphene  # noqa: E402


@dataclass
class WorkAreaItem:
    renderer: Renderer
    data: object
    x_mm: float  # Position in workarea, in mm
    y_mm: float  # Position in workarea, in mm
    width_mm: float  # Real-world width in mm
    height_mm: float  # Real-world height in mm
    angle: float = 0.0
    selected: bool = False
    surface: cairo.Surface = None

    def render(self, pixels_per_mm):
        width = int(self.width_mm*pixels_per_mm)
        height = int(self.height_mm*pixels_per_mm)

        if not self.surface \
           or self.surface.get_width() != width \
           or self.surface.get_height() != height:
            self.surface = self.renderer.render_item(self, width, height)

        return self.surface

    def get_aspect_ratio(self):
        """Returns the current aspect ratio (i.e. not the natural ratio)"""
        return self.width_mm/self.height_mm


@dataclass
class Group:
    workarea: object
    items: list[WorkAreaItem] = field(default_factory=list)
    processors: list[Processor] = field(default_factory=lambda: [
        MakeTransparent,
        ToGrayscale,
        OutlineTracer
    ])
    pixels_per_mm: int = 20
    pathdom: PathDOM = PathDOM()
    surface: cairo.Surface = None

    def copy(self):
        return Group(self.workarea,
                     self.items,
                     self.processors,
                     self.pixels_per_mm)

    def add_item(self, item):
        self.items.append(item)

    def remove_selected(self):
        self.items = [i for i in self.items if not i.selected]

    def size_mm(self):
        width_mm, height_mm = 0, 0
        for item in self.items:
            width_mm = max(width_mm, item.width_mm+item.x_mm)
            height_mm = max(height_mm, item.height_mm+item.y_mm)
        return width_mm, height_mm

    def render(self):
        # Make a surface for the layer and copy all relevant items to it.
        width_mm, height_mm = self.size_mm()
        width = width_mm*self.pixels_per_mm
        height = height_mm*self.pixels_per_mm
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                          int(width), int(height))

        ctx = cairo.Context(self.surface)
        for item in self.items:
            ctx.save()
            item_x = item.x_mm*self.pixels_per_mm
            item_y = item.y_mm*self.pixels_per_mm
            item_w = item.width_mm*self.pixels_per_mm
            item_h = item.height_mm*self.pixels_per_mm
            scale_x = item_w/item.surface.get_width()
            scale_y = item_h/item.surface.get_height()
            ctx.translate(item_x, item_y)
            ctx.scale(scale_x, scale_y)
            ctx.set_source_surface(item.surface, 0, 0)
            ctx.paint()
            ctx.restore()

        # Run the processors.
        self.pathdom.clear()
        for processor in self.processors:
            processor.process(self)
        self.pathdom.render(self.surface, self.pixels_per_mm, self.workarea.height_mm)

        return self.surface


@dataclass
class WorkArea:
    width_mm: float = 10   # Real-world width in mm
    height_mm: float = 10  # Real-world height in mm
    items: list = field(default_factory=lambda: [])
    groups: list = field(default_factory=lambda: [])

    def add_item(self, item):
        self.items.append(item)

    def remove_selected(self):
        self.items = [i for i in self.items if not i.selected]
        for group in self.groups:
            group.remove_selected()


class WorkAreaWidget(Gtk.DrawingArea):
    def __init__(self, width_mm=100, height_mm=100, **kwargs):
        super().__init__(**kwargs)
        self.workarea = WorkArea(width_mm, height_mm)
        self.workarea.groups.append(Group(self.workarea))
        self.aspect_ratio = width_mm/height_mm
        self.set_focusable(True)

        # Location of the work area in the drawing area.
        self.workarea_x = 10
        self.workarea_x_end = 20
        self.workarea_y = 10
        self.workarea_y_end = 20
        self.workarea_w = 10
        self.workarea_h = 10
        self.pixels_per_mm = self.workarea_w/self.workarea.width_mm
        self.label_padding = 2
        self.grid_size = 10  # in mm

        # Configure gestures.
        self.click_gesture = Gtk.GestureClick()
        self.click_gesture.connect("pressed", self.on_button_press)
        self.add_controller(self.click_gesture)
        self.last_click = None, None
        self.active_item = None
        self.active_item_copy = None
        self.handle_size = 10.0

        self.drag_gesture = Gtk.GestureDrag()
        self.drag_gesture.connect("drag-update", self.on_mouse_drag)
        self.drag_gesture.connect("drag-end", self.on_button_release)
        self.add_controller(self.drag_gesture)
        self.resizing = False
        self.moving = False

        # Create an event controller for key events
        self.key_controller = Gtk.EventControllerKey.new()
        self.key_controller.connect("key-pressed", self.on_key_pressed)
        self.key_controller.connect("key-released", self.on_key_released)
        self.add_controller(self.key_controller)
        self.shift_pressed = False
        self.grab_focus()

    def add_svg(self, data):
        """
        Add a new item from an SVG (XML as binary string).
        """
        self._add_item(SVGRenderer, data)

    def add_png(self, data):
        """
        Add a new item from a PNG image (binary string).
        """
        self._add_item(PNGRenderer, data)

    def _add_item(self, renderer, data):
        data = renderer.prepare(data)
        aspect_ratio = renderer.get_aspect_ratio(data)
        width_mm, height_mm = self._get_default_size_mm(aspect_ratio)
        item = WorkAreaItem(renderer,
                            data,
                            self.workarea.width_mm/2-width_mm/2,
                            self.workarea.height_mm/2-height_mm/2,
                            width_mm,
                            height_mm)
        self.workarea.add_item(item)
        self.workarea.groups[0].add_item(item)
        self.queue_draw()

    def _get_default_size_mm(self, aspect_ratio):
        width_mm = self.workarea.width_mm
        height_mm = width_mm/aspect_ratio
        if height_mm > self.workarea.height_mm:
            height_mm = self.workarea.height_mm
            width_mm = height_mm*aspect_ratio
        return width_mm, height_mm

    def do_snapshot(self, snapshot):
        """
        Render the Cairo surface and draw scales on the widget.
        """
        # Get the widget's allocated size
        width = self.get_width()
        height = width/self.aspect_ratio
        if height > self.get_height():
            height = self.get_height()
            width = height*self.aspect_ratio

        # Create a Cairo context for the snapshot
        ctx = snapshot.append_cairo(
            Graphene.Rect().init(0, 0, width, height)
        )

        # Clear the background
        ctx.set_source_rgb(1, 1, 1)  # White background
        ctx.paint()

        # Draw scales on the X and Y axes
        self._draw_scales(ctx, width, height)

        # Draw the items.
        for item in self.workarea.items:
            self._draw_item(ctx, item)

        if self.resizing or self.moving:
            return

        # Draw the paths.
        for group in self.workarea.groups:
            group = group.copy()
            group.pixels_per_mm = self.pixels_per_mm
            surface = group.render()
            ctx.set_source_surface(surface,
                                   self.workarea_x,
                                   self.workarea_y_end)
            ctx.paint()

    def _draw_item(self, cr, item):
        surface = item.render(self.pixels_per_mm)

        cr.save()
        item_x = self.workarea_x+item.x_mm*self.pixels_per_mm
        item_y = self.workarea_y_end+item.y_mm*self.pixels_per_mm

        cr.translate(item_x, item_y)
        item_width = surface.get_width()
        item_height = surface.get_height()
        target_width = item.width_mm*self.pixels_per_mm
        target_height = item.height_mm*self.pixels_per_mm
        cr.scale(target_width/item_width, target_height/item_height)
        cr.rotate(item.angle)
        cr.set_source_surface(surface, 0, 0)
        cr.paint()
        cr.restore()

        # Draw rectangle around selected items
        if item.selected:
            cr.set_source_rgb(0, 0, 1)
            cr.rectangle(item_x, item_y, target_width, target_height)
            cr.stroke()

        # Draw resize handle
        if item == self.active_item:
            cr.set_source_rgb(0, 0, 1)
            handle_x = item_x + target_width
            handle_y = item_y + target_height
            cr.rectangle(handle_x-self.handle_size/2,
                         handle_y-self.handle_size/2,
                         self.handle_size,
                         self.handle_size)
            cr.fill()

    def _update_surface_extents(self, cr, width, height):
        label_x_max = f"{self.workarea.width_mm}"
        x_label_max_extents = cr.text_extents(label_x_max)
        x_label_width = x_label_max_extents.width
        x_label_height = x_label_max_extents.height
        label_y_max = f"{self.workarea.height_mm}"
        y_label_max_extents = cr.text_extents(label_y_max)
        y_label_width = y_label_max_extents.width
        y_label_height = y_label_max_extents.height

        self.workarea_x = y_label_width+2*self.label_padding
        self.workarea_x_end = width-x_label_width/2-self.label_padding
        self.workarea_y = height-x_label_height-2*self.label_padding
        self.workarea_y_end = y_label_height/2+self.label_padding
        self.workarea_w = self.workarea_x_end-self.workarea_x
        self.workarea_h = self.workarea_y-self.workarea_y_end
        self.pixels_per_mm = self.workarea_w/self.workarea.width_mm

    def _draw_scales(self, cr, width, height):
        """
        Draw scales on the X and Y axes.
        """
        self._update_surface_extents(cr, width, height)

        # Draw X axis line.
        cr.set_line_width(1)
        cr.set_source_rgb(0, 0, 0)
        cr.move_to(self.workarea_x, self.workarea_y)
        cr.line_to(self.workarea_x_end, self.workarea_y)

        # Draw Y axis line.
        cr.move_to(self.workarea_x, self.workarea_y)
        cr.line_to(self.workarea_x, self.workarea_y_end)
        cr.stroke()

        # Draw X-axis scale
        interval = self.grid_size
        for x in range(interval, self.workarea.width_mm+1, interval):
            x_px = x/self.workarea.width_mm*self.workarea_w
            cr.move_to(self.workarea_x+x_px, self.workarea_y)
            cr.line_to(self.workarea_x+x_px,
                       self.workarea_y-self.workarea_h)
            cr.set_source_rgb(.9, .9, .9)
            cr.stroke()

            cr.set_source_rgb(0, 0, 0)
            label = f"{x}"
            extents = cr.text_extents(label)
            cr.move_to(self.workarea_x+x_px-extents.width/2,
                       self.workarea_y+extents.height+self.label_padding)
            cr.show_text(f"{x}")

        # Draw Y-axis scale
        for y in range(interval, self.workarea.height_mm + 1, interval):
            y_px = self.workarea_y-y/self.workarea.height_mm*self.workarea_h
            cr.move_to(self.workarea_x, y_px)
            cr.line_to(self.workarea_x+self.workarea_w, y_px)
            cr.set_source_rgb(.9, .9, .9)
            cr.stroke()

            cr.set_source_rgb(0, 0, 0)
            label = f"{y}"
            extents = cr.text_extents(label)
            cr.move_to(self.workarea_x-extents.width-self.label_padding,
                       y_px+extents.height/2)
            cr.show_text(label)

    def get_item_at(self, x_mm, y_mm):
        for item in reversed(self.workarea.items):
            if x_mm >= item.x_mm and x_mm <= item.x_mm+item.width_mm \
              and y_mm >= item.y_mm and y_mm <= item.y_mm+item.height_mm:
                return item
            if item.selected and self._handle_clicked(item, x_mm, y_mm):
                return item
        return None

    def _handle_clicked(self, item, x_mm, y_mm):
        handle_size_mm = self.handle_size/self.pixels_per_mm
        return x_mm >= item.x_mm+item.width_mm-handle_size_mm/2 \
            and x_mm <= item.x_mm+item.width_mm+handle_size_mm/2 \
            and y_mm >= item.y_mm+item.height_mm-handle_size_mm/2 \
            and y_mm <= item.y_mm+item.height_mm+handle_size_mm/2

    def _unselect_all(self):
        for item in self.workarea.items:
            item.selected = False
        self.queue_draw()

    def on_button_press(self, gesture, n_press, x, y):
        self.grab_focus()

        x_mm = (x-self.workarea_x)/self.pixels_per_mm
        y_mm = (y-self.workarea_y_end)/self.pixels_per_mm
        self.last_click = x_mm, y_mm

        item = self.get_item_at(x_mm, y_mm)
        if not item:
            self._unselect_all()
            return

        self.active_item_copy = copy(item)
        item.selected = True
        self.active_item = item

        # Handle clicked?
        if self._handle_clicked(item, x_mm, y_mm):
            self.resizing = True
        else:
            self.moving = True
        self.queue_draw()

    def on_button_release(self, gesture, x, y):
        self.active_item = None
        self.resizing = False
        self.moving = False

    def on_mouse_drag(self, gesture, x, y):
        if not self.active_item:
            return

        start_x = self.active_item_copy.x_mm
        start_y = self.active_item_copy.y_mm
        start_w = self.active_item_copy.width_mm
        start_h = self.active_item_copy.height_mm

        dx = x/self.pixels_per_mm
        dy = y/self.pixels_per_mm
        if self.resizing:
            self.active_item.width_mm = min(max(self.handle_size, start_w+dx),
                                            self.workarea.width_mm)
            if self.shift_pressed:
                aspect = self.active_item_copy.get_aspect_ratio()
                self.active_item.height_mm = self.active_item.width_mm/aspect
            else:
                self.active_item.height_mm = min(max(self.handle_size,
                                                     start_h+dy),
                                                 self.workarea.height_mm)

            self.queue_draw()
            return

        # Ending up here, the user is trying to move the item.
        self.active_item.x_mm = min(max(-start_w/2, start_x+dx),
                                    self.workarea.width_mm-start_w/2)
        self.active_item.y_mm = min(max(-start_h/2, start_y+dy),
                                    self.workarea.height_mm-start_h/2)
        self.queue_draw()

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Shift_L or keyval == Gdk.KEY_Shift_R:
            self.shift_pressed = True
        elif keyval == Gdk.KEY_Delete:
            self.workarea.remove_selected()
            self.active_item = None
            self.active_item_copy = None
            self.queue_draw()

    def on_key_released(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Shift_L or keyval == Gdk.KEY_Shift_R:
            self.shift_pressed = False
