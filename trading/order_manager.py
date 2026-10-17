import asyncio
import math
import time
import uuid


class TwinOrderExecutor:
    def __init__(self, config: dict, client_init, log_fn=print):
        self.config = config
        self.client_init = client_init
        self.log = log_fn
        self.sliders = config["sliders"]
        self.twin_config = config["advanced_features"]["twin_order_split"]

        # --- Entry guard (P3: dedup) ---
        self._entry_locks: dict[str, asyncio.Lock] = {}
        self._entry_cooldown: dict[str, float] = {}
        self.entry_cooldown_sec = float(self.sliders.get("slider_entry_cooldown_sec", 60.0))
        self._instruments: dict[str, dict] = {}

        self.coin_settings = {
            "XRP": {"leverage": 20, "step": 0.1},
            "SOL": {"leverage": 20, "step": 0.1},
            "ETH": {"leverage": 20, "step": 0.01},
            "BTC": {"leverage": 20, "step": 0.001},
        }

    # ---------- Helpers ----------

    def _round_to_step(self, value: float, step: float) -> float:
        if step <= 0:
            return value
        decimals = len(str(step).split(".")[1]) if "." in str(step) else 0
        return round(math.floor(value / step) * step, decimals)

    @staticmethod
    def _make_order_link_id(coin: str, tag: str) -> str:
        """Генерит уникальный orderLinkId.

        Bybit ограничения: до 36 символов, только A-Z a-z 0-9 _ -
        """
        ts = int(time.time() * 1000) % 10_000_000_000  # 10 цифр
        rnd = uuid.uuid4().hex[:6]
        link = f"IC-{coin}-{tag}-{ts}-{rnd}"[:36]
        return link

    async def warmup_instruments(self) -> None:
        """Loads qtyStep/tickSize for all coin_settings from Bybit instruments-info."""
        session = self.client_init.get_rest_session()
        for coin in self.coin_settings:
            symbol = f"{coin}USDT"
            try:
                resp = await self._rest(
                    session.get_instruments_info,
                    category="linear",
                    symbol=symbol,
                )
                item = resp["result"]["list"][0]
                qty_step = float(item["lotSizeFilter"]["qtyStep"])
                tick_size = float(item["priceFilter"]["tickSize"])
                self._instruments[symbol] = {"qtyStep": qty_step, "tickSize": tick_size}
                self.log(f"[INSTR] {symbol}: qtyStep={qty_step}, tickSize={tick_size}")
            except Exception as e:
                self.log(f"[INSTR WARNING] {symbol}: {e}. Using hardcoded step.")

    def _round_qty(self, symbol: str, qty: float) -> float:
        info = self._instruments.get(symbol)
        if info:
            step = info["qtyStep"]
            return math.floor(qty / step) * step
        coin = symbol.replace("USDT", "")
        step = self.coin_settings.get(coin, {}).get("step", 0.01)
        return self._round_to_step(qty, step)

    def _round_price(self, symbol: str, price: float) -> float:
        info = self._instruments.get(symbol)
        if info:
            step = info["tickSize"]
            return round(price / step) * step
        return round(price, 2)

    async def _rest(self, func, *args, **kwargs):
        """Прокси через throttled_call."""
        return await self.client_init.throttled_call(func, *args, **kwargs)

    # ---------- Entry ----------

    async def execute_twin_entry(
        self, coin: str, trigger_price: float, direction: str = "UP"
    ) -> dict:
        symbol = f"{coin}USDT"

        # --- P3: entry guard ---
        lock = self._entry_locks.setdefault(symbol, asyncio.Lock())
        if lock.locked():
            self.log(f"[GUARD] {coin} entry in-flight - reject")
            return {
                "status": "rejected",
                "coin": coin,
                "reason": "duplicate_entry_in_flight",
            }

        now = time.time()
        cd_until = self._entry_cooldown.get(symbol, 0.0)
        if now < cd_until:
            remaining = round(cd_until - now, 1)
            self.log(f"[GUARD] {coin} cooldown {remaining}s - reject")
            return {
                "status": "rejected",
                "coin": coin,
                "reason": "cooldown",
                "cooldown_remaining_sec": remaining,
            }

        async with lock:
            result = await self._execute_twin_entry_inner(
                symbol, coin, trigger_price, direction
            )
            if result.get("status") == "OPENED":
                self._entry_cooldown[symbol] = time.time() + self.entry_cooldown_sec
            return result

    async def _execute_twin_entry_inner(
        self, symbol: str, coin: str, trigger_price: float, direction: str = "UP"
    ) -> dict:
        session = self.client_init.get_rest_session()
        is_short = direction == "UP"

        settings = self.coin_settings.get(coin, {"leverage": 20, "step": 0.01})
        leverage = settings["leverage"]
        step = settings["step"]

        total_margin = self.sliders["slider_6_fixed_margin_per_trade_usdt"]
        total_qty = (total_margin * leverage) / trigger_price

        raw_market = total_qty * (self.twin_config["first_entry_market_pct"] / 100.0)
        raw_limit = total_qty * (self.twin_config["second_limit_volume_pct"] / 100.0)

        qty_market = self._round_qty(symbol, raw_market)
        qty_limit = self._round_qty(symbol, raw_limit)

        if qty_market <= 0:
            qty_market = step
        if qty_limit <= 0:
            qty_limit = step

        distance = self.twin_config["second_limit_distance_pct"] / 100.0
        if is_short:
            ins_price = self._round_price(symbol, trigger_price * (1.0 + distance))
            entry_side = "Sell"
            exit_side = "Buy"
            hard_stop = self._round_price(symbol, ins_price * 1.015)
        else:
            ins_price = self._round_price(symbol, trigger_price * (1.0 - distance))
            entry_side = "Buy"
            exit_side = "Sell"
            hard_stop = self._round_price(symbol, ins_price * 0.985)

        market_link = self._make_order_link_id(coin, "MKT")
        limit_link = self._make_order_link_id(coin, "LMT")

        try:
            try:
                await self._rest(
                    session.set_leverage,
                    category="linear",
                    symbol=symbol,
                    buyLeverage=str(leverage),
                    sellLeverage=str(leverage),
                )
            except Exception:
                pass

            market_res = await self._rest(
                session.place_order,
                category="linear",
                symbol=symbol,
                side=entry_side,
                orderType="Market",
                qty=str(qty_market),
                positionIdx=0,
                orderLinkId=market_link,
            )
            direction_label = "Short" if is_short else "Long"
            self.log(
                f"[API] Market {direction_label} {coin} (Leverage: {leverage}x): "
                f"qty={qty_market}, linkId={market_link}"
            )

            # === AMR: Auto-Add Margin для защиты от ликвидации ===
            try:
                await self._rest(
                    session.set_auto_add_margin,
                    category="linear",
                    symbol=symbol,
                    autoAddMargin=1,
                    positionIdx=0,
                )
                self.log(f"[API SAFETY] AMR enabled for {coin}")
            except Exception as amr_err:
                self.log(f"[API WARNING] Failed to enable AMR: {amr_err}")
            # === /AMR ===

            await asyncio.sleep(0.25)
            real_entry_price = trigger_price
            try:
                pos_resp = await self._rest(
                    session.get_positions,
                    category="linear",
                    symbol=symbol,
                )
                for pos in pos_resp.get("result", {}).get("list", []):
                    if abs(float(pos.get("size", 0))) > 0:
                        real_entry_price = float(pos.get("avgPrice", trigger_price))
                        break
                self.log(f"[API] Real avg entry for {coin}: {real_entry_price}")
            except Exception as pos_err:
                self.log(
                    f"[API WARNING] Could not fetch avg entry: {pos_err}. Using trigger price."
                )

            limit_res = await self._rest(
                session.place_order,
                category="linear",
                symbol=symbol,
                side=entry_side,
                orderType="Limit",
                qty=str(qty_limit),
                price=str(ins_price),
                positionIdx=0,
                orderLinkId=limit_link,
            )
            self.log(
                f"[API] Limit Insurance {coin} @ {ins_price}, qty={qty_limit}, "
                f"side={entry_side}, linkId={limit_link}"
            )

            # === LIQ SAFETY: проверка liqPrice перед SL ===
            try:
                pos_resp = await self._rest(
                    session.get_positions,
                    category="linear",
                    symbol=symbol,
                )
                for pos in pos_resp.get("result", {}).get("list", []):
                    if abs(float(pos.get("size", 0))) > 0:
                        liq_price = float(pos.get("liqPrice", 0) or 0)
                        if liq_price > 0:
                            if is_short and liq_price <= hard_stop:
                                self.log(
                                    f"[LIQ SAFETY] Liq {liq_price} <= SL {hard_stop}. "
                                    f"Closing {coin} to avoid liquidation."
                                )
                                await self.close_market_position(symbol, direction)
                                return {"status": "FAILED", "coin": coin, "error": "SL beyond liquidation"}
                            if not is_short and liq_price >= hard_stop:
                                self.log(
                                    f"[LIQ SAFETY] Liq {liq_price} >= SL {hard_stop}. "
                                    f"Closing {coin} to avoid liquidation."
                                )
                                await self.close_market_position(symbol, direction)
                                return {"status": "FAILED", "coin": coin, "error": "SL beyond liquidation"}
                        break
            except Exception as liq_err:
                self.log(f"[API WARNING] Liq check failed: {liq_err}")
            # === /LIQ SAFETY ===

            try:
                await self._rest(
                    session.set_trading_stop,
                    category="linear",
                    symbol=symbol,
                    tpslMode="Full",
                    stopLoss=str(hard_stop),
                    slTriggerBy="LastPrice",
                    positionIdx=0,
                )
                self.log(f"[API SAFETY] Server Stop Loss set: {hard_stop}")
            except Exception as sl_err:
                self.log(f"[API WARNING] Failed to set general TP/SL on position: {sl_err}")

            return {
                "status": "OPENED",
                "coin": coin,
                "symbol": symbol,
                "direction": direction,
                "exit_side": exit_side,
                "market_order_id": market_res["result"]["orderId"],
                "market_order_link_id": market_link,
                "limit_order_id": limit_res["result"]["orderId"],
                "limit_order_link_id": limit_link,
                "average_entry_price": real_entry_price,
                "server_stop_loss": hard_stop,
                "is_insurance_filled": False,
            }
        except Exception as exc:
            self.log(f"[API ERROR] Critical order failure for {coin}: {exc}")
            return {"status": "FAILED", "coin": coin, "error": str(exc)}


    # ---------- Exit ----------

    async def close_market_position(self, symbol: str, direction: str = "UP") -> bool:
        session = self.client_init.get_rest_session()
        close_link = self._make_order_link_id(symbol.replace("USDT", ""), "CLS")
        try:
            positions = await self._rest(
                session.get_positions,
                category="linear",
                symbol=symbol,
            )
            pos_list = positions.get("result", {}).get("list", [])
            size = 0.0
            side = None
            for pos in pos_list:
                sz = abs(float(pos.get("size", 0)))
                if sz > 0:
                    size = sz
                    side = pos.get("side", None)
                    break

            if size <= 0:
                self.log(f"[API] No active position found for {symbol}")
                return True

            if side == "Buy":
                close_side = "Sell"
            elif side == "Sell":
                close_side = "Buy"
            else:
                close_side = "Buy" if direction == "UP" else "Sell"

            await self._rest(
                session.place_order,
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(size),
                positionIdx=0,
                reduceOnly=True,
                orderLinkId=close_link,
            )
            self.log(
                f"[API] Position {symbol} closed via Market, qty={size}, "
                f"side={close_side}, linkId={close_link}"
            )
            return True
        except Exception as exc:
            self.log(f"[API ERROR] Closing {symbol} failed: {exc}")
            return False

    # ---------- Emergency ----------

    async def cancel_all_orders_for_safety(self):
        session = self.client_init.get_rest_session()
        try:
            await self._rest(
                session.cancel_all_orders,
                category="linear",
                settleCoin="USDT",
            )
            self.log("[API] All limit orders cancelled (Kill Switch).")
        except Exception as exc:
            self.log(f"[API ERROR] Kill Switch failed: {exc}")