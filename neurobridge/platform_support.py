"""Small OS boundary; recording and analysis rules remain shared."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid


def support_dir():
    default = Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData/Local')))/'NeuroBridge' if sys.platform == 'win32' else Path.home()/'Library/Application Support/NeuroBridge'
    return Path(os.environ.get('NEUROBRIDGE_SUPPORT_DIR', str(default)))


class FileLock:
    """An OS-owned lock, released after a crash without stale PID files."""
    def __init__(self, path):
        self.path = Path(path)
        self.file = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open('a+b')
        self.file.seek(0, os.SEEK_END)
        if not self.file.tell():
            self.file.write(b'0'); self.file.flush()
        self.file.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            self.file.close(); self.file = None
            return False
        return True

    def close(self):
        if self.file:
            if sys.platform == 'win32':
                import msvcrt
                self.file.seek(0); msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.file.close(); self.file = None


def worker_options(visible=False, new_session=False):
    if sys.platform == 'win32':
        return {'creationflags': subprocess.CREATE_NEW_CONSOLE if visible else subprocess.CREATE_NO_WINDOW}
    return {'start_new_session': new_session}


def spawn_worker(args, **kwargs):
    """Windows uses a cooperative stop file instead of destructive SIGINT emulation."""
    env = dict(kwargs.pop('env', os.environ), PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    if sys.platform == 'win32':
        folder = support_dir()/'worker-control'; folder.mkdir(parents=True, exist_ok=True)
        path = folder/(uuid.uuid4().hex+'.stop')
        env['NEUROBRIDGE_STOP_FILE'] = str(path)
        kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
    proc = subprocess.Popen(args, env=env, **kwargs)
    if sys.platform == 'win32': proc.neurobridge_stop_path = path
    return proc


def request_stop(proc, group=False):
    path = getattr(proc, 'neurobridge_stop_path', None)
    if path is not None:
        Path(path).touch()
    elif group and sys.platform != 'win32':
        os.killpg(proc.pid, signal.SIGINT)
    else:
        proc.send_signal(signal.SIGINT)


def remove_control(proc):
    path = getattr(proc, 'neurobridge_stop_path', None)
    if path is not None: Path(path).unlink(missing_ok=True)


def watch_stop_file():
    path = os.environ.get('NEUROBRIDGE_STOP_FILE')
    if not path: return
    import _thread
    def watch():
        while not Path(path).exists(): time.sleep(.1)
        # Python's SIGINT handler runs on the main thread; recorder/session finally
        # blocks can flush CSVs, close LSL and finalize metadata before exiting.
        _thread.interrupt_main()
    threading.Thread(target=watch, daemon=True).start()


def audio_command(path):
    if sys.platform == 'win32':
        from runtime import worker
        return worker('audio', path)
    return ['/usr/bin/afplay', str(path)]


def notify(message):
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'NeuroBridge', 0x40)
    else:
        from AppKit import NSAlert
        alert = NSAlert.alloc().init(); alert.setMessageText_(message); alert.runModal()
