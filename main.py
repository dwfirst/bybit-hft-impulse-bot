import os
import sys
import json
import asyncio

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

for key in [
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "all_proxy", "ALL_PROXY", "NO_PROXY", "no_proxy",
]:
    os.environ.pop(key, None)

from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop

from engine.time_sync import TimeSynchronizer
from engine.hft_processor import HFTProcessor
from engine.ws_connector import WebSocketConnector
from trading.client_init import BybitClientInitializer
from trading.order_manager import TwinOrderExecutor
from trading.position_tracker import PositionTracker
from ui.interface import TradingTerminalUI
from ui.popup_trigger import PopupSignalTrigger


class ImpulseCatcherOrchestrator:
    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        domain = self.config["api"].get("domain", "bybit")
        self.log_fn = print
        self._busy_coins = set()
        self._tick_counter = 0

        self.time_sync = TimeSynchronizer(domain=domain)
        self.hft_processor = HFTProcessor(self.config)
        self.client_init = BybitClientInitializer(self.config)
        self.order_manager = TwinOrderExecutor(self.config, self.client_init, self._log)
        self.position_tracker = PositionTracker(self.config, self.order_manager, self._log)
        self.popup = PopupSignalTrigger(self.config)
        self.ws_connector = WebSocketConnector(self.config, self.hft_processor, self._log)

    def set_log_callback(self, callback):
        self.log_fn = callback
        self.order_manager.log = callback
        self.position_tracker.log = callback
        self.ws_connector.log = callback

    def _log(self, text: str):
        print(text)
        try:
            with open("bot_debug.log", "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass
            
        if self.log_fn and self.log_fn is not print:
            try:
                self.log_fn(text)
            except Exception:
                pass

    async def run_network_layers(self):
        self._log("[SYSTEM] time sync with bybit...")
        await self.time_sync.sync_with_bybit()
        self._log("[SYSTEM] start websocket stream...")
        await self.ws_connector.start_streaming(self._handle_tick)

    async def _handle_tick(self, tick_data: dict):
        status = tick_data.get("status")
        coin = tick_data.get("coin")
        price = tick_data.get("price") or tick_data.get("trigger_price")

        self._tick_counter += 1
        if self._tick_counter % 50 == 0 and price is not None:
            self._log(f"[ТИК] {coin} = {price}")

        if status == "TRIGGERED":
            change = tick_data.get("change_pct", 0)
            self._log(
                f"\n[⚡ ИМПУЛЬС] {coin} +{change:.2f}% — "
                f"ожидание отката {self.config['sliders']['slider_4_rebound_entry_trigger_pct']}%"
            )
            await self.popup.trigger_visual_and_audio_alert(coin, price)
            return

        if status != "ENTRY":
            return

        if coin in self._busy_coins or self.position_tracker.current_position:
            return

        self._busy_coins.add(coin)
        try:
            self._log(f"\n[⚡ ENTRY] {coin} @ {price} — sending twin-short orders...")
            order_report = await self.order_manager.execute_twin_short_entry(coin, price)
            if order_report.get("status") == "OPENED":
                asyncio.create_task(
                    self.position_tracker.track_position_loop(order_report, self.hft_processor)
                )
            else:
                self.hft_processor.reset_coin(coin)
        finally:
            self._busy_coins.discard(coin)

    def trigger_kill_switch(self):
        self._log("\n[⚠️ KILL SWITCH] emergency stop!")
        loop = asyncio.get_event_loop()
        loop.create_task(self._kill_switch_async())

    async def _kill_switch_async(self):
        await self.order_manager.cancel_all_orders_for_safety()
        await self.position_tracker.emergency_close_all(self.hft_processor)
        self.ws_connector.stop_streaming()
        self._log("[⚠️ KILL SWITCH] stopped.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    orchestrator = ImpulseCatcherOrchestrator(config_path)
    ui = TradingTerminalUI(orchestrator.config, orchestrator.trigger_kill_switch)
    orchestrator.set_log_callback(ui.append_log)
    ui.show()

    with loop:
        loop.create_task(orchestrator.run_network_layers())
        loop.run_forever()
