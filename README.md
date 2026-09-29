# ⚡ ImpulseCatcher V5

> Research prototype of a semi-automated HFT terminal for scalping Bybit perpetual futures. Catches the first micro-rebound after a liquidation cascade.

**Status: prototype / work in progress. Not production-ready. No live PnL published.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.x-41CD52?logo=qt&logoColor=white)](https://pypi.org/project/PyQt6/)
[![Bybit V5](https://img.shields.io/badge/Bybit-API%20V5-F7A600)](https://bybit-exchange.github.io/docs/v5/intro)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ⚠️ Disclaimer

**This is not financial advice and not a money printer.** It is an experimental research tool for traders who understand derivatives, funding, liquidations, and slippage.

- Leveraged futures trading can result in **total loss of your deposit**.
- The author is **not responsible** for losses, API errors, network failures, or bugs.
- Before any live use:
  - Run for **48h on Bybit Testnet** with micro size.
  - Use API keys with **`Withdrawal — Disabled`**.
  - Understand funding, slippage, and exchange rate limits.
- **No live PnL is published.** All thresholds in this repo are design targets, not measured results.

---

## 🎯 Concept

The bot does **not** try to predict trends. It exploits a specific microstructure pattern at the climax of a panic move:

```
Impulse ➡️ Exhaustion ➡️ Liquidation cascade ➡️ V-shaped rebound
```

It consumes tick-by-tick `publicTrade` events, detects momentum acceleration, and enters on the first pullback from the peak. Exit is driven by an instability model: as soon as price retraces from the local peak of unrealized profit by a defined amount, the position is closed.

**No candle-close logic — raw ticks only.**

---

## 🧠 What's implemented

- **Async engine** — asyncio + `pybit` V5 + `qasync` + PyQt6.
- **Tick-based momentum detection** with explicit **UP / DOWN** direction.
- **Direction-aware orders** — Long or Short based on signal direction.
- **Twin entry** — Market scout (40%) + Limit add (60%) with a **server-side SL** attached to the position.
- **RiskGuard** — daily max loss, max consecutive losses, automatic day rollover.
- **PnL reporting** — every closed position reports realized PnL back to RiskGuard.
- **Real avgPrice** — read from the exchange after entry, used by the tracker for accurate trailing.
- **Trailing exit** — driven by instability rollback (percentage-based; ATR-normalization planned).
- **Kill Switch (F12)** — cancels all orders and closes all positions.

## 🚧 What's NOT implemented yet

- `liquidation` stream subscription — currently only `publicTrade`.
- Anti-FOMO filter (`slider_5_trend_exhaustion_limit_1m_candles`) — present in config, not enforced.
- ATR-based dynamic stop — currently fixed 1.5% in `order_manager`.
- ATR-normalized trailing exit — currently percentage-based.
- True **Chase Limit** re-posting — currently Market scout + static Limit add.
- Real-time API throttle (`api_throttle_ms`) — not wired to REST calls.
- Space / Escape hotkeys and a modal popup — `F12` works only when the window has focus.
- Dynamic `recvWindow` — `time_sync.get_recv_window` exists but is not connected to `client_init`.
- Instruments-info rounding — no `instruments-info` fetch; `_round_to_step` is an approximation.
- Persistence of RiskGuard state across restarts — counters live in memory only.
- Funding-rate blackout (30 s before / 15 s after settlement) — not implemented.
- Periodic position existence check (`get_positions`) — tracker assumes the position is alive until exit.
- `orderLinkId` on outgoing orders — not set.

---

## 🏗 Architecture

Three isolated async layers communicating through shared state and callbacks:

```
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│        ENGINE        │── │       TRADING        │── │          UI          │
│  ticks, momentum,    │   │  orders, positions,  │   │  PyQt6, sliders,     │
│  direction, RiskGuard│   │  trailing, PnL       │   │  popup, Kill Switch  │
└──────────────────────┘   └──────────────────────┘   └──────────────────────┘
```

### Project tree

```
ImpulseCatcherV5/
├── main.py                     # Orchestrator
├── config.example.json         # Config template (copy to config.json)
├── requirements.txt
├── run_terminal.bat
├── LICENSE
├── README.md
│
├── engine/
│   ├── time_sync.py            # NTP sync + recvWindow (partially wired)
│   ├── ws_connector.py         # WebSocket publicTrade (liquidation — planned)
│   ├── hft_processor.py        # Momentum detection, direction, peak tracking
│   ├── risk_guard.py           # Daily loss limit, consecutive losses
│   └── market_analyzer.py      # Daily/weekly context (placeholder)
│
├── trading/
│   ├── client_init.py          # pybit V5 HTTP session
│   ├── order_manager.py        # Twin order + server-side SL, real avgPrice
│   └── position_tracker.py     # Trailing exit, PnL reporting to RiskGuard
│
└── ui/
    ├── interface.py            # PyQt6 sliders + Kill Switch
    └── popup_trigger.py        # Alert (print + beep; modal popup planned)
```

### How the orchestra plays

1. `main.py` calls `time_sync.sync_with_bybit()`.
2. Launches `interface.py` on the main thread via `qasync`.
3. Background: `ws_connector` subscribes to `publicTrade` for all monitored symbols.
4. `hft_processor.process_new_tick()` detects momentum and returns `TRIGGERED` / `ENTRY` events with a `direction`.
5. On `ENTRY`, `main.py` checks `RiskGuard.can_trade()`, then calls `order_manager.execute_twin_entry(coin, price, direction)`.
6. On success, `position_tracker.track_position_loop()` manages the position: trailing activation → rollback exit → PnL report to RiskGuard.

---

##  Config

Copy `config.example.json` to `config.json` and fill in:

- `api.api_key`, `api.api_secret` — **use testnet first** (`api.testnet: true`).
- `risk_management.deposit_usdt` — your actual starting balance in USDT. **Required for daily loss limits to work.**
- `assets.monitored_coins` — symbols to scan.
- `sliders.*` — tuning parameters, editable from the UI at runtime.

**Never commit `config.json`.** It is listed in `.gitignore`.

---

##  Quick start

### Requirements

- Python **3.11+**
- Windows 10/11 / macOS / Linux
- Bybit **UTA** (Unified Trading Account)
- API keys with **withdrawal disabled**

### Install

```bash
git clone https://github.com/dwfirst/bybit-hft-impulse-bot.git
cd bybit-hft-impulse-bot
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### Configure

```bash
cp config.example.json config.json
```

Edit `config.json` — fill in API keys (testnet), `deposit_usdt`, and symbol list.

### Run

```bash
python main.py
```

On startup the bot:

1. Syncs time with Bybit.
2. Opens a WebSocket subscription to `publicTrade`.
3. Displays the PyQt6 terminal with sliders.

**Hotkeys:**
- `F12` — **KILL SWITCH** (works when the terminal window has focus).

---

##  Roadmap

- [x] Async engine (asyncio + pybit V5 + qasync + PyQt6)
- [x] Tick-based momentum detection with UP/DOWN direction
- [x] Direction-aware twin orders (Long/Short)
- [x] RiskGuard with PnL reporting
- [x] Real `avgPrice` from exchange after entry
- [x] Kill Switch (F12)
- [ ] `liquidation` stream subscription
- [ ] Anti-FOMO filter (1m candle counter)
- [ ] ATR-based stop and trailing exit
- [ ] True Chase Limit re-posting
- [ ] API throttle + rate-limit backoff
- [ ] Instruments-info rounding for Price/Qty
- [ ] Space / Escape hotkeys + modal popup
- [ ] Dynamic `recvWindow` wired into `client_init`
- [ ] RiskGuard state persistence (JSON/SQLite)
- [ ] Funding-rate blackout window
- [ ] 48h Bybit Testnet run

---

## 🛠 Tech stack

- **Python 3.11+** — core
- **asyncio** — async engine
- **pybit V5** — official Bybit SDK
- **PyQt6** — GUI
- **qasync** — bridge between asyncio and the Qt event loop
- **websockets** — HFT streams
- **aiohttp** — REST calls in `time_sync`

---

## ⚠️ Known limitations

These are documented on purpose. A serious trading tool is defined by what it honestly admits it does not yet do.

1. **No live PnL is published.** All thresholds are design targets.
2. **`liquidation` stream is not connected.** Panic detection is currently volume-spike based on `publicTrade` only.
3. **RiskGuard is not persisted.** Restarting the bot resets daily counters.
4. **ATR is not computed.** The hard stop is a fixed 1.5%.
5. **Chase Limit is partial.** It is a static Limit add, not a re-posting chase.
6. **Kill Switch is client-side only.** No server-side dead-man's switch.
7. **`average_2h_volume` in `hft_processor` is hardcoded** — the volume-climax filter is not fully active.

---

## 🤝 Contributing

Pull requests are welcome. For bugs, open an issue with logs from `bot_debug.log` (**redact secrets first**).

Before submitting a PR: `ruff check . && black .`

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

## 🔗 References

- [Bybit API V5 Docs](https://bybit-exchange.github.io/docs/v5/intro)
- [pybit SDK](https://github.com/bybit-exchange/pybit)
- [PyQt6 Docs](https://www.riverbankcomputing.com/static/Docs/PyQt6/)

---

> ⚡ **Remember:** the market is fractal; risk is not. Trade only what you can afford to lose.
