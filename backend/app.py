from flask import Flask, jsonify, request
import os, json, pandas as pd, ta
from tracker import get_state

app = Flask(__name__)
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR,"data","market_data.csv")
STATUS_PATH = os.path.join(BASE_DIR,"ai_status.json")

def read_status():
    if not os.path.exists(STATUS_PATH):
        return {"active":True,"training":False,"mode":"run"}
    return json.load(open(STATUS_PATH))

def write_status(st):
    json.dump(st, open(STATUS_PATH,"w"))

@app.route("/status")
def status(): return jsonify(read_status())

@app.route("/mode/<name>", methods=["POST"])
def set_mode(name):
    name=name.lower()
    if name not in ["run","scan","off"]:
        return jsonify({"error":"Invalid mode"}),400
    st=read_status(); st["mode"]=name
    write_status(st)
    return jsonify(st)

@app.route("/latest")
def latest():
    if not os.path.exists(DATA_PATH): return jsonify({"error":"No data yet."})
    df=pd.read_csv(DATA_PATH)
    if df.empty: return jsonify({"error":"No data yet."})
    for c in ["open","high","low","close","volume"]:
        df[c]=pd.to_numeric(df[c],errors="coerce")
    df["rsi"]=ta.momentum.RSIIndicator(df["close"]).rsi()
    last=df.iloc[-1]
    acc=df["prediction_correct"].dropna().mean() if "prediction_correct" in df.columns else None
    out={
        "timestamp":last["timestamp"],
        "open":float(last["open"]),
        "high":float(last["high"]),
        "low":float(last["low"]),
        "close":float(last["close"]),
        "prediction":last.get("prediction","HOLD"),
        "rsi":float(last["rsi"]),
        "accuracy":None if acc is None else float(acc)
    }
    out.update(read_status())
    out.update(get_state())
    return jsonify(out)

if __name__=="__main__":
    app.run(port=5000)
