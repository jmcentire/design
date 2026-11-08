"""Bounded viewport traversal activates native and observer-driven lazy media."""
import asyncio
from pathlib import Path
from time import monotonic
from ..config import (CAPTURE_MEDIA_BUDGET_MS, CAPTURE_MEDIA_LOAD_MS, CAPTURE_MEDIA_SETTLE_MS,
                      CAPTURE_MEDIA_QUIET_MS, CAPTURE_MEDIA_DECODE_MS, CAPTURE_MEDIA_MAX_STEPS,
                      CAPTURE_MEDIA_STEP_FRACTION, CAPTURE_MEDIA_PROTOCOL_GRACE_MS)


async def prepare_media(page,timeout_ms):
    from playwright.async_api import TimeoutError, Error
    budget=min(timeout_ms,CAPTURE_MEDIA_BUDGET_MS);start=monotonic();notes=[]
    try:await page.wait_for_load_state('load',timeout=min(budget/3,CAPTURE_MEDIA_LOAD_MS))
    except TimeoutError:notes.append('Initial page load remained active during media preparation')
    remaining=max(1,budget-(monotonic()-start)*1000)
    args={'budgetMs':remaining,'settleMs':CAPTURE_MEDIA_SETTLE_MS,'quietMs':CAPTURE_MEDIA_QUIET_MS,
          'decodeMs':CAPTURE_MEDIA_DECODE_MS,'maxSteps':CAPTURE_MEDIA_MAX_STEPS,'stepFraction':CAPTURE_MEDIA_STEP_FRACTION}
    try:
        result=await asyncio.wait_for(page.evaluate(Path(__file__).with_name('media_ready.js').read_text(),args),(remaining+CAPTURE_MEDIA_PROTOCOL_GRACE_MS)/1000)
    except asyncio.TimeoutError as exc:raise Error('Lazy-media preparation exceeded its capture time bound') from exc
    problems=[]
    if not result['complete_sweep']:problems.append('Lazy-media viewport traversal reached its time or step bound before the page end')
    if result['pending_images']:problems.append(f'{result["pending_images"]} visible images did not load within the capture bound')
    return {'stats':result,'notes':notes,'problems':problems}
