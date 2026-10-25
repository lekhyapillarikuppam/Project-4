"""Planning calls in a thread pool, at most api.max_concurrent_solves at once (API-FR-13).

A request waits up to api.solve_wait_s for a slot, then gets 429 "busy, try again".
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from api.errors import ApiError
from tripwise import config

_pool: ThreadPoolExecutor | None = None
_sem: asyncio.Semaphore | None = None


def start() -> None:
    global _pool, _sem
    n = config.default().api["max_concurrent_solves"]
    _pool = ThreadPoolExecutor(max_workers=n, thread_name_prefix="solve")
    _sem = asyncio.Semaphore(n)


def stop() -> None:
    global _pool, _sem
    if _pool:
        _pool.shutdown(wait=False, cancel_futures=True)
    _pool, _sem = None, None


async def solve(fn: Callable, *args: Any) -> Any:
    if _pool is None or _sem is None:
        start()
    try:
        await asyncio.wait_for(_sem.acquire(), timeout=config.default().api["solve_wait_s"])
    except asyncio.TimeoutError:
        raise ApiError(429, "The planner is busy, please try again in a moment.", "busy")
    try:
        return await asyncio.get_running_loop().run_in_executor(_pool, fn, *args)
    finally:
        _sem.release()


async def run_blocking(fn: Callable, *args: Any, **kw: Any) -> Any:
    """A blocking call that is not a solve (such as a Groq request), off the event loop and outside the solve limit."""
    return await asyncio.get_running_loop().run_in_executor(None, lambda: fn(*args, **kw))
