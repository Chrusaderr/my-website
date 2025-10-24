import os, time, threading, requests, json
from collections import deque
from datetime import datetime

# Simple in-memory state + file log
STATE = {
    "mode": os.getenv("DEFAULT_MODE", "scan").lower(),  # scan | run | off
    "symbol": os.getenv("DEFAULT_SYMBOL", "DOGEUSDT").upper(),
    "trade_fraction": float(os.getenv("DEFAULT_TRADE_FRACTION", "0.25")),  # 0-1
    "cooldown_sec": int(os.getenv("COOLDOWN_SEC", "8")),
    "last_trade_ts": 0.0,
    "min_hold_sec": int(os.getenv("MIN_HOLD_SEC", "10")),
    "status": "idle",
    "latency_ms": 0.0
}

WALLET = {
    "balance": float(os.getenv("START_BALANCE", "10000")),
    "qty": 0.0,
    "avg_price": 0.0,
    "equity": float(os.getenv("START_BALANCE", "10000"))
}

TICKS = deque(maxlen=600)   # store last ~10 mins @1s
CLOSES = deque(maxlen=200)

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "app.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def _binance_price(symbol):
    # data-api (no auth). Use ticker/price for last price.
    url = f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}"
    r = requests.get(url, timeout=2)
    data = r.json()
    return float(data["price"])

def _coingecko_price(symbol):
    # Map common USDT pairs to CoinGecko ids
    m = {
        "BTCUSDT": "bitcoin",
        "ETHUSDT": "ethereum",
        "DOGEUSDT": "dogecoin",
        "SOLUSDT": "solana",
        "ADAUSDT": "cardano"
    }
    coin = m.get(symbol.upper())
    if not coin:
        raise ValueError("unsupported symbol for CoinGecko fallback")
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd"
    r = requests.get(url, timeout=3)
    data = r.json()
    return float(data[coin]["usd"])

def fetch_price(symbol):
    t0 = time.time()
    try:
        px = _binance_price(symbol)
    except Exception:
        try:
            px = _coingecko_price(symbol)
        except Exception as e:
            log(f"❌ Fetch error: {e}")
            return None
    STATE["latency_ms"] = round((time.time() - t0) * 1000.0, 1)
    return px

# --- indicators ---
def rsi(values, period=14):
    if len(values) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        change = values[i] - values[i-1]
        if change > 0:
            gains += change
        else:
            losses -= change
    if gains + losses == 0:
        return 50.0
    rs = (gains / period) / (losses / period if losses > 0 else 1e-9)
    return 100.0 - (100.0 / (1.0 + rs))

def ema(values, span):
    if len(values) < span:
        return None
    k = 2 / (span + 1)
    ema_val = values[0]
    for v in values[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val

def macd(values, fast=12, slow=26, signal=9):
    if len(values) < slow + signal:
        return None, None, None
    fast_ema = ema(values[-slow:], fast) if fast <= slow else ema(values, fast)
    slow_ema = ema(values, slow)
    if fast_ema is None or slow_ema is None:
        return None, None, None
    macd_line = fast_ema - slow_ema
    # build signal by last (signal) samples of macd approx (simple)
    tmp = list(values)[- (slow + signal) :]
    macd_series = []
    efast = None
    eslow = None
    kf = 2 / (fast + 1)
    ks = 2 / (slow + 1)
    for v in tmp:
        efast = v if efast is None else v * kf + efast * (1 - kf)
        eslow = v if eslow is None else v * ks + eslow * (1 - ks)
        macd_series.append(efast - eslow)
    # signal EMA
    ksig = 2 / (signal + 1)
    sig = None
    for m in macd_series:
        sig = m if sig is None else m * ksig + sig * (1 - ksig)
    hist = macd_line - (sig if sig is not None else 0.0)
    return macd_line, sig, hist

# --- trading ---
FEE = 0.001  # 0.1%

def buy(price):
    # use fraction of balance
    alloc = max(0.05, min(STATE["trade_fraction"], 0.5))  # clamp 5%-50%
    usd = WALLET["balance"] * alloc
    if usd <= 1e-6:
        log("⚠️ Not enough balance to buy")
        return False
    qty = (usd * (1 - FEE)) / price
    WALLET["balance"] -= usd
    new_qty = WALLET["qty"] + qty
    WALLET["avg_price"] = (WALLET["avg_price"] * WALLET["qty"] + price * qty) / new_qty if new_qty > 0 else 0.0
    WALLET["qty"] = new_qty
    STATE["last_trade_ts"] = time.time()
    log(f"🟢 BUY {qty:.4f} @ {price:.5f} | alloc={alloc*100:.1f}%")
    return True

def sell(price):
    qty = WALLET["qty"]
    if qty <= 0:
        log("⚠️ Nothing to sell")
        return False
    proceeds = qty * price * (1 - FEE)
    pnl = (price - WALLET["avg_price"]) * qty
    WALLET["balance"] += proceeds
    WALLET["qty"] = 0.0
    WALLET["avg_price"] = 0.0
    STATE["last_trade_ts"] = time.time()
    log(f"🔴 SELL {qty:.4f} @ {price:.5f} | PnL={pnl:.2f}")
    return True

def step_decision(price):
    # compute indicators
    CLOSES.append(price)
    r = rsi(list(CLOSES))
    m_line, m_sig, m_hist = macd(list(CLOSES))
    # default action
    act = "HOLD"
    now = time.time()

    if r is not None and m_line is not None and m_sig is not None:
        # simple rules + cooldown + hold time
        cooldown = (now - STATE["last_trade_ts"]) < STATE["cooldown_sec"]
        holding = WALLET["qty"] > 0 and (now - STATE["last_trade_ts"]) < STATE["min_hold_sec"]

        if STATE["mode"] == "run":
            if (r < 35 and m_line > m_sig and not cooldown):
                if buy(price):
                    act = "BUY"
            elif (r > 65 and m_line < m_sig and not holding and not cooldown):
                if sell(price):
                    act = "SELL"

    return {
        "rsi": r,
        "macd": m_line,
        "macd_signal": m_sig,
        "macd_hist": m_hist,
        "action": act
    }

def update_equity(price):
    WALLET["equity"] = WALLET["balance"] + WALLET["qty"] * price

def trader_loop(stop_event):
    log(f"🤖 Trader loop started | symbol={STATE['symbol']} | mode={STATE['mode']}")
    while not stop_event.is_set():
        px = fetch_price(STATE["symbol"])
        if px is None:
            time.sleep(1)
            continue
        # candle proxy (1s)
        TICKS.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "open": px, "high": px, "low": px, "close": px, "volume": 0.0
        })
        # decision
        info = step_decision(px)
        update_equity(px)
        log(f"{STATE['symbol']} {px:.5f} | {info['action']} | RSI={info['rsi'] and round(info['rsi'],2)} MACD={info['macd'] and round(info['macd'],4)}")
        time.sleep(1)

# helpers to read state safely
def latest_tick():
    return TICKS[-1] if TICKS else None
