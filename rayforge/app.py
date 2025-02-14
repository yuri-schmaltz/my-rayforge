import mimetypes
import argparse
import gi

gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Adw  # noqa: E402
from .widgets.mainwindow import MainWindow  # noqa: E402
from .asyncloop import shutdown  # noqa: E402
from .config import config_mgr  # noqa: E402


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

def main():
    parser = argparse.ArgumentParser(
            description="A GCode generator for laser cutters.")
    parser.add_argument("filename",
                        help="Path to the input SVG or image file.",
                        nargs='?')

    args = parser.parse_args()
    app = App(args)
    app.run(None)
    config_mgr.save()

if __name__ == "__main__":
    main()
