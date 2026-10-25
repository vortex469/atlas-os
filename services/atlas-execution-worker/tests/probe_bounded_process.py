"""Credential-free bounded-process checks, runnable on stdin in a worker image."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from atlas_execution_worker.process import run_command


class BoundedProcessTests(unittest.TestCase):
    def test_large_concurrent_output_is_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            code = "import os,threading; t=threading.Thread(target=lambda: os.write(2,b'e'*2097152)); t.start(); os.write(1,b'o'*2097152); t.join()"
            result = run_command([sys.executable, '-c', code], cwd=Path(root), timeout=10, output_limit=4096)
            self.assertEqual(result.returncode, 0)
            for output in (result.stdout, result.stderr):
                output.validate()
                self.assertEqual(len(output.text), 4096)
                self.assertEqual(output.original_bytes, 2097152)
                self.assertTrue(output.truncated)

    def test_timeout_stops_inherited_child(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / 'child.pid'
            code = "import subprocess,sys,time; from pathlib import Path; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); " + f"Path({str(marker)!r}).write_text(str(p.pid)); time.sleep(60)"
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_command([sys.executable, '-c', code], cwd=Path(root), timeout=1)
                pid = int(marker.read_text())
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    status = Path(f'/proc/{pid}/stat')
                    if not status.exists() or status.read_text().split()[2] == 'Z':
                        break
                    time.sleep(0.01)
                else:
                    self.fail('owned child remained live after timeout')
            finally:
                if marker.exists():
                    import os
                    import signal
                    try:
                        os.kill(int(marker.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
