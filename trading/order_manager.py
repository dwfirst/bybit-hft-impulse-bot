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
            "XRP": {"leverage": 20, "step": 0.5},
            "SOL": {"leverage": 35, "step": 0.1},
            "ETH": {"leverage": 50, "step": 0.01},
            "BTC": {"leverage": 80, "step": 0.001},
        }

    def _round_to_step(self, value: float, step: float) -> float:
        if step <= 0:
            return value
        decimals = len(str(step).split(".")[1]) if "." in str(step) else 0
        return round(math.floor(value / step) * step, decimals)

    async def execute_twin_short_entry(self, coin: str, trigger_price: float) -> dict:
        session = self.client_init.get_rest_session()
        symbol = f"{coin}USDT"

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

        ins_price = round(trigger_price * (1.0 + self.twin_config["second_limit_distance_pct"] / 100.0), 2)
        hard_stop = round(ins_price * 1.015, 2)

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
                side="Sell",
                orderType="Market",
                qty=str(qty_market),
                positionIdx=0,
            )
            self.log(f"[API] Market Short {coin} (Leverage: {leverage}x): qty={qty_market}")

            limit_res = await asyncio.to_thread(
                session.place_order,
                category="linear",
                symbol=symbol,
                side="Sell",
                orderType="Limit",
                qty=str(qty_limit),
                price=str(ins_price),
                positionIdx=0,
            )
            self.log(f"[API] Limit Insurance {coin} @ {ins_price}, qty={qty_limit}")

            try:
                await asyncio.to_thread(
                    session.set_trading_stop,
                    category="linear",
                    symbol=symbol,
                    tpslMode="Full",
                    stopLoss=str(hard_stop),
                    slTriggerBy="LastPrice",
                    positionIdx=0
                )
                self.log(f"[API SAFETY] Server Stop Loss set successfully: {hard_stop}")
            except Exception as sl_err:
                self.log(f"[API WARNING] Failed to set general TP/SL on position: {sl_err}")

            return {
                "status": "OPENED",
                "coin": coin,
                "symbol": symbol,
                "market_order_id": market_res["result"]["orderId"],
                "limit_order_id": limit_res["result"]["orderId"],
                "average_entry_price": trigger_price,
                "server_stop_loss": hard_stop,
                "is_insurance_filled": False,
            }
        except Exception as exc:
            self.log(f"[API ERROR] Critical order failure for {coin}: {exc}")
            return {"status": "FAILED", "coin": coin, "error": str(exc)}

    async def close_market_position(self, symbol: str) -> bool:
        session = self.client_init.get_rest_session()
        try:
            positions = await asyncio.to_thread(
                session.get_positions,
                category="linear",
                symbol=symbol,
            )
            pos_list = positions.get("result", {}).get("list", [])
            size = 0.0
            for pos in pos_list:
                size = max(size, abs(float(pos.get("size", 0))))

            if size <= 0:
                self.log(f"[API] No active position found for {symbol}")
                return True

            await asyncio.to_thread(
                session.place_order,
                category="linear",
                symbol=symbol,
                side="Buy",
                orderType="Market",
                qty=str(size),
                positionIdx=0,
                reduceOnly=True,
            )
            self.log(f"[API] Position {symbol} closed via Market, qty={size}")
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

