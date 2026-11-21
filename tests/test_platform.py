"""Platform boundary checks, run unchanged on Mac and Windows CI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'neurobridge'))
import platform_support as platform
import runtime
import terminal_muse

class PlatformTests(unittest.TestCase):
    def test_frozen_windows_uses_console_worker_beside_gui(self):
        with patch.object(sys,'platform','win32'),patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable','/a folder/NeuroBridge.exe'):
            args=runtime.worker('record','/data folder/測試.csv',60)
            self.assertEqual(Path(args[0]),Path('/a folder/NeuroBridge-Worker.exe'))
            self.assertEqual(args[1:3],['--worker','record']);self.assertEqual(args[-1],'60')
    def test_console_launch_uses_argument_vector_and_new_console(self):
        with patch.object(sys,'platform','win32'),patch.object(terminal_muse,'worker',return_value=['C:/a folder/NeuroBridge-Worker.exe','--worker','terminal-stream','--backend','bleak','--lsltime']),patch.object(platform.subprocess,'CREATE_NEW_CONSOLE',0x10,create=True),patch.object(terminal_muse.subprocess,'Popen') as spawn:
            terminal_muse.launch()
            args,kw=spawn.call_args
            self.assertEqual(args[0][0],'C:/a folder/NeuroBridge-Worker.exe');self.assertEqual(kw['creationflags'],0x10)
            self.assertNotIn('shell',kw);self.assertNotIn('NEUROBRIDGE_STOP_FILE',kw['env'])
    def test_windows_stop_is_cooperative_not_terminate(self):
        with tempfile.TemporaryDirectory() as tmp:
            class Proc:
                neurobridge_stop_path=Path(tmp)/'stop'
                def send_signal(self,*_):raise AssertionError('must preserve data, not terminate')
            proc=Proc();platform.request_stop(proc)
            self.assertTrue(proc.neurobridge_stop_path.exists());platform.remove_control(proc)
            self.assertFalse(proc.neurobridge_stop_path.exists())
    def test_real_cooperative_shutdown_runs_finally(self):
        # Same watcher used by frozen recorders; no EEG stream is broadcast here.
        with tempfile.TemporaryDirectory() as tmp:
            stop=Path(tmp)/'stop';ready=Path(tmp)/'ready';saved=Path(tmp)/'saved'
            source="import signal,time,pathlib; from platform_support import watch_stop_file; watch_stop_file(); pathlib.Path(%r).touch()\ntry:\n while True: time.sleep(.05)\nfinally: pathlib.Path(%r).write_text('flushed',encoding='utf-8')" % (str(ready),str(saved))
            env=dict(os.environ,PYTHONPATH=str(Path(platform.__file__).parent),NEUROBRIDGE_STOP_FILE=str(stop))
            proc=subprocess.Popen([sys.executable,'-c',source],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+10
                while not ready.exists() and time.monotonic()<deadline:time.sleep(.05)
                self.assertTrue(ready.exists());proc.neurobridge_stop_path=stop;platform.request_stop(proc)
                proc.communicate(timeout=10);self.assertEqual(saved.read_text(),'flushed')
            finally:
                if proc.poll() is None:proc.kill();proc.communicate()
    def test_audio_dispatch_and_explicit_support_path(self):
        with patch.object(sys,'platform','win32'),patch.dict(os.environ,{'NEUROBRIDGE_SUPPORT_DIR':'chosen support'}):
            self.assertEqual(platform.support_dir(),Path('chosen support'))
            self.assertEqual(platform.audio_command('sample.m4a')[-3:],['--worker','audio','sample.m4a'])
