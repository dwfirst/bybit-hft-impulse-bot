import asyncio


class PositionTracker:
    def __init__(self, config: dict, order_manager, risk_guard=None, log_fn=print):
        self.config = config
        self.order_manager = order_manager
        self.risk_guard = risk_guard
        self.log = log_fn
        self.sliders = config["sliders"]
        self.trailing_activation_pct = self.sliders["slider_8_trailing_activation_pct"]
        self.instability_rollback_pct = self.sliders["slider_9_instability_rollback_exit_pct"]

        self.current_position = None
        self.is_trailing_active = False
        self.local_best_profit_price = 0.0
        self._tracking_task = None

    def _clear_position(self):
        self.current_position = None
        self.is_trailing_active = False
        self.local_best_profit_price = 0.0

    async def track_position_loop(self, opened_position_report: dict, hft_processor):
        if self._tracking_task and not self._tracking_task.done():
            self.log("[TRACKER] Another position tracking is already active.")
            return

        self._tracking_task = asyncio.create_task(
            self._track(opened_position_report, hft_processor)
        )
        await self._tracking_task

    def _report_pnl_to_risk_guard(self, pnl_pct: float, entry_price: float, exit_price: float):
        if self.risk_guard is None:
            return
        try:
            margin = self.sliders.get("slider_6_fixed_margin_per_trade_usdt", 1.5)
            leverage = 10
            if self.current_position:
                leverage = self.current_position.get("leverage", 10)
            notional = margin * leverage
            pnl_usdt = notional * (pnl_pct / 100.0)
            deposit = self.config.get("risk_management", {}).get("deposit_usdt", 100.0)
            self.risk_guard.register_trade_result(pnl_usdt, deposit_usdt=deposit)
            self.log(
                f"[TRACKER] PnL reported to RiskGuard: "
                f"{pnl_pct:.3f}% ≈ {pnl_usdt:.4f} USDT"
            )
        except Exception as e:
            self.log(f"[TRACKER WARNING] Failed to report PnL: {e}")

    async def _track(self, opened_position_report: dict, hft_processor):
        self.current_position = opened_position_report
        self.is_trailing_active = False
        trailing_target = self.trailing_activation_pct

        direction = self.current_position.get("direction", "UP")
        is_short = direction == "UP"

        if self.current_position.get("is_insurance_filled"):
            trailing_target /= 2.0
            self.log(f"[TRACKER] Insurance filled. Trailing target updated to: {trailing_target}%")

        coin = self.current_position["coin"]
        symbol = self.current_position["symbol"]
        avg_entry = self.current_position["average_entry_price"]
        self.local_best_profit_price = avg_entry
        self.log(
            f"[TRACKER] Tracking active for {coin} ({direction}), entry @ {avg_entry}"
        )

        try:
            while self.current_position:
                await asyncio.sleep(0.05)

                current_price = hft_processor.get_latest_price(coin)
                if current_price is None:
                    continue

                # For SHORT: best profit = lowest price. For LONG: best profit = highest price.
                if is_short:
                    if current_price < self.local_best_profit_price:
                        self.local_best_profit_price = current_price
                    current_profit_pct = ((avg_entry - current_price) / avg_entry) * 100
                else:
                    if current_price > self.local_best_profit_price:
                        self.local_best_profit_price = current_price
                    current_profit_pct = ((current_price - avg_entry) / avg_entry) * 100

                if not self.is_trailing_active and current_profit_pct >= trailing_target:
                    self.is_trailing_active = True
                    self.log(
                        f"[TRACKER] Profit reached {current_profit_pct:.2f}% — trailing activated"
                    )

                if self.is_trailing_active:
                    if is_short:
                        rollback_threshold = self.local_best_profit_price * (
                            1 + self.instability_rollback_pct / 100.0
                        )
                        hit = current_price >= rollback_threshold
                    else:
                        rollback_threshold = self.local_best_profit_price * (
                            1 - self.instability_rollback_pct / 100.0
                        )
                        hit = current_price <= rollback_threshold

                    if hit:
                        self.log(
                            f"[TRACKER] Rebound exit triggered: {current_price:.4f} "
                            f"(threshold {rollback_threshold:.4f})"
                        )
                        closed = await self.order_manager.close_market_position(
                            symbol, direction
                        )
                        if closed:
                            pnl = (
                                (avg_entry - current_price) / avg_entry * 100.0
                                if is_short
                                else (current_price - avg_entry) / avg_entry * 100.0
                            )
                            self._report_pnl_to_risk_guard(pnl, avg_entry, current_price)
                        hft_processor.reset_coin(coin)
                        break
        except Exception as e:
            self.log(f"[TRACKER ERROR] Error in tracking loop: {e}")
            try:
                await self.order_manager.close_market_position(
                    symbol, self.current_position.get("direction", "UP")
                )
            except Exception:
                pass
            hft_processor.reset_coin(coin)
        finally:
            self._clear_position()

    async def emergency_close_all(self, hft_processor):
        if self.current_position:
            symbol = self.current_position["symbol"]
            coin = self.current_position["coin"]
            direction = self.current_position.get("direction", "UP")
            await self.order_manager.close_market_position(symbol, direction)
            hft_processor.reset_coin(coin)
        self._clear_position()