# AI Trader — One-Click Final (1s Live Candles)

This repo runs a real-time AI crypto dashboard with **one command**.

## 🚀 Quick Start
```bash
cd backend
python -m pip install -r requirements.txt
python app.py
```
Open: http://127.0.0.1:5000

## 🧠 Features
- 1s live price from Binance (no API key)
- Candlestick chart + RSI & MACD
- AI predictions (BUY / SELL / HOLD)
- Start / Scan / Stop controls
- Select BTC, ETH, DOGE, SOL, ADA
- Paper trading balance tracking

## ⚙️ Config (`backend/.env`)
```
SYMBOL=BTCUSDT
REFRESH_INTERVAL=1
RETRAIN_INTERVAL=200
```

## 📂 Structure
- `backend/` Flask API + AI loop + data/models folders
- `frontend/` Dashboard served by Flask

## 📝 Notes
- Keep app running for learning and live charts.
- Data saves to backend/data/market_data.csv.
