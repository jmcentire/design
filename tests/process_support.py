"""Bounded supervision of test-owned process trees on this run's macOS host.

Only numeric process ancestry/state is inspected: no other process commands,
environments, source or work are read. Kqueue supplies exit events, not sleep/poll
retry loops. Cleanup kills only the job we started, after assertions observe it.
"""

from contextlib import contextmanager
import errno
import os
import select
import signal
import subprocess
import sys
import time
from types import SimpleNamespace


def job_processes(root, known=None):
    known = known or {}
    result = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,pgid=,lstart=,stat="],
                            capture_output=True, text=True, check=True, timeout=2)
    rows = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        pid, parent, group = map(int, fields[:3])
        rows[pid] = (parent, group, fields[-1], tuple(fields[3:-1]))
    surviving = {pid for pid, previous in known.items() if pid in rows and rows[pid][3] == previous[3]}
    root_matches = root in rows and (root not in known or root in surviving)
    descendants = {root} if root_matches else set()
    while True:
        found = {pid for pid, row in rows.items() if row[0] in descendants}
        if found <= descendants:
            break
        descendants |= found
    owned = descendants | surviving
    group_owned = root_matches or any(rows[pid][1] == root for pid in surviving)
    return {pid: row for pid, row in rows.items()
            if (pid in owned or (group_owned and row[1] == root)) and not row[2].startswith("Z")}


class ExitEvents:
    def __init__(self, pids):
        assert hasattr(select, "kqueue"), "This process-lifecycle probe requires the run's macOS kqueue runtime"
        self.queue = select.kqueue()
        self.pending = set()
        for pid in pids:
            event = select.kevent(pid, filter=select.KQ_FILTER_PROC,
                                  flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                                  fflags=select.KQ_NOTE_EXIT)
            try:
                self.queue.control([event], 0, 0)
            except OSError as error:
                if error.errno != errno.ESRCH:
                    self.queue.close()
                    raise
            else:
                self.pending.add(pid)

    def wait(self, timeout):
        deadline = time.monotonic() + timeout
        while self.pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            events = self.queue.control(None, len(self.pending), remaining)
            if not events:
                return False
            for event in events:
                if event.fflags & select.KQ_NOTE_EXIT:
                    self.pending.discard(event.ident)
        return True

    def close(self):
        self.queue.close()


@contextmanager
def capture_job(library, url, log_root):
    stdout_path, stderr_path = log_root / "capture.stdout", log_root / "capture.stderr"
    with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
        command = [sys.executable, "-m", "kinbase_design", "capture", "--url", url,
                   "--library", str(library.library), "--workspace", str(library.workspace)]
        process = subprocess.Popen(command, cwd=library.project, env=library.environment(),
                                   stdout=stdout, stderr=stderr, start_new_session=True)
        job = SimpleNamespace(process=process, known={}, stdout=stdout_path, stderr=stderr_path)
        try:
            job.known.update(job_processes(process.pid))
            yield job
        finally:
            try:
                remaining = job_processes(process.pid, job.known)
            except Exception:
                # While the unreaped CLI is alive its session/group is still
                # ours, even when this host denies process-table inspection.
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=5)
                raise
            if any(row[1] == process.pid for row in remaining.values()):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for pid in remaining:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=5)
