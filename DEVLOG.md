# DEVLOG — ImpulseCatcher V5

История ключевых правок, аудитов и решений. Для агента/Cursor/AI-ассистента при возврате в проект.

**Последнее обновление:** 2026-09-29
**Репозиторий:** https://github.com/dwfirst/bybit-hft-impulse-bot
**Рабочая копия:** `D:\done_it_project\bybit-hft-impulse-bot` (open in Cursor)
**Три копии проекта:**
1. Рабочая — в Cursor, папка выше. **Работаем только здесь.**
2. Старая версия с токеном и русскими вставками — **не трогаем**, ключи будут отозваны.
3. GitHub — результат, куда пушим.

---

## Стек

- Python 3.11+
- asyncio + `pybit` V5 + `qasync` + PyQt6
- WebSocket `publicTrade` (Bybit linear)
- Конфиг: `config.json` (локально) / `config.example.json` (в репо)

---

## Сделано в этой итерации

### main.py
- Импорт `RiskGuard` из `engine.risk_guard`.
- Экземпляр `self.risk_guard` создан в `__init__`, логгер прокинут через `set_log_callback`.
- Перед каждым входом: проверка `self.risk_guard.can_trade()`. Если locked out — сброс монеты в SCANNING, лог `[RISK]`, сигнал пропускается.
- `direction` пробрасывается из тика в `execute_twin_entry(coin, price, direction)`.
- Лог `[ТИК]` → `[TICK]`.

### engine/hft_processor.py
- Убран `abs()` в `_detect_momentum` — теперь рост и падение различаются.
- Добавлен `direction` ("UP"/"DOWN") в события `TRIGGERED` и `ENTRY`.
- Пик обновляется корректно: для UP — максимум, для DOWN — минимум.
- В `__init__` добавлен `self.trigger_directions`.
- `reset_coin` сбрасывает и `trigger_directions`.
- Порог отката для DOWN зеркалится (`peak * (1 + rebound_pct)`).

### trading/order_manager.py
- `execute_twin_short_entry` → `execute_twin_entry(coin, trigger_price, direction="UP")`.
- `side` выбирается по direction: `Sell` для UP (шорт), `Buy` для DOWN (лонг).
- `hard_stop` считается зеркально: `ins_price * 1.015` для шорта, `ins_price * 0.985` для лонга.
- После Market — пауза 0.25 сек и чтение реального `avgPrice` из `get_positions`. Он идёт в `order_report["average_entry_price"]`.
- В отчёт добавлены `direction` и `exit_side`.
- `close_market_position(symbol, direction)` читает `side` позиции с биржи и сам выбирает сторону закрытия.
- `coin_settings.leverage` приведён к 20× по всем монетам (было 20/35/50/80).

### trading/position_tracker.py
- Сигнатура: `__init__(config, order_manager, risk_guard=None, log_fn=print)`.
- Добавлен `_report_pnl_to_risk_guard(pnl_pct, entry_price, exit_price)`. Вызывается после успешного закрытия. Считает `pnl_usdt = notional * (pnl_pct / 100)`, где `notional = margin * leverage`. Депозит — из `config["risk_management"]["deposit_usdt"]`, дефолт 100.
- Трейлинг и порог отката зеркалятся для Long/Short.
- `close_market_position` вызывается с `direction` в трёх местах: основной цикл, except-блок, `emergency_close_all`.

### .gitignore
Добавлено: `.env`, `secrets.json`. Уже было: `hft_env/`, `.venv/`, `venv/`, `config.json`, `*.log`, `**/__pycache__/`, `*.pyc`.

### LICENSE
MIT, `Copyright (c) 2026 dwfirst`.

### README.md
- Честная секция «What's implemented» / «What's NOT implemented yet».
- Дисклеймер, статус-плашка «prototype / not production-ready».
- Архитектура, quick start, roadmap, ссылка на LICENSE.

---

## Git — что сделано

- `git init` в рабочей папке.
- `git remote add origin https://github.com/dwfirst/bybit-hft-impulse-bot.git`.
- Ветка: `main`.
- Два коммита:
  - `a01ce19` — Rewrite: risk guard, direction-aware entries, real avgPrice, PnL reporting (**push --force**, потому что на хабе лежала старая версия и возможные ключи в истории).
  - `3f8102d` — Add LICENSE and README (**обычный push**).

