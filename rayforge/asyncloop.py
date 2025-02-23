import asyncio
import threading
from gi.repository import GLib
from collections import defaultdict
from typing import Optional, Callable

_loop = asyncio.new_event_loop()
_shutdown = asyncio.Event()
_task_queue = asyncio.Queue()  # Queue for managing tasks
_progress_callbacks = defaultdict(list)  # Track progress callbacks by key

def _run_until_complete():
    _loop.run_until_complete(_shutdown.wait())

async def _cancel_existing_tasks(key: str):
    """Cancel all existing tasks associated with the given key."""
    if key is None:
        return
    for task in _progress_callbacks.get(key, []):
        task.cancel()
    _progress_callbacks[key].clear()

def _handle_task_result(fut, when_done: Optional[Callable]):
    """Handle the result of a completed task."""
    try:
        if when_done:
            result = fut.result()
            GLib.idle_add(when_done, result)
    except (asyncio.CancelledError, Exception):
        pass

def _cleanup_task(task, key: str):
    """Clean up the task from the progress callbacks."""
    if key is None or key not in _progress_callbacks:
        return

    if task in _progress_callbacks[key]:
        _progress_callbacks[key].remove(task)

    if not _progress_callbacks[key]:
        del _progress_callbacks[key]

def _handle_task_completion(task, when_done: Optional[Callable], key: str):
    """Handle task completion and cleanup."""
    def _done_callback(fut):
        _handle_task_result(fut, when_done)
        _cleanup_task(task, key)
    task.add_done_callback(_done_callback)

async def _worker():
    """Worker to process tasks from the queue."""
    while not _shutdown.is_set():
        key, coro, when_done = await _task_queue.get()
        await _cancel_existing_tasks(key)

        task = asyncio.create_task(coro)
        if key is not None:
            _progress_callbacks[key].append(task)

        _handle_task_completion(task, when_done, key)

def run_async(coro, when_done: Optional[Callable] = None, key=None):
    """Schedule a coroutine to run asynchronously."""
    _loop.call_soon_threadsafe(_task_queue.put_nowait, (key, coro, when_done))

def shutdown():
    """Shutdown the event loop and cancel all tasks."""
    _loop.call_soon_threadsafe(_shutdown.set)
    for tasks in _progress_callbacks.values():
        for task in tasks:
            task.cancel()
    _progress_callbacks.clear()

# Start the worker and event loop
_loop.create_task(_worker())
thread = threading.Thread(target=_run_until_complete, daemon=True)
thread.start()
