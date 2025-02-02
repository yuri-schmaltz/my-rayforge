import cairo
from copy import copy
from dataclasses import dataclass, field
from render import Renderer, SVGRenderer, PNGRenderer
from pathdom import PathDOM
from processor import Processor, ToGrayscale, OutlineTracer
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Graphene  # noqa: E402


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


@dataclass
class Group:
    items: list[WorkAreaItem] = field(default_factory=list)
    processors: list[Processor] = field(default_factory=lambda: [
        ToGrayscale,
        OutlineTracer
    ])
    pathdom: PathDOM = PathDOM()
    surface: cairo.Surface = None

    def add_item(self, item):
        self.items.append(item)

    def render(self, width, height, pixels_per_mm):
        # Make a surface for the layer and copy all relevant items to it.
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                          int(width), int(height))
        ctx = cairo.Context(self.surface)
        for item in self.items:
            item_x = item.x_mm*pixels_per_mm
            item_y = item.y_mm*pixels_per_mm
            item_w = item.width_mm*pixels_per_mm
            item_h = item.height_mm*pixels_per_mm
            ctx.translate(item_x, item_y)
            ctx.scale(item_w/item.surface.get_width(), item_h/item.surface.get_height())
            ctx.set_source_surface(item.surface, 0, 0)
            ctx.paint()

        # Run the processors.
        self.pathdom.clear()
        for processor in self.processors:
            processor.process(self)
        self.pathdom.render(self.surface)

        return self.surface


@dataclass
class WorkArea:
    width_mm: float = 10   # Real-world width in mm
    height_mm: float = 10  # Real-world height in mm
    items: list = field(default_factory=lambda: [])
    groups: list = field(default_factory=lambda: [Group()])

    def add_item(self, item):
        self.items.append(item)


