"""计时装饰器：对函数或单次调用打点，不侵入业务逻辑。"""

import logging
import time
from functools import wraps
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")
_log = logging.getLogger(__name__)


def log_timing(name: str | None = None):
    """装饰器：对 async 函数记录调用耗时（logger name 为当前模块）。"""

    def deco(f):
        @wraps(f)
        async def wrap(*args: Any, **kwargs: Any) -> Any:
            label = name if name is not None else f.__qualname__
            t0 = time.perf_counter()
            try:
                return await f(*args, **kwargs)
            finally:
                _log.info("[timing] %s %.2fs", label, time.perf_counter() - t0)

        return wrap

    return deco


async def timed_run(name: str, coro: Coroutine[Any, Any, T]) -> T:
    """执行一个 coroutine 并记录耗时，用于单次调用（如 agent.run）。"""
    t0 = time.perf_counter()
    try:
        return await coro
    finally:
        _log.info("[timing] %s %.2fs", name, time.perf_counter() - t0)
