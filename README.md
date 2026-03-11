# CryptoEdge Trading Platform

A comprehensive, full-stack algorithmic cryptocurrency trading platform. CryptoEdge allows you to build, backtest, and deploy sophisticated trading strategies, visually screen for the highest probability setups, and execute them live with automated Telegram alerts.

## 🚀 Features

- **Advanced Backtesting Engine**: Test custom PineScript/Python strategies across multiple timeframes simultaneously.
- **Dynamic Coin Screener**: Filter backtest results by win rate, minimum trades, and automatically deploy the absolute most profitable strategy per coin.
- **Live Market Scanner**: Runs quietly in the background (via APScheduler), scanning live Binance data every 15 minutes against your deployed strategies.
- **Telegram Integration**: Instant, beautifully formatted buy/sell alerts sent directly to your phone when a live signal triggers.
- **Beautiful Dashboard**: Real-time TradingView charts, active signal tracking, and performance metrics built with a stunning dark-mode UI.

## Tech Stack

- **Frontend**: React (Vite), React Query v5, Framer Motion, Lucide Icons
- **Backend**: Python, FastAPI, SQLAlchemy
- **Data/Trading**: CCXT (Binance API), Pandas, NumPy, TA-Lib (Indicators)
- **Database**: MySQL

---

## 🛠️ Setup & Installation

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- MySQL Server

### 1. Database Setup
1. Open MySQL and create a new database:
   ```sql
   CREATE DATABASE crypto_platform;
   ```

### 2. Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Mac/Linux
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the `backend` directory with your credentials:
   ```env
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_password
   DB_NAME=crypto_platform
   
   BINANCE_API_KEY=your_binance_api_key
   
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_telegram_chat_id
   ```

### 3. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```

---

## 🏃‍♂️ How to Run the Application

You need to run both the backend and frontend servers simultaneously in separate terminal windows.

### Starting the Backend
1. Open a terminal and navigate to the `backend` folder.
2. Activate your virtual environment (if not already activated).
3. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
*The backend API will now be running on `http://127.0.0.1:8000`. The Live Market Scanner will automatically start in the background.*

### Starting the Frontend
1. Open a second terminal and navigate to the `frontend` folder.
2. Start the Vite development server:
   ```bash
   npm run dev
   ```
*The frontend application will now be running on `http://localhost:5173`. Open this in your browser to access CryptoEdge.*

---

## ⚡ Using the Platform

1. **Test Strategies**: Go to the **Backtest** page and run a simulation across all coins and timeframes.
2. **Assign Coins**: Go to the **Screener** page. Filter by `Min Win% > 80%`. Select the best coins and click "Assign Selected". The system will intelligently deploy the single most profitable strategy for each coin.
3. **Live Trading**: Go to the **Dashboard**. The background scanner is now actively watching your assigned coins. You will see signals appear under the "Live Signals" panel and receive Telegram alerts instantly. Use the **Scan Now** button to force a manual scan at any time.
