import asyncio
import threading
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import GLib  # noqa: E402

_loop = asyncio.new_event_loop()
_shutdown = asyncio.Event()

def _run_until_complete():
    _loop.run_until_complete(_shutdown.wait())

def run_async(coro, when_done=None):
    fut = asyncio.run_coroutine_threadsafe(coro, _loop)
    if not when_done:
        return
    def call_when_done():
        when_done(fut.result())
    fut.add_done_callback(lambda _: GLib.idle_add(call_when_done))

def shutdown():
    _loop.call_soon_threadsafe(_shutdown.set)

# Run asyncio loop and wait forever
thread = threading.Thread(target=_run_until_complete)
thread.start()
