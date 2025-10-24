# 🤖 AI Trader v4.8 Pro Studio

**Live 1s crypto paper-trading simulator** with candlestick charts, RSI/MACD signals, and realistic trade execution (virtual fees, allocation slider).

## Quick Start (Windows)
1. Unzip the folder.
2. Open `backend`, double‑click `run_ai_trader.bat` (or run from the project root).
3. Your default browser opens the dashboard: `http://127.0.0.1:5000`
4. Use **Run / Scan / Stop**, pick a coin, and adjust **Trade Allocation**.

## Tech
- Flask backend, 1s loop
- Binance (fast) → CoinGecko (fallback)
- Chart.js + Financial plugin (UMD, local-friendly)
- /logs live stream viewer
- GitHub-ready: `.env.example`, `.gitignore`, CI workflow
