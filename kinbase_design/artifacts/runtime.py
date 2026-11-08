"""Bounded subprocess and Chromium boundaries shared by capture and fidelity."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from ..config import CAPTURE_TIMEOUT_MS, CAPTURE_TOTAL_SECONDS
from ..storage import write_json


def run_job(module, job, timeout=CAPTURE_TOTAL_SECONDS):
    with TemporaryDirectory(prefix='kinbase-job-') as temp:
        path=Path(temp)/'job.json';write_json(path,job)
        process=subprocess.Popen([sys.executable,'-m',module,str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=os.name=='posix')
        try:
            stdout,stderr=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
            else:process.kill()
            process.communicate()
            raise ValueError(f'Browser operation exceeded {timeout}s and was terminated') from exc
        try:result=json.loads(stdout)
        except ValueError:raise ValueError('Browser operation failed: '+(stderr or stdout)[:2000]) from None
        if process.returncode:raise ValueError(result.get('error','Browser operation failed'))
        return result


@contextmanager
def chromium():
    from playwright.sync_api import sync_playwright
    engine=sync_playwright().start()
    try:
        if not Path(engine.chromium.executable_path).is_file():
            raise ValueError('Chromium executable is not installed')
        try:browser=engine.chromium.launch(headless=True,timeout=CAPTURE_TIMEOUT_MS)
        except Exception as exc:raise ValueError('Chromium is unavailable or cannot start: '+str(exc)[:1000]) from exc
        try:yield browser
        finally:browser.close()
    finally:engine.stop()
