import collections
import time


class HFTProcessor:
    def __init__(self, config: dict):
        self.config = config
        self.sliders = config["sliders"]
        self.rm_config = config["risk_management"]
        self.monitored_coins = config["assets"]["monitored_coins"]

        self.ticks_buffer = collections.deque()
        self.latest_prices = {coin: None for coin in self.monitored_coins}
        self.coin_states = {coin: "SCANNING" for coin in self.monitored_coins}
        self.peak_prices = {coin: 0.0 for coin in self.monitored_coins}
        self.trigger_directions = {coin: None for coin in self.monitored_coins}
        self.average_2h_volume = 1000.0

    def get_latest_price(self, coin: str) -> float | None:
        return self.latest_prices.get(coin)

    def reset_coin(self, coin: str):
        self.coin_states[coin] = "SCANNING"
        self.peak_prices[coin] = 0.0
        self.trigger_directions[coin] = None

    def sync_states_with_exchange(self, active_positions: list, log_fn=print):
        try:
            active_symbols = set()
            for pos in active_positions:
                symbol = pos.get("symbol", "")
                size = float(pos.get("size", 0))
                if size > 0:
                    active_symbols.add(symbol)

            for coin in self.monitored_coins:
                symbol = f"{coin}USDT"
                if symbol in active_symbols:
                    self.coin_states[coin] = "IN_POSITION"
                    log_fn(f"[STATE SYNC] Warning: Active position detected on exchange for {symbol}. State restored to IN_POSITION.")
                else:
                    if self.coin_states[coin] == "IN_POSITION":
                        self.reset_coin(coin)
        except Exception as e:
            log_fn(f"[STATE ERROR] Position synchronization failed: {e}")

    def process_new_tick(self, coin: str, price: float, volume: float) -> dict:
        now_ms = int(time.time() * 1000)
        self.latest_prices[coin] = price
        self.ticks_buffer.append((now_ms, price, volume, coin))

        while self.ticks_buffer and self.ticks_buffer[0][0] < now_ms - 60000:
            self.ticks_buffer.popleft()

        state = self.coin_states[coin]

        if state == "SCANNING":
            signal = self._detect_momentum(coin, price, now_ms)
            if signal:
                self.coin_states[coin] = "TRIGGERED"
                self.peak_prices[coin] = price
                self.trigger_directions[coin] = signal.get("direction", "UP")
                return signal
            return {"status": "SCANNING", "coin": coin, "price": price}

        if state == "TRIGGERED":
            direction = self.trigger_directions.get(coin, "UP")
            if direction == "UP":
                if price > self.peak_prices[coin]:
                    self.peak_prices[coin] = price
            else:
                if self.peak_prices[coin] == 0.0 or price < self.peak_prices[coin]:
                    self.peak_prices[coin] = price

            rebound_pct = self.sliders["slider_4_rebound_entry_trigger_pct"]
            if direction == "UP":
                rebound_trigger = self.peak_prices[coin] * (1.0 - rebound_pct / 100.0)
                hit = price <= rebound_trigger
            else:
                rebound_trigger = self.peak_prices[coin] * (1.0 + rebound_pct / 100.0)
                hit = price >= rebound_trigger

            if hit:
                self.coin_states[coin] = "IN_POSITION"
                return {
                    "status": "ENTRY",
                    "coin": coin,
                    "direction": direction,
                    "trigger_price": price,
                    "peak_price": self.peak_prices[coin],
                    "atr_multiplier": self.rm_config["atr_stop_multiplier"],
                }

            return {"status": "WAIT_REBOUND", "coin": coin, "price": price}

        return {"status": state, "coin": coin, "price": price}

    def _detect_momentum(self, coin: str, price: float, now_ms: int) -> dict | None:
        sec_volume = sum(
            tick[2] for tick in self.ticks_buffer
            if tick[0] >= now_ms - 1000 and tick[3] == coin
        )
        if sec_volume < self.average_2h_volume * 0.05:
            return None

        window_ms = int(self.sliders["slider_2_panic_window_sec"] * 1000)
        historical_ticks = [
            tick for tick in self.ticks_buffer
            if tick[0] >= now_ms - window_ms and tick[3] == coin
        ]
        if len(historical_ticks) < 2:
            return None

        start_price = historical_ticks[0][1]
        if start_price <= 0:
            return None

        price_change_pct = (price - start_price) / start_price * 100
        threshold = self.sliders["slider_1_momentum_threshold_pct"]

        if price_change_pct >= threshold:
            return {
                "status": "TRIGGERED",
                "coin": coin,
                "trigger_price": price,
                "change_pct": price_change_pct,
                "direction": "UP",
                "atr_multiplier": self.rm_config["atr_stop_multiplier"],
            }
        if price_change_pct <= -threshold:
            return {
                "status": "TRIGGERED",
                "coin": coin,
                "trigger_price": price,
                "change_pct": price_change_pct,
                "direction": "DOWN",
                "atr_multiplier": self.rm_config["atr_stop_multiplier"],
            }
        return None