# AI Trader Dashboard

An AI-driven crypto dashboard that learns from charts, predicts movements, and tracks paper profits using Webull data.

## Features
- Live data feed from Webull
- Run / Scan / Off modes
- Candlestick + RSI chart
- Paper trading simulation
- Live accuracy & profit tracking

## Setup
1. `cd ai_trader/backend`
2. `pip install -r requirements.txt`
3. Create `.env` and fill Webull credentials
4. Run the bot:
   ```bash
   python ai_trader.py
   python app.py
   ```
5. Open `frontend/index.html` in your browser.
