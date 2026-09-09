"""Shared async utilities for tool functions."""

from __future__ import annotations

import asyncio
import concurrent.futures


def run_async(coro):
    """Run an async coroutine from a sync context, handling nested event loops.

    Works in three scenarios:
    1. No event loop running → asyncio.run()
    2. Event loop running (e.g. inside FastMCP) → ThreadPoolExecutor
    3. asyncio.run() fails → fallback to new event loop
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)