class WorkAreaWidget(Gtk.DrawingArea):
    def __init__(self, width_mm=100, height_mm=100):
        super().__init__()
        self.work_area = WorkArea(width_mm, height_mm)
        self.groups = [Group()]
        self.aspect_ratio = width_mm/height_mm
        self.set_has_tooltip(True)

        # Location of the work area in the drawing area.
        self.work_area.width_mm = width_mm  # Real-world width in mm
        self.work_area.height_mm = height_mm  # Real-world height in mm
        self.work_area_x = 10
        self.work_area_x_end = 20
        self.work_area_y = 10
        self.work_area_y_end = 20
        self.work_area_w = 10
        self.work_area_h = 10
        self.pixels_per_mm = self.work_area_w/self.work_area.width_mm
        self.label_padding = 2
        self.grid_size = 10  # in mm

        # Configure gestures.
        self.active_item = None
        self.active_item_copy = None
        self.resizing = False
        self.moving = False
        self.handle_size = 10.0
        self.click_pos = None, None
        self.click_gesture = Gtk.GestureClick()
        self.click_gesture.connect("pressed", self.on_button_press)
        self.add_controller(self.click_gesture)

        self.drag_gesture = Gtk.GestureDrag()
        self.drag_gesture.connect("drag-update", self.on_mouse_drag)
        self.drag_gesture.connect("drag-end", self.on_button_release)
        self.add_controller(self.drag_gesture)

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
        aspect_ratio = renderer.get_aspect_ratio(data)
        width_mm, height_mm = self._get_default_size_mm(aspect_ratio)
        item = WorkAreaItem(renderer, data, 0, 0, width_mm, height_mm)
        self.work_area.add_item(item)
        self.groups[0].add_item(item)
        self.queue_draw()

    def _get_default_size_mm(self, aspect_ratio):
        width_mm = self.work_area.width_mm
        height_mm = width_mm/aspect_ratio
        if height_mm > self.work_area.height_mm:
            height_mm = self.work_area.height_mm
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
        for item in self.work_area.items:
            self._draw_item(ctx, item)

        if self.resizing or self.moving:
            return

        # Draw the paths.
        for group in self.groups:
            surface = group.render(self.work_area_w, self.work_area_h, self.pixels_per_mm)
            ctx.set_source_surface(surface, self.work_area_x, self.work_area_y_end)
            ctx.paint()

    def _draw_item(self, cr, item):
        surface = item.render(self.pixels_per_mm)

        cr.save()
        item_x = self.work_area_x+item.x_mm*self.pixels_per_mm
        item_y = self.work_area_y_end+item.y_mm*self.pixels_per_mm

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
        label_x_max = f"{self.work_area.width_mm}"
        x_label_max_extents = cr.text_extents(label_x_max)
        x_label_width = x_label_max_extents.width
        x_label_height = x_label_max_extents.height
        label_y_max = f"{self.work_area.height_mm}"
        y_label_max_extents = cr.text_extents(label_y_max)
        y_label_width = y_label_max_extents.width
        y_label_height = y_label_max_extents.height

        self.work_area_x = y_label_width+2*self.label_padding
        self.work_area_x_end = width-x_label_width/2-self.label_padding
        self.work_area_y = height-x_label_height-2*self.label_padding
        self.work_area_y_end = y_label_height/2+self.label_padding
        self.work_area_w = self.work_area_x_end-self.work_area_x
        self.work_area_h = self.work_area_y-self.work_area_y_end
        self.pixels_per_mm = self.work_area_w/self.work_area.width_mm

    def _draw_scales(self, cr, width, height):
        """
        Draw scales on the X and Y axes.
        """
        self._update_surface_extents(cr, width, height)

        # Draw X axis line.
        cr.set_line_width(1)
        cr.set_source_rgb(0, 0, 0)
        cr.move_to(self.work_area_x, self.work_area_y)
        cr.line_to(self.work_area_x_end, self.work_area_y)

        # Draw Y axis line.
        cr.move_to(self.work_area_x, self.work_area_y)
        cr.line_to(self.work_area_x, self.work_area_y_end)
        cr.stroke()

        # Draw X-axis scale
        interval = self.grid_size
        for x in range(interval, self.work_area.width_mm+1, interval):
            x_px = x/self.work_area.width_mm*self.work_area_w
            cr.move_to(self.work_area_x+x_px, self.work_area_y)
            cr.line_to(self.work_area_x+x_px,
                       self.work_area_y-self.work_area_h)
            cr.set_source_rgb(.9, .9, .9)
            cr.stroke()

            cr.set_source_rgb(0, 0, 0)
            label = f"{x}"
            extents = cr.text_extents(label)
            cr.move_to(self.work_area_x+x_px-extents.width/2,
                       self.work_area_y+extents.height+self.label_padding)
            cr.show_text(f"{x}")

        # Draw Y-axis scale
        for y in range(interval, self.work_area.height_mm + 1, interval):
            y_px = self.work_area_y-y/self.work_area.height_mm*self.work_area_h
            cr.move_to(self.work_area_x, y_px)
            cr.line_to(self.work_area_x+self.work_area_w, y_px)
            cr.set_source_rgb(.9, .9, .9)
            cr.stroke()

            cr.set_source_rgb(0, 0, 0)
            label = f"{y}"
            extents = cr.text_extents(label)
            cr.move_to(self.work_area_x-extents.width-self.label_padding,
                       y_px+extents.height/2)
            cr.show_text(label)

    def get_item_at(self, x_mm, y_mm):
        for item in reversed(self.work_area.items):
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
        for item in self.work_area.items:
            item.selected = False
        self.queue_draw()

    def on_button_press(self, gesture, n_press, x, y):
        x_mm = (x-self.work_area_x)/self.pixels_per_mm
        y_mm = (y-self.work_area_y_end)/self.pixels_per_mm
        self.click_pos = x_mm, y_mm

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
                                            self.work_area.width_mm)
            self.active_item.height_mm = min(max(self.handle_size, start_h+dy),
                                             self.work_area.height_mm)
            self.queue_draw()
            return

        # Ending up here, the user is trying to move the item.
        self.active_item.x_mm = min(max(-start_w/2, start_x+dx),
                                    self.work_area.width_mm-start_w/2)
        self.active_item.y_mm = min(max(-start_h/2, start_y+dy),
                                    self.work_area.height_mm-start_h/2)
        self.queue_draw()
