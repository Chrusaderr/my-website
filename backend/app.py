from flask import Flask, jsonify, request, send_from_directory
import os, time, json, csv, requests, threading, joblib, warnings
import pandas as pd
from datetime import datetime
from sklearn.preprocessing import StandardScaler
import ta
from tracker import update_on_signal

warnings.filterwarnings("ignore")

# --- Configuration ---
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "data", "market_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "model.pkl")
STATUS_PATH = os.path.join(BASE_DIR, "ai_status.json")

SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "1"))
RETRAIN_INTERVAL = int(os.getenv("RETRAIN_INTERVAL", "200"))

os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

try:
    from xgboost import XGBClassifier
    USE_XGB = True
except Exception:
    from sklearn.ensemble import RandomForestClassifier
    USE_XGB = False

FEATURES = [
    "open","high","low","close","volume","delta","ma5","ma10","vol_delta",
    "rsi","ema9","macd","macd_signal","boll_upper","boll_lower","bb_pct","atr"
]

def fetch_data(symbol="BTCUSDT"):
    # Fast REST call (1s)
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=2)
        data = r.json()
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(data["openPrice"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "close": float(data["lastPrice"]),
            "volume": float(data["volume"]),
        }
    except Exception as e:
        print("❌ Fetch error:", e)
        return None

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["delta"] = df["close"].diff()
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["vol_delta"] = df["volume"].diff()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
    df["ema9"] = ta.trend.EMAIndicator(df["close"], window=9).ema_indicator()
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    bb = ta.volatility.BollingerBands(df["close"])
    df["boll_upper"] = bb.bollinger_hband()
    df["boll_lower"] = bb.bollinger_lband()
    denom = (df["boll_upper"] - df["boll_lower"]).replace(0, pd.NA)
    df["bb_pct"] = (df["close"] - df["boll_lower"]) / denom
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"]).average_true_range()
    return df.replace([float("inf"), float("-inf")], pd.NA).fillna(method="ffill").fillna(method="bfill")

def append_row(row):
    header = ["timestamp","open","high","low","close","volume","prediction","target","prediction_correct"]
    file_exists = os.path.exists(DATA_PATH)
    with open(DATA_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists: writer.writeheader()
        writer.writerow(row)

def load_df() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH) if os.path.exists(DATA_PATH) else pd.DataFrame()

def save_df(df: pd.DataFrame):
    df.to_csv(DATA_PATH, index=False)

def train_model(df_full: pd.DataFrame):
    if len(df_full) < 120: return None
    df = add_features(df_full.copy())
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
    train = df.dropna(subset=FEATURES + ["target"])
    if train.empty: return None
    X = train[FEATURES].values
    y = train["target"].values
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    if USE_XGB:
        model = XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9)
    else:
        model = RandomForestClassifier(n_estimators=300, random_state=42)
    model.fit(Xs, y)
    joblib.dump((model, scaler), MODEL_PATH)
    print("✅ Model retrained.")
    return model, scaler

def predict_latest(df_full: pd.DataFrame) -> str:
    if not os.path.exists(MODEL_PATH): return "HOLD"
    model, scaler = joblib.load(MODEL_PATH)
    df = add_features(df_full.copy())
    last = df.iloc[[-1]]
    if last[FEATURES].isna().any(axis=None):
        return "HOLD"
    Xs = scaler.transform(last[FEATURES].values)
    pred = int(model.predict(Xs)[0])
    return "BUY" if pred == 1 else "SELL"

# Flask app
app = Flask(__name__, static_folder="../frontend", static_url_path="/")

def read_status():
    if not os.path.exists(STATUS_PATH):
        st = {"active": False, "mode": "off", "symbol": SYMBOL}
        json.dump(st, open(STATUS_PATH, "w"))
    return json.load(open(STATUS_PATH))

def write_status(st):
    json.dump(st, open(STATUS_PATH, "w"))

def ai_loop():
    print("🤖 AI loop ready.")
    while True:
        st = read_status()
        if not st.get("active") or st.get("mode") == "off":
            time.sleep(0.5)
            continue

        symbol = st.get("symbol", SYMBOL)
        quote = fetch_data(symbol)
        if quote:
            row = {**quote, "prediction": "HOLD", "target": None, "prediction_correct": None}
            append_row(row)
            df = load_df()
            # periodic retrain
            if len(df) % RETRAIN_INTERVAL == 0:
                train_model(df)
            # predict
            decision = predict_latest(df)
            df.loc[df.index[-1], "prediction"] = decision
            save_df(df)
            if decision in ["BUY", "SELL"]:
                update_on_signal(decision, float(df.iloc[-1]["close"]))
            print(f"[{quote['timestamp']}] {symbol} {quote['close']:.2f} → {decision}")

        time.sleep(REFRESH_INTERVAL)

threading.Thread(target=ai_loop, daemon=True).start()

@app.route("/")
def root_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/latest")
def latest():
    df = load_df()
    if df.empty:
        return jsonify({"error": "No data yet."})
    df = add_features(df)
    last = df.iloc[-1]
    acc = df["prediction_correct"].dropna().mean() if "prediction_correct" in df.columns else None
    return jsonify({
        "timestamp": last["timestamp"],
        "open": float(last["open"]),
        "high": float(last["high"]),
        "low": float(last["low"]),
        "close": float(last["close"]),
        "volume": float(last["volume"]),
        "prediction": last.get("prediction", "HOLD"),
        "rsi": float(last["rsi"]),
        "macd": float(last["macd"]),
        "accuracy": None if acc is None else float(acc)
    })

@app.route("/mode/<name>", methods=["POST"])
def set_mode(name):
    name = name.lower()
    if name not in ["run", "scan", "off"]:
        return jsonify({"error": "Invalid mode"}), 400
    st = read_status()
    st["active"] = (name != "off")
    st["mode"] = name
    write_status(st)
    return jsonify(st)

@app.route("/symbol", methods=["POST"])
def set_symbol():
    data = request.get_json(force=True, silent=True) or {}
    sym = data.get("symbol", "").upper()
    if not sym:
        return jsonify({"error": "symbol required"}), 400
    st = read_status(); st["symbol"] = sym
    write_status(st)
    return jsonify(st)

if __name__ == "__main__":
    print("🚀 Flask AI Trader running at http://127.0.0.1:5000")
    app.run(port=5000)
