import mimetypes
import gi
from .widgets.mainwindow import MainWindow
from .asyncloop import shutdown

gi.require_version('Adw', '1')
from gi.repository import Adw, GLib  # noqa: E402


class App(Adw.Application):
    def __init__(self, args):
        super().__init__(application_id='com.barebaric.rayforge')
        self.set_accels_for_action("win.quit", ["<Ctrl>Q"])
        self.args = args

    def do_activate(self):
        win = MainWindow(application=self)
        if self.args.filename:
            mime_type, _ = mimetypes.guess_type(self.args.filename)
            win.load_file(self.args.filename, mime_type)
        win.present()

    def do_shutdown(self):
        shutdown()
        Adw.Application.do_shutdown(self)
