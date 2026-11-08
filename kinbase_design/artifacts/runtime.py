"""Bounded subprocess and Chromium boundaries shared by capture and fidelity."""
from contextlib import contextmanager, asynccontextmanager
import atexit
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
from tempfile import TemporaryDirectory
from ..config import CAPTURE_TIMEOUT_MS, CAPTURE_TOTAL_SECONDS, WORKER_CLEANUP_SECONDS
from ..storage import write_json


def run_job(module, job, timeout=CAPTURE_TOTAL_SECONDS):
    with TemporaryDirectory(prefix='kinbase-job-') as temp:
        path=Path(temp)/'job.json';write_json(path,job)
        process=None;pipe=None;handlers={};environment=os.environ.copy()
        def stop():
            if process is None:return
            try:
                if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
                elif process.poll() is None:process.kill()
            except ProcessLookupError:pass
            try:process.wait(timeout=WORKER_CLEANUP_SECONDS)
            except subprocess.TimeoutExpired:pass  # Kill has been sent; never stall cleanup.
        def interrupted(signum,frame):
            stop()
            if signum==signal.SIGINT:raise KeyboardInterrupt
            raise SystemExit(128+signum)
        atexit.register(stop)
        try:
            if threading.current_thread() is threading.main_thread():
                for signum in (signal.SIGINT,signal.SIGTERM):
                    handlers[signum]=signal.signal(signum,interrupted)
            options={}
            if os.name=='posix':
                pipe=os.pipe();environment['KINBASE_DESIGN_PARENT_FD']=str(pipe[0])
                options['pass_fds']=(pipe[0],)
            process=subprocess.Popen([sys.executable,'-m',module,str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                     text=True,start_new_session=os.name=='posix',env=environment,**options)
            if pipe:os.close(pipe[0]);pipe=(None,pipe[1])
            try:stdout,stderr=process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                raise ValueError(f'Browser operation exceeded {timeout}s and was terminated') from exc
        finally:
            stop()
            if process:
                for stream in (process.stdout,process.stderr):
                    if stream:stream.close()
            if pipe:
                for descriptor in pipe:
                    if descriptor is not None:os.close(descriptor)
            for signum,previous in handlers.items():signal.signal(signum,previous)
            atexit.unregister(stop)
        try:result=json.loads(stdout)
        except ValueError:raise ValueError('Browser operation failed: '+(stderr or stdout)[:2000]) from None
        if process.returncode:raise ValueError(result.get('error','Browser operation failed'))
        return result


def watch_parent():
    """EOF on an inherited pipe kills our entire group even if the parent was SIGKILLed."""
    descriptor=os.environ.pop('KINBASE_DESIGN_PARENT_FD',None)
    if descriptor is None or os.name!='posix':return
    descriptor=int(descriptor);os.set_inheritable(descriptor,False)
    group=os.getpgrp()
    if group!=os.getpid():raise ValueError('Browser worker must own its process group')
    def watch():
        try:
            while os.read(descriptor,1):pass
        finally:
            os.close(descriptor)
            os.killpg(group,signal.SIGKILL)
    threading.Thread(target=watch,name='capture-parent-watch',daemon=True).start()


@asynccontextmanager
async def async_chromium(timeout_ms=CAPTURE_TIMEOUT_MS):
    from playwright.async_api import async_playwright
    engine=await async_playwright().start()
    try:
        if not Path(engine.chromium.executable_path).is_file():raise ValueError('Chromium executable is not installed')
        try:browser=await engine.chromium.launch(headless=True,timeout=timeout_ms)
        except Exception as exc:raise ValueError('Chromium is unavailable or cannot start: '+str(exc)[:1000]) from exc
        try:yield browser,engine.request
        finally:await browser.close()
    finally:await engine.stop()


@contextmanager
def chromium(with_requests=False,timeout_ms=CAPTURE_TIMEOUT_MS):
    from playwright.sync_api import sync_playwright
    engine=sync_playwright().start()
    try:
        if not Path(engine.chromium.executable_path).is_file():
            raise ValueError('Chromium executable is not installed')
        try:browser=engine.chromium.launch(headless=True,timeout=timeout_ms)
        except Exception as exc:raise ValueError('Chromium is unavailable or cannot start: '+str(exc)[:1000]) from exc
        try:yield (browser,engine.request) if with_requests else browser
        finally:browser.close()
    finally:engine.stop()
