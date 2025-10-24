from flask import Flask, jsonify, send_from_directory, request
import os, threading, time, json
from trader_core import STATE, WALLET, TICKS, log, trader_loop, latest_tick

app = Flask(__name__, static_folder="static", static_url_path="/")

stop_event = threading.Event()
bg_thread = threading.Thread(target=trader_loop, args=(stop_event,), daemon=True)
bg_thread.start()

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/latest")
def latest():
    tick = latest_tick()
    if not tick:
        return jsonify({"error": "no data yet"})
    out = {**tick}
    # attach derived state
    out.update({
        "prediction": STATE.get("status", "HOLD"),
        "rsi": None,
        "macd": None,
        "latency_ms": STATE.get("latency_ms", 0.0),
        "mode": STATE["mode"]
    })
    return jsonify(out)

@app.route("/wallet")
def wallet():
    return jsonify({
        "balance": WALLET["balance"],
        "qty": WALLET["qty"],
        "avg_price": WALLET["avg_price"],
        "equity": WALLET["equity"],
        "symbol": STATE["symbol"],
        "trade_fraction": STATE["trade_fraction"]
    })

@app.route("/mode/<name>", methods=["POST"])
def set_mode(name):
    name = name.lower()
    if name not in ["run","scan","off"]:
        return jsonify({"error":"bad mode"}), 400
    STATE["mode"] = name
    log(f"⚙️ MODE → {name.upper()}")
    return jsonify({"ok": True, "mode": name})

@app.route("/symbol", methods=["POST"])
def set_symbol():
    data = request.get_json(silent=True) or {}
    sym = (data.get("symbol") or "").upper()
    if not sym or not sym.endswith("USDT"):
        return jsonify({"error": "symbol must end with USDT"}), 400
    STATE["symbol"] = sym
    log(f"🔁 SYMBOL → {sym}")
    return jsonify({"ok": True, "symbol": sym})

@app.route("/set_trade_fraction", methods=["POST"])
def set_trade_fraction():
    data = request.get_json(silent=True) or {}
    try:
        f = float(data.get("fraction"))
    except Exception:
        return jsonify({"error": "fraction must be float"}), 400
    f = max(0.05, min(f, 0.5))
    STATE["trade_fraction"] = f
    log(f"🎚️ TRADE ALLOCATION → {f*100:.1f}%")
    return jsonify({"ok": True, "fraction": f})

@app.route("/logs")
def logs():
    # Simple log viewer
    return send_from_directory(app.static_folder, "logs.html")

@app.route("/log_stream")
def log_stream():
    log_path = os.path.join(os.path.dirname(__file__), "logs", "app.log")
    if not os.path.exists(log_path):
        return jsonify({"lines": []})
    # Return last 200 lines
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-200:]
    return jsonify({"lines": [ln.rstrip() for ln in lines]})

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    print(f"🚀 Flask AI Trader running at http://127.0.0.1:{port}")
    app.run(port=port, host="127.0.0.1")