---

## Что НЕ реализовано (по аудиту от 2026-09-29)

1. `liquidation` stream — `ws_connector.py` слушает только `publicTrade`.
2. Anti-FOMO (`slider_5_trend_exhaustion_limit_1m_candles`) — ключ в конфиге есть, в коде не проверяется.
3. ATR — не считается. `hard_stop` в `order_manager` фиксированный 1.5%. `atr_multiplier` из конфига не используется.
4. `api_throttle_ms` (rate limiting) — не подключён.
5. Chase Limit как переставление лимитки — не реализован, только Market + Limit.
6. Space/Escape hotkeys — не обрабатываются. `F12` работает только при фокусе окна.
7. `popup_trigger.py` — это `print` + beep, не модальное окно.
8. `average_2h_volume` в `hft_processor.py` — захардкожен `1000.0`, реальный volume climax не считается.
9. `hft_processor.sync_states_with_exchange` — не вызывается.
10. `time_sync.get_recv_window` — метод есть, не подключён к `client_init`.
11. Динамический `recvWindow`, periodic re-sync — нет.
12. Персистентность `RiskGuard` (дневной PnL, серия стопов) — нет.
13. `instruments-info` (tick/lot precision) — не загружается, `_round_to_step` — грубая замена.
14. `orderLinkId` на ордерах — не ставится.
15. Периодическая проверка, что позиция ещё существует на бирже (`get_positions`) — нет.
16. Funding-rate blackout (за 30 сек до / 15 сек после) — не реализован.

---

## Что сделать в первую очередь (следующая итерация)

1. Вписать реальный `deposit_usdt` в `config.json` (локально) и `config.example.json` (публично).
2. Проверить, что нигде не остался `execute_twin_short_entry` (Ctrl+Shift+F по проекту).
3. Отозвать старые API-ключи на Bybit, создать новые с `Withdrawal — Disabled`.
4. Зафиксировать версии в `requirements.txt` (`pybit`, `PyQt6`, `qasync`, `websockets`, `aiohttp`).
5. Реализовать Anti-FOMO (счётчик 1m-свечей) — самый дешёвый пункт из списка.
6. Реализовать ATR (1m, 2h) и заменить фиксированный `hard_stop` на `atr * multiplier`.
7. Подключить `api_throttle_ms` (throttle на REST-запросы).
8. Space/Escape через `QShortcut` с `ApplicationShortcut`.
9. Подписка на `liquidation` (или fallback на volume-climax по `publicTrade`).
10. Персистентность `RiskGuard` (JSON/SQLite) — иначе Ctrl+C сбрасывает дневные лимиты.

---

## Правила работы

- Правки делаем **только** в рабочей копии (`D:\done_it_project\bybit-hft-impulse-bot`).
- Пуш в `origin main`. `--force` — только если ключи попали в историю.
- Секреты (`config.json`, `.env`, ключи) — **никогда** в git.
- После правки — `Ctrl+K S` (Save All) в Cursor перед `python main.py`.
- Логи на английском, сообщения пользователю могут быть русскими, но теги — только `[UPPERCASE]` на латинице.
## 2026-10-07 — Hardening pass (Steps 1-2)

### Step 1: RiskGuard persistence
- Atomic JSON state file (`risk_guard_state.json`) with `os.replace`
- Auto-skip restore if state file is from a previous day
- `.gitignore` cleanup (state file no longer tracked)
- Tested: save/restore, day-rollover safety

### Step 2: API reliability
- `RateLimiter` class in `client_init.py` — global REST throttle (default 120ms)
- `throttled_call()` helper on `BybitClientInitializer`
- Dynamic `recvWindow` resolved from `TimeSynchronizer.get_recv_window()`
- `main.py` now passes `time_sync` into the client initializer
- `orderLinkId` added to every `place_order` (Market / Limit / Close)
- `orderLinkId` returned in `order_report` for future tracker reconciliation
- Tested: import smoke, recvWindow resolution, rate-limiter timing