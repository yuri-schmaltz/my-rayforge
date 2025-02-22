from abc import ABC, abstractmethod


class Renderer(ABC):
    """
    Reads image data and renders to a Cairo surface.
    """
    label = None
    mime_types = None
    extensions = None

    @classmethod
    def prepare(cls, data):
        """
        Called once for every image on import and can be used to preload
        or prepare the image.
        """
        return data

    @classmethod
    @abstractmethod
    def get_natural_size(cls, data):
        """
        Returns the natural (untransformed) size of the image in mm, if
        known. Return None, None, otherwise.
        """
        return None, None

    @classmethod
    @abstractmethod
    def get_aspect_ratio(cls, data):
        """
        Returns the natural (untransformed) aspect ratio of the image.
        """
        pass

    @classmethod
    @abstractmethod
    def render_workpiece(cls, data, width=None, height=None):
        """
        Renders to a Cairo surface.
        """
        pass
