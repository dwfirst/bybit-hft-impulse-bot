import asyncio
import time

import aiohttp


class TimeSynchronizer:
    def __init__(self, domain: str = "bybit"):
        self.domain = domain
        self.time_drift_ms = 0
        self.current_ping_ms = 0
        self.is_synchronized = False

    async def sync_with_bybit(self) -> bool:
        url = f"https://api.{self.domain}.com/v5/market/time"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            try:
                start_time = time.time()
                async with session.get(url, headers=headers, timeout=5) as response:
                    end_time = time.time()
                    if response.status != 200:
                        print(f"[TIME SYNC] Invalid status: {response.status}")
                        return False

                    data = await response.json()
                    server_time_ms = int(data["result"]["timeNano"]) // 1_000_000
                    self.current_ping_ms = int((end_time - start_time) * 1000)
                    local_now_ms = int(time.time() * 1000)
                    self.time_drift_ms = server_time_ms - (local_now_ms + (self.current_ping_ms // 2))
                    self.is_synchronized = True
                    print(
                        f"[TIME SYNC] OK ping={self.current_ping_ms}ms "
                        f"drift={self.time_drift_ms}ms"
                    )
                    return True
            except Exception as exc:
                print(f"[TIME SYNC] Error: {exc}")

        self.time_drift_ms = 0
        self.current_ping_ms = 150
        self.is_synchronized = False
        print("[TIME SYNC] Fallback to local PC time.")
        return False

    def get_bybit_timestamp(self) -> int:
        return int(time.time() * 1000) + self.time_drift_ms

    def get_recv_window(self, base_recv_window: int = 5000) -> int:
        if self.current_ping_ms > 150:
            return base_recv_window + (self.current_ping_ms * 2)
        return base_recv_window

