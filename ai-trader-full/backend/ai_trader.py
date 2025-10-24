import os, time, csv, joblib, warnings, json 
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from webull import webull
from sklearn.preprocessing import StandardScaler
import ta
from tracker import update_on_signal

warnings.filterwarnings("ignore")
load_dotenv()

BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "data", "market_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "model.pkl")
STATUS_PATH = os.path.join(BASE_DIR, "ai_status.json")

REFRESH_INTERVAL = 10
RETRAIN_INTERVAL = 50
TICKER = os.getenv("TICKER", "BTCUSD")

os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

wb = webull()
wb.login(os.getenv("WEBULL_EMAIL"), os.getenv("WEBULL_PASSWORD"))

try:
    from xgboost import XGBClassifier
    USE_XGB = True
except:
    from sklearn.ensemble import RandomForestClassifier
    USE_XGB = False

FEATURES = [
    "open","high","low","close","volume","delta","ma5","ma10","vol_delta",
    "rsi","ema9","macd","macd_signal","boll_upper","boll_lower","bb_pct","atr"
]

def add_features(df):
    if df.empty: return df
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
    df["bb_pct"] = (df["close"] - df["boll_lower"]) / (df["boll_upper"] - df["boll_lower"])
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"]).average_true_range()
    return df.fillna(method="ffill").fillna(method="bfill")

def fetch_data():
    q = wb.get_quote(TICKER)
    if not q: return None
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "open": q.get("open"), "high": q.get("high"),
        "low": q.get("low"), "close": q.get("pPrice"),
        "volume": q.get("volume"),
    }

def append_row(row):
    header = ["timestamp","open","high","low","close","volume","prediction","target","prediction_correct"]
    file_exists = os.path.exists(DATA_PATH)
    with open(DATA_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists: writer.writeheader()
        writer.writerow(row)

def load_df():
    return pd.read_csv(DATA_PATH) if os.path.exists(DATA_PATH) else pd.DataFrame()

def save_df(df): df.to_csv(DATA_PATH, index=False)

def set_training(active):
    st = json.load(open(STATUS_PATH))
    st["training"] = active
    json.dump(st, open(STATUS_PATH,"w"))

def train_model(df):
    if len(df) < 80: return None
    df = add_features(df)
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
    df = df.dropna(subset=FEATURES + ["target"])
    if df.empty: return None
    X = df[FEATURES].values
    y = df["target"].values
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    model = XGBClassifier(n_estimators=200) if USE_XGB else RandomForestClassifier(n_estimators=200)
    set_training(True)
    model.fit(Xs, y)
    joblib.dump((model, scaler), MODEL_PATH)
    set_training(False)
    print("✅ Model retrained.")
    return model, scaler

def predict(df):
    if not os.path.exists(MODEL_PATH): return "HOLD"
    model, scaler = joblib.load(MODEL_PATH)
    df = add_features(df)
    last = df[FEATURES].iloc[[-1]]
    pred = model.predict(scaler.transform(last))[0]
    return "BUY" if pred == 1 else "SELL"

if not os.path.exists(STATUS_PATH):
    json.dump({"active": True, "training": False, "mode": "run"}, open(STATUS_PATH,"w"))

print(f"🚀 AI Trader running on {TICKER}")
while True:
    try:
        status = json.load(open(STATUS_PATH))
        mode = status.get("mode","run")

        if mode == "off":
            print("🛑 AI paused.")
            time.sleep(3)
            continue
        elif mode == "scan":
            data = fetch_data()
            if data:
                data.update({"prediction":"SCAN","target":None,"prediction_correct":None})
                append_row(data)
                print(f"🔍 Scanning {TICKER} | close={data['close']}")
            time.sleep(REFRESH_INTERVAL)
            continue

        # --- RUN mode ---
        data = fetch_data()
        if data:
            data.update({"prediction":"HOLD","target":None,"prediction_correct":None})
            append_row(data)
            df = load_df()
            if len(df) % RETRAIN_INTERVAL == 0: train_model(df)
            decision = predict(df)
            df.loc[df.index[-1], "prediction"] = decision
            save_df(df)
            if decision in ["BUY","SELL"]:
                update_on_signal(decision, float(df.iloc[-1]["close"]))
            print(f"🤖 {decision} | close={data['close']}")
        time.sleep(REFRESH_INTERVAL)
    except Exception as e:
        print("Error:", e)
        time.sleep(5)
