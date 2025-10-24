import os, json

TRACK_FILE = os.path.join(os.path.dirname(__file__), "balance.json")

DEFAULT_STATE = {
    "balance": 10000.0,
    "position": 0.0,
    "avg_price": 0.0,
    "profit": 0.0
}

def load_state():
    if not os.path.exists(TRACK_FILE):
        save_state(DEFAULT_STATE)
    with open(TRACK_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(TRACK_FILE, "w") as f:
        json.dump(state, f, indent=2)

def update_on_signal(signal, price):
    st = load_state()
    qty = 1.0
    if signal == "BUY" and st["balance"] >= price:
        st["balance"] -= price * qty
        st["position"] += qty
        st["avg_price"] = price
    elif signal == "SELL" and st["position"] > 0:
        st["balance"] += price * st["position"]
        st["profit"] += (price - st["avg_price"]) * st["position"]
        st["position"] = 0
        st["avg_price"] = 0
    save_state(st)
    return st

def get_state():
    st = load_state()
    st["equity"] = st["balance"] + st["position"] * st["avg_price"]
    return st
