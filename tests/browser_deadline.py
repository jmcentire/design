"""Host-side deadlines for browser phases, including evaluate and cleanup.

Playwright action timeouts do not bound promises returned by evaluate. The host
timer works even when page JavaScript is disabled, without relying on a page
timer or animation callback. This bounds the harness, not product response time.
"""

from contextlib import contextmanager
import signal
import threading

import pytest


@contextmanager
def browser_deadline(label, seconds=60):
    if not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread():
        pytest.fail("Browser deadlines require POSIX setitimer on the main thread", pytrace=False)

    def expired(signum, frame):
        pytest.fail(f"Browser phase timed out after {seconds:g}s: {label}", pytrace=False)

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, expired)
    # Repeat after expiry to bound any cleanup entered while unwinding a stuck call.
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds, 5)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if any(previous_timer):
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)
