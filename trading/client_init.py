import asyncio
import time
from typing import Optional

from pybit.unified_trading import HTTP


class RateLimiter:
    """Глобальный троттлинг REST-вызовов Bybit.

    Гарантирует минимальный интервал между запросами, чтобы не ловить
    rate-limit от биржи при активной торговле.
    """

    def __init__(self, min_interval_ms: int = 120):
        self.min_interval_s = max(0, min_interval_ms) / 1000.0
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self.min_interval_s - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


class BybitClientInitializer:
    def __init__(self, config: dict, time_sync: Optional[object] = None):
        self.api_config = config["api"]
        self.time_sync = time_sync
        self.session: Optional[HTTP] = None

        throttle_ms = int(self.api_config.get("api_throttle_ms", 120))
        self.rate_limiter = RateLimiter(min_interval_ms=throttle_ms)

    def _resolve_recv_window(self) -> int:
        """Приоритет: time_sync (адаптивный) > config (статический)."""
        base = int(self.api_config.get("recv_window_default", 5000))

        if self.time_sync is not None and hasattr(self.time_sync, "get_recv_window"):
            try:
                dynamic = int(self.time_sync.get_recv_window(base_recv_window=base))
                # Санity-check: Bybit допускает 1000..60000
                if 1000 <= dynamic <= 60000:
                    return dynamic
            except Exception:
                pass

        return max(1000, min(60000, base))

    def get_rest_session(self) -> HTTP:
        if self.session is not None:
            return self.session

        api_key = self.api_config.get("api_key")
        api_secret = self.api_config.get("api_secret")
        if not api_key or not api_secret:
            raise ValueError(
                "[CLIENT] api_key / api_secret missing in config.json. "
                "Refusing to init session."
            )

        kwargs = {
            "testnet": bool(self.api_config.get("testnet", True)),
            "api_key": api_key,
            "api_secret": api_secret,
            "recv_window": self._resolve_recv_window(),
        }

        domain = self.api_config.get("domain")
        if domain:
            kwargs["domain"] = domain

        self.session = HTTP(**kwargs)
        print(
            f"[CLIENT] Session initialized "
            f"(testnet={kwargs['testnet']}, recv_window={kwargs['recv_window']}ms, "
            f"throttle={self.rate_limiter.min_interval_s * 1000:.0f}ms)"
        )
        return self.session

    async def throttled_call(self, func, *args, **kwargs):
        """Обёртка для REST-вызовов: ждёт слот в rate-limiter, затем вызывает.

        Использование:
            result = await client.throttled_call(
                session.place_order, category="linear", symbol="BTCUSDT", ...
            )
        """
        await self.rate_limiter.acquire()
        # pybit — синхронный SDK, уводим в thread pool
        return await asyncio.to_thread(func, *args, **kwargs)