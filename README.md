# AI Trader — One-Click Dashboard (Binance, 1s updates)

Run everything with a single command:
- Flask serves the dashboard and API at http://127.0.0.1:5000
- Background thread fetches Binance prices every 1s
- Indicators (RSI, MACD, BB, ATR) and ML predictions (BUY/SELL)
- Control buttons on the dashboard: Start / Scan / Stop
- Switch symbol from the dropdown (BTC/ETH/DOGE/SOL/ADA)

## Setup

```bash
cd backend
python -m pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## Configure

Edit `backend/.env` (optional):

```
SYMBOL=BTCUSDT
REFRESH_INTERVAL=1
RETRAIN_INTERVAL=200
```

## Notes
- No API keys required (public Binance REST).
- Data/models/balance are kept locally.
- `.gitignore` keeps runtime files out of Git.
