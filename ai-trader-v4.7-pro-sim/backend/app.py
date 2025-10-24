import os, time, json, threading, requests
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, Response

BASE_DIR = os.path.dirname(__file__)
FRONT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
from live_log import log_line, recent_lines
from trader_core import TraderCore

app = Flask(__name__)

STATE_PATH = os.path.join(BASE_DIR, "ai_status.json")
DEFAULT_STATUS = {"active": True, "training": False, "mode": "scan", "symbol": "DOGEUSDT"}
core = TraderCore(starting_balance=10000.0)

def read_status():
    if not os.path.exists(STATE_PATH): write_status(DEFAULT_STATUS.copy())
    with open(STATE_PATH,"r") as f: return json.load(f)

def write_status(st):
    with open(STATE_PATH,"w") as f: json.dump(st,f,indent=2)

def fetch_price_binance(symbol):
    try:
        r = requests.get(f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}", timeout=2)
        j = r.json()
        if isinstance(j, dict) and "price" in j: return float(j["price"])
    except: pass
    return None

def fetch_price_coingecko(symbol):
    sym_map={"BTCUSDT":"bitcoin","ETHUSDT":"ethereum","DOGEUSDT":"dogecoin","SOLUSDT":"solana","ADAUSDT":"cardano"}
    coin_id=sym_map.get(symbol,"dogecoin")
    try:
        r=requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd", timeout=2)
        j=r.json(); price=j.get(coin_id,{}).get("usd")
        return float(price) if price is not None else None
    except: return None

LATEST={"timestamp":None,"open":0.0,"high":0.0,"low":0.0,"close":0.0,"volume":0.0,"rsi":None,"macd":None,"prediction":"SCAN"}

def loop():
    log_line(BASE_DIR,"SYSTEM","SCAN",None,"AI loop ready (SCAN by default).")
    while True:
        st=read_status()
        symbol=st.get("symbol","DOGEUSDT"); mode=st.get("mode","scan")
        if mode in ("scan","run"):
            price = fetch_price_binance(symbol) or fetch_price_coingecko(symbol)
            if price is not None:
                core.add_price(price); rsi,macd = core.compute_rsi_macd()
                action = core.analyze_signals(price,rsi,macd)
                trade_info=None; shown_action="SCAN"
                if mode=="run":
                    shown_action = action if action in ("BUY","SELL") else "HOLD"
                    exec_result, detail = core.execute_trade(action, price)
                    trade_info=(exec_result, detail)
                now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                LATEST.update({"timestamp":now,"open":price,"high":price,"low":price,"close":price,
                    "volume":0.0,"rsi": None if rsi is None else float(rsi),
                    "macd": None if macd is None else float(macd),"prediction":shown_action})
                extra=""
                if trade_info and trade_info[0]=="BUY":
                    extra=f"BUY qty={trade_info[1]['qty']:.2f} using {trade_info[1]['usd']:.2f} USD | alloc={core.trade_fraction*100:.0f}%"
                elif trade_info and trade_info[0]=="SELL":
                    extra=f"SELL qty={trade_info[1]['qty']:.2f} profit={trade_info[1]['profit']:.2f} USD"
                log_line(BASE_DIR, symbol, shown_action if mode=="run" else "SCAN", price, extra)
        time.sleep(1)

@app.route("/")
def root(): return send_from_directory(FRONT_DIR,"index.html")

@app.route("/static/<path:name>")
def static_files(name): return send_from_directory(os.path.join(FRONT_DIR,"static"), name)

@app.route("/latest")
def latest():
    if not LATEST["timestamp"]: return jsonify({"error":"No data yet."})
    return jsonify(LATEST)

@app.route("/mode/<name>", methods=["POST"])
def set_mode(name):
    name=name.lower()
    if name not in ("scan","run","off"): return jsonify({"error":"Invalid mode"}),400
    st=read_status(); st["mode"]=name; write_status(st)
    log_line(BASE_DIR,"SYSTEM",name.upper(),None,"mode changed")
    return jsonify(st)

@app.route("/symbol", methods=["POST"])
def set_symbol():
    data=request.get_json(force=True) or {}
    symbol=data.get("symbol","DOGEUSDT").upper()
    st=read_status(); st["symbol"]=symbol; write_status(st)
    log_line(BASE_DIR,"SYSTEM","SCAN",None,f"symbol set to {symbol}")
    return jsonify(st)

@app.route("/set_trade_fraction", methods=["POST"])
def set_trade_fraction():
    data=request.get_json(force=True) or {}
    frac=float(data.get("fraction",0.25))
    newf=core.set_trade_fraction(frac)
    log_line(BASE_DIR,"SYSTEM","SCAN",None,f"trade allocation set to {newf*100:.0f}%")
    return jsonify({"fraction":newf})

@app.route("/wallet")
def wallet():
    price = LATEST.get("close") or 0.0
    return jsonify({"balance":core.balance,"position_size":core.position_size,"entry_price":core.entry_price or 0.0,"equity":core.equity(price)})

@app.route("/logs")
def logs_page():
    html = '''
    <!doctype html><html><head><meta charset="utf-8"/><title>AI Trader Logs</title>
    <link rel="stylesheet" href="/static/style.css"></head><body>
    <h1>Live Logs</h1><div class="card"><small class="hint">Auto-refreshes every 2s. Scroll sticks to bottom.</small>
    <pre id="logbox" class="logbox"></pre></div>
    <script>
    async function refresh(){ try{ const r=await fetch('/logs/feed'); const j=await r.json();
      const el=document.getElementById('logbox'); el.textContent=j.lines.join('\n'); el.scrollTop=el.scrollHeight; }catch(e){console.error(e);}}
    setInterval(refresh,2000); refresh();
    </script></body></html>'''
    return Response(html, mimetype="text/html")

@app.route("/logs/feed")
def logs_feed():
    return jsonify({"lines": recent_lines(80)})

def start_loop():
    t=threading.Thread(target=loop,daemon=True); t.start()

if __name__=="__main__":
    if not os.path.exists(STATE_PATH): write_status(DEFAULT_STATUS.copy())
    start_loop()
    print("🚀 Flask AI Trader running at http://127.0.0.1:5000", flush=True)
    app.run(port=5000, debug=False)
