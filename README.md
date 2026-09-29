# ⚡ ImpulseCatcher V5

> Research prototype of a semi-automated HFT terminal for scalping Bybit perpetual futures. Catches the first micro-rebound after a liquidation cascade.

**Status: prototype / work in progress. Not production-ready. No live PnL published.**

---

## ⚠️ Disclaimer

Not financial advice. Leveraged futures trading can result in total loss of deposit. The author is not responsible for losses. Before any live use:

- Run for 48h on Bybit Testnet with micro size.
- Use API keys with **Withdrawal disabled**.
- Understand funding, slippage, and rate limits.

---

## 🎯 Concept

The bot does not predict trends. It exploits a microstructure pattern at the climax of a panic move:

```
Impulse ➡️ Exhaustion ➡️ Liquidation cascade ➡️ V-shaped rebound
```

It listens to tick-by-tick `publicTrade`, detects momentum acceleration, and enters on the first pullback from the peak. Exit is driven by an instability model: when price retraces from the local peak of unrealized profit by a set amount, the position closes.

**No candle-close logic — raw ticks only.**

---

## 🧠 What's implemented

- **Async engine** (asyncio + pybit V5 + qasync + PyQt6).
- **Tick-based momentum detection** with UP/DOWN direction.
- **Chase-style entry**: Market scout (40%) + Limit add (60%) with server-side SL.
- **Direction-aware orders**: Long or Short based on signal direction.
- **RiskGuard**: daily max loss, max consecutive losses, day rollover.
- **PnL reporting** back to RiskGuard on every closed position.
- **Real avgPrice** read from exchange after entry.
- **Trailing exit** driven by instability rollback (ATR-normalization planned).
- **Kill Switch (F12)**: cancel all orders + close all positions.

## 🚧 What's NOT implemented yet

- `liquidation` stream subscription (currently only `publicTrade`).
- Anti-FOMO filter (`slider_5` in config is not enforced).
- ATR-based dynamic stop (currently fixed 1.5%).
- Real-time API throttle (`api_throttle_ms` not used).
- Space/Escape hotkeys + modal popup.
- ATR-normalized trailing exit.
- Persistence of RiskGuard state across restarts.
- Dynamic `recvWindow` (method exists, not wired).
- Instruments-info rounding for Price/Qty.

---

## 🏗 Architecture

```
main.py  →  orchestrator
  ├── engine/
  │   ├── time_sync.py       NTP + recvWindow
  │   ├── ws_connector.py    WebSocket publicTrade
  │   ├── hft_processor.py   momentum detection, direction, peak tracking
  │   └── risk_guard.py      daily limits, consecutive losses
  ├── trading/
  │   ├── client_init.py     pybit V5 session
  │   ├── order_manager.py   Twin order + server SL
  │   └── position_tracker.py breakeven, trailing, instability exit
  └── ui/
      ├── interface.py       PyQt6 sliders + Kill Switch
      └── popup_trigger.py   alert (print + beep)
```

---

## 🎛 Config

Copy `config.example.json` to `config.json` and fill in:

- `api.api_key`, `api.api_secret` — **use testnet first**.
- `risk_management.deposit_usdt` — your actual starting balance.
- `assets.monitored_coins` — symbols to scan.

---

## 🚀 Quick start

```bash
git clone https://github.com/dwfirst/bybit-hft-impulse-bot.git
cd bybit-hft-impulse-bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `config.example.json` to `config.json`, edit, then:

```bash
python main.py
```

**Hotkeys:** `F12` — emergency stop.

---

## 📋 Roadmap

- [x] Async engine, WS, PyQt6 integration
- [x] Direction-aware twin orders
- [x] RiskGuard + PnL reporting
- [x] Real avgPrice from exchange
- [ ] Liquidation stream
- [ ] ATR-based stop and trailing
- [ ] Anti-FOMO filter
- [ ] Space / Escape hotkeys + modal popup
- [ ] API throttle + rate-limit backoff
- [ ] Instruments-info rounding
- [ ] 48h Testnet run

---

## 📄 License

MIT — see [LICENSE](LICENSE).