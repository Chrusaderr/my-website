# AI Trader Bot + Dashboard

A trading AI that uses machine learning and rich indicators to predict buy/sell signals, plus a live web dashboard.

## ⚙️ Local Run

1. Install dependencies  
   `pip install -r backend/requirements.txt`

2. Add your credentials in `backend/.env`

3. Start the trader  
   `python backend/ai_trader.py`

4. Start the API  
   `python backend/app.py`

5. Open `index.html` in your browser (uses local Flask endpoint or static demo data).

## 🌐 GitHub Pages

When hosted on GitHub Pages, `index.html` automatically loads demo data from `api_preview.json`.
