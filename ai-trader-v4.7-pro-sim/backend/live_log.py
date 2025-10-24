import os
from collections import deque
from datetime import datetime

LOG_BUFFER = deque(maxlen=500)
def _ts(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ensure_log_dir(base_dir):
    logs_dir = os.path.join(base_dir, "logs"); os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, "trading.log")

def log_line(base_dir, symbol, action, price=None, extra=""):
    icon = "🟡" if action=="SCAN" else ("🟢" if action=="BUY" else ("🔴" if action=="SELL" else "⚪"))
    core = f"{icon} {action}"
    if price is not None:
        try: core += f" @ {float(price):,.6f}"
        except: core += f" @ {price}"
    if extra: core += f"  {extra}"
    line = f"[{_ts()}] [{symbol}] {core}"
    LOG_BUFFER.append(line)
    try:
        with open(ensure_log_dir(base_dir), "a", encoding="utf-8") as f: f.write(line+"\n")
    except: pass
    print(line, flush=True)
    return line

def recent_lines(n=50):
    return list(LOG_BUFFER)[-n:] if n>0 else []
