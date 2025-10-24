import os, time, json, threading, requests
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(__file__)
FRONT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)

STATE_PATH = os.path.join(BASE_DIR, "ai_status.json")
DEFAULT_STATUS = {"active": True, "training": False, "mode": "scan", "symbol": "BTCUSDT"}

def read_status():
    if not os.path.exists(STATE_PATH):
        write_status(DEFAULT_STATUS.copy())
    with open(STATE_PATH, "r") as f:
        return json.load(f)

def write_status(st):
    with open(STATE_PATH, "w") as f:
        json.dump(st, f, indent=2)

def fetch_price_binance(symbol: str):
    try:
        url = f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}"
        r = requests.get(url, timeout=2)
        j = r.json()
        if isinstance(j, dict) and "price" in j:
            return float(j["price"])
    except Exception:
        pass
    return None

def fetch_price_coingecko(symbol: str):
    sym_map = {"BTCUSDT":"bitcoin","ETHUSDT":"ethereum","DOGEUSDT":"dogecoin","SOLUSDT":"solana","ADAUSDT":"cardano"}
    coin_id = sym_map.get(symbol, "bitcoin")
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        r = requests.get(url, timeout=2)
        j = r.json()
        price = j.get(coin_id, {}).get("usd")
        return float(price) if price is not None else None
    except Exception:
        return None

LATEST = {"timestamp": None, "open":0.0,"high":0.0,"low":0.0,"close":0.0,"volume":0.0,"rsi":None,"macd":None,"prediction":"HOLD"}
price_history = []

def compute_indicators(prices, period=14):
    rsi = None; macd = None
    if len(prices) >= 2:
        n = min(period, len(prices)-1)
        gains = [max(0.0, prices[-i] - prices[-i-1]) for i in range(1, n+1)]
        losses = [max(0.0, prices[-i-1] - prices[-i]) for i in range(1, n+1)]
        avg_gain = sum(gains)/n if n else 0.0
        avg_loss = sum(losses)/n if n else 0.0
        if avg_loss == 0: rsi = 100.0
        else:
            rs = avg_gain/avg_loss
            rsi = 100 - (100/(1+rs))
        def ema(vals, span):
            k = 2/(span+1); e = vals[0]
            for v in vals[1:]: e = v*k + e*(1-k)
            return e
        if len(prices) >= 26:
            macd = ema(prices[-26:],12) - ema(prices[-26:],26)
    return rsi, macd

def ai_loop():
    global LATEST, price_history
    print("🤖 AI loop ready (SCAN by default).")
    while True:
        st = read_status()
        symbol = st.get("symbol","BTCUSDT")
        mode = st.get("mode","scan")
        if mode in ("scan","run"):
            price = fetch_price_binance(symbol)
            if price is None:
                price = fetch_price_coingecko(symbol)
            if price is not None:
                price_history.append(price)
                price_history = price_history[-300:]
                rsi, macd = compute_indicators(price_history)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                LATEST = {"timestamp":now,"open":price,"high":price,"low":price,"close":price,"volume":0.0,
                          "rsi":None if rsi is None else float(rsi),
                          "macd":None if macd is None else float(macd),
                          "prediction":"HOLD" if mode=="run" else "SCAN"}
                print(f"[{now}] {symbol} {price:.2f} ({mode})")
        time.sleep(1)

@app.route("/")
def root(): return send_from_directory(FRONT_DIR, "index.html")

@app.route("/latest")
def latest():
    if not LATEST["timestamp"]:
        return jsonify({"error":"No data yet."})
    return jsonify(LATEST)

@app.route("/mode/<name>", methods=["POST"])
def set_mode(name):
    name = name.lower()
    if name not in ("scan","run","off"):
        return jsonify({"error":"Invalid mode"}), 400
    st = read_status(); st["mode"] = name; write_status(st); return jsonify(st)

@app.route("/symbol", methods=["POST"])
def set_symbol():
    data = request.get_json(force=True) or {}
    symbol = data.get("symbol","BTCUSDT").upper()
    st = read_status(); st["symbol"]=symbol; write_status(st); return jsonify(st)

def start_loop():
    t = threading.Thread(target=ai_loop, daemon=True); t.start()

if __name__ == "__main__":
    read_status()
    start_loop()
    print("🚀 Flask AI Trader running at http://127.0.0.1:5000")
    app.run(port=5000, debug=False)
