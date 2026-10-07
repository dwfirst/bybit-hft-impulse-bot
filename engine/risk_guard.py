import datetime
import json
import os
from pathlib import Path


STATE_FILE = Path("risk_guard_state.json")


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

        # Восстанавливаем состояние после рестарта
        self._load_state()

    # ---------- Persistence ----------

    def _load_state(self):
        """Загружает состояние с диска. Если день сменился — сбрасывает дневные счётчики."""
        if not STATE_FILE.exists():
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            saved_day_str = state.get("current_day")
            if not saved_day_str:
                return

            saved_day = datetime.date.fromisoformat(saved_day_str)
            today = datetime.datetime.now(datetime.timezone.utc).date()

            if saved_day != today:
                self.log(f"[RISK GUARD] State file is from {saved_day}, today is {today}. Skipping restore.")
                # Файл устаревший — просто перезапишем при следующем сохранении
                return

            self.current_day = saved_day
            self.today_realized_pnl = float(state.get("today_realized_pnl", 0.0))
            self.consecutive_losses = int(state.get("consecutive_losses", 0))
            self.is_locked_out = bool(state.get("is_locked_out", False))

            self.log(
                f"[RISK GUARD] State restored: pnl={self.today_realized_pnl:.2f} USDT, "
                f"consec_losses={self.consecutive_losses}, locked={self.is_locked_out}"
            )
        except Exception as e:
            self.log(f"[RISK GUARD] Failed to load state: {e}")

    def _save_state(self):
        """Атомарно сохраняет состояние на диск."""
        try:
            state = {
                "current_day": self.current_day.isoformat(),
                "today_realized_pnl": self.today_realized_pnl,
                "consecutive_losses": self.consecutive_losses,
                "is_locked_out": self.is_locked_out,
            }
            tmp = STATE_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp, STATE_FILE)
        except Exception as e:
            self.log(f"[RISK GUARD] Failed to save state: {e}")

    # ---------- Core logic ----------

    def check_new_day(self):
        now_day = datetime.datetime.now(datetime.timezone.utc).date()
        if now_day != self.current_day:
            self.log("[RISK GUARD] New day detected. Resetting loss counters.")
            self.current_day = now_day
            self.today_realized_pnl = 0.0
            if self.is_locked_out:
                self.is_locked_out = False
                self.log("[RISK GUARD] Lockout lifted with the start of a new day.")
            self._save_state()

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
            self._save_state()
            return False

        if self.consecutive_losses >= self.max_consecutive_losses:
            self.is_locked_out = True
            self.log(f"[CRITICAL RISK] Max consecutive losses reached ({self.consecutive_losses}). Trading paused!")
            self._save_state()
            return False

        self._save_state()
        return True

    def can_trade(self) -> bool:
        self.check_new_day()
        return not self.is_locked_out