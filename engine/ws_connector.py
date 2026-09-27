import asyncio
import json
import ssl

import websockets


class WebSocketConnector:
    def __init__(self, config: dict, hft_processor, log_fn=print):
        self.config = config
        self.hft_processor = hft_processor
        self.log = log_fn
        self.monitored_coins = config["assets"]["monitored_coins"]
        self.is_running = False

        domain = config["api"].get("domain", "bybit")
        self.ws_url = f"wss://stream.{domain}.com/v5/public/linear"
        hft_cfg = config.get("hft_protections", {})
        self.ping_interval = hft_cfg.get("websocket_ping_interval_sec", 20)
        self.ping_timeout = hft_cfg.get("websocket_ping_timeout_sec", 10)

    async def start_streaming(self, tick_callback):
        self.is_running = True
        ssl_context = ssl.create_default_context()

        while self.is_running:
            try:
                self.log(f"[WS] Connecting to {self.ws_url}...")
                async with websockets.connect(
                    self.ws_url,
                    ssl=ssl_context,
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout,
                ) as ws:
                    topics = [f"publicTrade.{coin}USDT" for coin in self.monitored_coins]
                    await ws.send(json.dumps({"op": "subscribe", "args": topics}))
                    self.log(f"[WS] Subscribed: {', '.join(self.monitored_coins)}")

                    while self.is_running:
                        message = await ws.recv()
                        data = json.loads(message)

                        if "topic" not in data or "data" not in data:
                            continue

                        raw_topic = str(data["topic"])
                        coin = next((c for c in self.monitored_coins if c in raw_topic), None)
                        if not coin:
                            continue

                        for trade in data["data"]:
                            try:
                                price = float(trade["p"])
                                volume = float(trade["v"])
                                result = self.hft_processor.process_new_tick(coin, price, volume)
                                await tick_callback(result)
                            except (KeyError, TypeError, ValueError):
                                continue

            except Exception as exc:
                if self.is_running:
                    self.log(f"[WS] Connection lost: {exc}. Reconnect in 3s...")
                    await asyncio.sleep(3)

    def stop_streaming(self):
        self.is_running = False
        self.log("[WS] Stream stopped.")
