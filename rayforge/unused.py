class SVGDeserializer:
    @staticmethod
    def parse_svg(svg_file):
        """
        Parses an SVG file and returns a DOM object.
        """
        # Use svgpathtools to extract paths and attributes
        paths, attributes, svg_attributes = svg2paths2(svg_file)

        dom = PathDOM({
            'width': svg_attributes.get('width'),
            'height': svg_attributes.get('height')
        })
        for path, attr in zip(paths, attributes):
            dom.add_path(path)
            #print(path, attr)
            #dom.attrs.update(attr)

        return dom


class LaserEtcher(Processor):
    """Strategy for laser etching (filling closed curves)."""
    @staticmethod
    def process(item):
        for path in item.dom.paths:
            if path.isclosed():
                fill_lines = self.generate_fill_lines(path)
                for line in fill_lines:
                    item.dom.add_path(line)
    
    def generate_fill_lines(self, path):
        """Generates a series of parallel lines to fill a closed path."""
        bounds = path.bbox()
        min_x, min_y, max_x, max_y = bounds
        fill_spacing = 0.5  # Distance between fill lines in mm
        lines = []
        
        y = min_y
        while y <= max_y:
            start_x = min_x
            end_x = max_x
            lines.append(svgpathtools.Line(complex(start_x, y), complex(end_x, y)))
            y += fill_spacing
        
        return lines


class PathDOMRenderer(Renderer):
    @classmethod
    def get_extents(cls, pathdom):
        min_x = None
        max_x = None
        min_y = None
        max_y = None
        for path in pathdom.paths:
            for segment in path:
                if segment.start is not None:
                    min_x = min(min_x if min_x is not None else segment.start.real, segment.start.real)
                    min_y = min(min_y if min_y is not None else segment.start.imag, segment.start.imag)
                    max_x = max(max_x if max_x is not None else segment.start.real, segment.start.real)
                    max_y = max(max_y if max_y is not None else segment.start.imag, segment.start.imag)
                if segment.end is not None:
                    min_x = min(min_x if min_x is not None else segment.end.real, segment.end.real)
                    min_y = min(min_y if min_y is not None else segment.end.imag, segment.end.imag)
                    max_x = max(max_x if max_x is not None else segment.end.real, segment.end.real)
                    max_y = max(max_y if max_y is not None else segment.end.imag, segment.end.imag)

        return min_x, max_x, min_y, max_y

    @classmethod
    def get_aspect_ratio(cls, pathdom):
        min_x, max_x, min_y, max_y = cls.get_extents(pathdom)
        return (max_x-min_x)/(max_y-min_y)

    @classmethod
    def render_item(cls, item, width=None, height=None):
        """
        print("RENDERPATH", width, height)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        context = cairo.Context(surface)

        min_x, max_x, min_y, max_y = cls.get_extents(item.data)
        print("EXTENTS", min_x, max_x, min_y, max_y)
        #context.translate(-min_x, -min_y)
        w, h = max_x-min_x, max_y-min_y
        scale_x = width/w
        scale_y = height/h
        print("SIZE:", scale_x, scale_y)
        #context.scale(scale_x, scale_y)

        # Render each path
        context.set_source_rgb(0, 0, 0)  # Set color to black
        for path in item.data.paths:
            for segment in path:
                print("SEG ", segment)
                if segment.start is not None:
                    print("REALIM", segment.start.real, segment.start.imag)
                    context.move_to(segment.start.real-min_x, segment.start.imag-min_y)
                if segment.end is not None:
                    context.line_to(segment.end.real-min_x, segment.end.imag-min_y)
            context.stroke()

        return surface
        """

        with NamedTemporaryFile() as fp:
            wsvg(item.data.paths, filename=fp.name)
            png_data = cairosvg.svg2png(url=fp.name,
                                        output_width=width,
                                        output_height=height)
            return cairo.ImageSurface.create_from_png(io.BytesIO(png_data))
