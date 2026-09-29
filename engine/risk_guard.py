import datetime


class RiskGuard:
    def __init__(self, config: dict, log_fn=print):
        self.config = config
        self.log = log_fn
        rm_cfg = config.get("risk_management", {})
        
        self.daily_max_loss_pct = rm_cfg.get("daily_max_loss_pct", 5.0)
        self.max_consecutive_losses = rm_cfg.get("max_consecutive_losses", 3)
        
        self.consecutive_losses = 0
        self.today_realized_pnl = 0.0
        self.current_day = datetime.datetime.now(datetime.timezone.utc).date()
        self.is_locked_out = False

    def check_new_day(self):
        now_day = datetime.datetime.now(datetime.timezone.utc).date()
        if now_day != self.current_day:
            self.log("[RISK GUARD] New day detected. Resetting loss counters.")
            self.current_day = now_day
            self.today_realized_pnl = 0.0
            if self.is_locked_out:
                self.is_locked_out = False
                self.log("[RISK GUARD] Lockout lifted with the start of a new day.")

    def register_trade_result(self, pnl_usdt: float, deposit_usdt: float = 1000.0) -> bool:
        self.check_new_day()
        if self.is_locked_out:
            return False

        self.today_realized_pnl += pnl_usdt
        max_loss_allowed_usdt = deposit_usdt * (self.daily_max_loss_pct / 100.0)

        if pnl_usdt < 0:
            self.consecutive_losses += 1
            self.log(f"[RISK GUARD] Loss: {pnl_usdt:.2f} USDT. Consecutive losses: {self.consecutive_losses}")
        else:
            self.consecutive_losses = 0

        if self.today_realized_pnl <= -abs(max_loss_allowed_usdt):
            self.is_locked_out = True
            self.log(f"[CRITICAL RISK] Daily drawdown limit exceeded ({self.today_realized_pnl:.2f} USDT). TRADING LOCKED OUT!")
            return False

        if self.consecutive_losses >= self.max_consecutive_losses:
            self.is_locked_out = True
            self.log(f"[CRITICAL RISK] Max consecutive losses reached ({self.consecutive_losses}). Trading paused!")
            return False

        return True

    def can_trade(self) -> bool:
        self.check_new_day()
        return not self.is_locked_out
