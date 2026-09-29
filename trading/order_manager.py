import asyncio
import math


class TwinOrderExecutor:
    def __init__(self, config: dict, client_init, log_fn=print):
        self.config = config
        self.client_init = client_init
        self.log = log_fn
        self.sliders = config["sliders"]
        self.twin_config = config["advanced_features"]["twin_order_split"]

        self.coin_settings = {
            "XRP": {"leverage": 20, "step": 0.1},
            "SOL": {"leverage": 20, "step": 0.1},
            "ETH": {"leverage": 20, "step": 0.01},
            "BTC": {"leverage": 20, "step": 0.001},
        }

    def _round_to_step(self, value: float, step: float) -> float:
        if step <= 0:
            return value
        decimals = len(str(step).split(".")[1]) if "." in str(step) else 0
        return round(math.floor(value / step) * step, decimals)

    async def execute_twin_entry(
        self, coin: str, trigger_price: float, direction: str = "UP"
    ) -> dict:
        session = self.client_init.get_rest_session()
        symbol = f"{coin}USDT"
        is_short = direction == "UP"

        settings = self.coin_settings.get(coin, {"leverage": 20, "step": 0.01})
        leverage = settings["leverage"]
        step = settings["step"]

        total_margin = self.sliders["slider_6_fixed_margin_per_trade_usdt"]
        total_qty = (total_margin * leverage) / trigger_price

        raw_market = total_qty * (self.twin_config["first_entry_market_pct"] / 100.0)
        raw_limit = total_qty * (self.twin_config["second_limit_volume_pct"] / 100.0)

        qty_market = self._round_to_step(raw_market, step)
        qty_limit = self._round_to_step(raw_limit, step)

        if qty_market <= 0:
            qty_market = step
        if qty_limit <= 0:
            qty_limit = step

        distance = self.twin_config["second_limit_distance_pct"] / 100.0
        if is_short:
            ins_price = round(trigger_price * (1.0 + distance), 2)
            entry_side = "Sell"
            exit_side = "Buy"
            hard_stop = round(ins_price * 1.015, 2)
        else:
            ins_price = round(trigger_price * (1.0 - distance), 2)
            entry_side = "Buy"
            exit_side = "Sell"
            hard_stop = round(ins_price * 0.985, 2)

        try:
            try:
                await asyncio.to_thread(
                    session.set_leverage,
                    category="linear",
                    symbol=symbol,
                    buyLeverage=str(leverage),
                    sellLeverage=str(leverage),
                )
            except Exception:
                pass

            market_res = await asyncio.to_thread(
                session.place_order,
                category="linear",
                symbol=symbol,
                side=entry_side,
                orderType="Market",
                qty=str(qty_market),
                positionIdx=0,
            )
            direction_label = "Short" if is_short else "Long"
            self.log(
                f"[API] Market {direction_label} {coin} (Leverage: {leverage}x): qty={qty_market}"
            )

            await asyncio.sleep(0.25)
            real_entry_price = trigger_price
            try:
                pos_resp = await asyncio.to_thread(
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

            limit_res = await asyncio.to_thread(
                session.place_order,
                category="linear",
                symbol=symbol,
                side=entry_side,
                orderType="Limit",
                qty=str(qty_limit),
                price=str(ins_price),
                positionIdx=0,
            )
            self.log(
                f"[API] Limit Insurance {coin} @ {ins_price}, qty={qty_limit}, side={entry_side}"
            )

            try:
                await asyncio.to_thread(
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
                "limit_order_id": limit_res["result"]["orderId"],
                "average_entry_price": real_entry_price,
                "server_stop_loss": hard_stop,
                "is_insurance_filled": False,
            }
        except Exception as exc:
            self.log(f"[API ERROR] Critical order failure for {coin}: {exc}")
            return {"status": "FAILED", "coin": coin, "error": str(exc)}

    async def close_market_position(self, symbol: str, direction: str = "UP") -> bool:
        session = self.client_init.get_rest_session()
        try:
            positions = await asyncio.to_thread(
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

            await asyncio.to_thread(
                session.place_order,
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(size),
                positionIdx=0,
                reduceOnly=True,
            )
            self.log(
                f"[API] Position {symbol} closed via Market, qty={size}, side={close_side}"
            )
            return True
        except Exception as exc:
            self.log(f"[API ERROR] Closing {symbol} failed: {exc}")
            return False

    async def cancel_all_orders_for_safety(self):
        session = self.client_init.get_rest_session()
        try:
            await asyncio.to_thread(
                session.cancel_all_orders,
                category="linear",
                settleCoin="USDT",
            )
            self.log("[API] All limit orders cancelled (Kill Switch).")
        except Exception as exc:
            self.log(f"[API ERROR] Kill Switch failed: {exc}")