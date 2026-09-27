# Bybit HFT Impulse Bot (v5.0)

A high-frequency trading (HFT) automation robot designed for the Bybit exchange. The system features a custom modular architecture with a PyQt6-based adaptive graphical user interface utilizing an asynchronous event loop via `qasync`.

## Core Features
* **HFT Momentum Processor:** Real-time WebSocket tick stream analysis with customized panic window filters.
* **Twin Order Execution:** Automated twin-short entries utilizing parallel Market + Limit order placement via `asyncio.to_thread`.
* **Server-side Risk Management:** Dynamic server-side Stop Loss placement and local trailing stop loops based on fixed drawdown limits.
* **Cyber-Antique UI:** High-performance dashboard with dynamic param sliders, scrolling telemetry log stream, and a global Emergency Kill Switch.
* **Adaptive Resolution:** Fully responsive layout optimized for compact and low-resolution monitors (e.g., 14-inch laptops).

## Architecture Layout
* `main.py` — Core system orchestrator connecting network layers and UI events.
* `engine/` — Market pulse, time synchronization, and algorithmic tick processing modules.
* `trading/` — Exchange API client initialization, order management, and position tracking.
* `ui/` — Desktop graphical terminal and pop-up alert controllers.
* `run_terminal.bat` — Universal 1-click execution launcher for automatic virtual environment deployment.

## How to Install & Launch

1. Make sure **Python 3.10 or higher** is installed on your computer.
2. Clone or download this clean repository to your local machine.
3. Locate `config.example.json` in the root folder, rename it to `config.json`, and insert your valid Bybit API keys.
4. Double-click `run_terminal.bat`. 

*Note: The launcher will automatically build the `hft_env` virtual environment, upgrade pip, install all mandatory libraries (`PyQt6`, `pybit`, `websockets`, `qasync`, `aiohttp`), and securely start the terminal.*
