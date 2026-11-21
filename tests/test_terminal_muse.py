import os,sys,tempfile,unittest,shlex,fcntl
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'neurobridge'))
import terminal_muse

class TerminalMuseTests(unittest.TestCase):
    def test_launcher_quotes_paths_and_keeps_known_working_options(self):
        with tempfile.TemporaryDirectory(prefix="Muse space ' ") as tmp, patch.dict(os.environ,{'NEUROBRIDGE_SUPPORT_DIR':tmp}), patch.object(terminal_muse.sys,'platform','darwin'), patch.object(terminal_muse,'worker',return_value=['/some app/NeuroBridge','--worker','terminal-stream','--backend','bleak','--lsltime']), patch.object(terminal_muse.subprocess,'run') as run:
            path=terminal_muse.launch();lines=path.read_text().splitlines()
            self.assertEqual(shlex.split(lines[-1]),['/some app/NeuroBridge','--worker','terminal-stream','--backend','bleak','--lsltime'])
            self.assertEqual(shlex.split(lines[-2])[1], 'NEUROBRIDGE_SUPPORT_DIR='+tmp)
            self.assertEqual(path.stat().st_mode & 0o777,0o700)
            run.assert_called_once_with(['/usr/bin/open','-a','Terminal',str(path)],check=True,timeout=10)
    def test_lock_detects_active_worker_and_releases_without_stale_pid(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'NEUROBRIDGE_SUPPORT_DIR':tmp}):
            self.assertFalse(terminal_muse.terminal_running())
            with (Path(tmp)/'terminal-muse.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.assertTrue(terminal_muse.terminal_running())
                with patch('muselsl.cli.CLI') as cli:
                    terminal_muse.run();cli.assert_not_called()
            self.assertFalse(terminal_muse.terminal_running())
    def test_terminal_worker_dispatches_identical_muselsl_options(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'NEUROBRIDGE_SUPPORT_DIR':tmp}), patch.object(sys,'argv',['terminal-stream','--backend','bleak','--lsltime']), patch('muselsl.cli.CLI') as cli:
            terminal_muse.run();cli.assert_called_once_with('stream')
            self.assertEqual(sys.argv,['muselsl','stream','--backend','bleak','--lsltime'])
