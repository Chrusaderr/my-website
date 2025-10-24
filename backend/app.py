import os, time, json, threading, requests
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, Response

BASE_DIR = os.path.dirname(__file__)
FRONT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

from live_log import log_line, recent_lines
from trader_core import TraderCore

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

LATEST = {"timestamp": None, "open":0.0,"high":0.0,"low":0.0,"close":0.0,"volume":0.0,"rsi":None,"macd":None,"prediction":"SCAN"}
core = TraderCore()

def loop():
    log_line(BASE_DIR, "SYSTEM", "SCAN", None, "AI loop ready (SCAN by default).")
    while True:
        st = read_status()
        symbol = st.get("symbol","BTCUSDT")
        mode = st.get("mode","scan")

        if mode in ("scan","run"):
            price = fetch_price_binance(symbol)
            if price is None:
                price = fetch_price_coingecko(symbol)

            if price is not None:
                action, rsi, macd = core.decide(price)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                LATEST.update({
                    "timestamp": now,
                    "open": price, "high": price, "low": price, "close": price,
                    "volume": 0.0,
                    "rsi": None if rsi is None else float(rsi),
                    "macd": None if macd is None else float(macd),
                    "prediction": action if mode == "run" else "SCAN"
                })
                log_line(BASE_DIR, symbol, "SCAN" if mode!="run" else action, price)
        time.sleep(1)

@app.route("/")
def root():
    return send_from_directory(FRONT_DIR, "index.html")

@app.route("/static/<path:name>")
def static_files(name):
    return send_from_directory(os.path.join(FRONT_DIR, "static"), name)

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
    st = read_status(); st["mode"]=name; write_status(st)
    log_line(BASE_DIR, "SYSTEM", name.upper(), None, "mode changed")
    return jsonify(st)

@app.route("/symbol", methods=["POST"])
def set_symbol():
    data = request.get_json(force=True) or {}
    symbol = data.get("symbol","BTCUSDT").upper()
    st = read_status(); st["symbol"]=symbol; write_status(st)
    log_line(BASE_DIR, "SYSTEM", "SCAN", None, f"symbol set to {symbol}")
    return jsonify(st)

@app.route("/logs")
def logs_page():
    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>AI Trader Logs</title>
      <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
      <h1>Live Logs</h1>
      <div class="card">
        <small class="hint">Auto-refreshes every 3s. Scroll sticks to bottom automatically.</small>
        <pre id="logbox" class="logbox"></pre>
      </div>
      <script>
        async function refresh() {{
          try {{
            const r = await fetch('/logs/feed');
            const j = await r.json();
            const el = document.getElementById('logbox');
            el.textContent = j.lines.join('\n');
            el.scrollTop = el.scrollHeight;
          }} catch(e) {{
            console.error(e);
          }}
        }}
        setInterval(refresh, 3000);
        refresh();
      </script>
    </body>
    </html>
    """
    return Response(html, mimetype="text/html")

@app.route("/logs/feed")
def logs_feed():
    lines = recent_lines(50)
    return jsonify({"lines": lines})

def start_loop():
    t = threading.Thread(target=loop, daemon=True)
    t.start()

if __name__ == "__main__":
    if not os.path.exists(STATE_PATH):
        write_status(DEFAULT_STATUS.copy())
    start_loop()
    print("🚀 Flask AI Trader running at http://127.0.0.1:5000", flush=True)
    app.run(port=5000, debug=False)
