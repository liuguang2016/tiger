# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Tigger** - A股与数字货币交易分析系统 (A-Share & Crypto Trading Analysis System)

A comprehensive trading assistant combining delivery order analysis, spring rebound stock screening, and cryptocurrency quantitative trading based on price action theory.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py

# Access the web interface
# http://127.0.0.1:5000
```

## Architecture

### Technology Stack
- **Backend**: Python 3.14 + Flask
- **Data Processing**: pandas, numpy
- **A-Share Data**: 东方财富 API / 腾讯财经 API (via akshare)
- **Crypto**: Binance REST API (HMAC-SHA256)
- **Frontend**: ECharts for charts
- **Database**: SQLite (`data/trades.db`)

### Project Structure
```
tigger/
├── app.py                      # Flask main application & API routes
├── requirements.txt            # Python dependencies
├── services/
│   ├── parser.py               # CSV delivery order parsing
│   ├── matcher.py              # FIFO trade matching & P&L calculation
│   ├── analyzer.py             # Trading style analysis
│   ├── stock_data.py           # A-share K-line data fetching
│   ├── database.py             # SQLite data storage
│   ├── screener.py             # Spring rebound stock screener
│   ├── signal_engine.py        # Trading signal generation
│   ├── binance_client.py       # Binance REST API wrapper
│   ├── crypto_trader.py        # Crypto trading bot
│   ├── crypto_backtest.py      # Crypto strategy backtest engine
│   └── stock_backtest.py       # Stock strategy backtest engine
└── static/
    ├── index.html              # Main frontend page
    ├── css/style.css           # Styles
    └── js/
        ├── app.js              # Frontend interaction logic
        └── chart.js            # K-line chart rendering
```

### Core Modules

**services/database.py** - SQLite abstraction layer with tables for:
- `raw_records` - Parsed CSV records
- `matched_trades` - FIFO-paired trades with P&L
- `stats` - Trading statistics
- `pool_stocks` - Screened stock pool
- `crypto_config` - Binance API keys
- `crypto_trades` - Trade history
- `backtest_runs` - Backtest results

**services/screener.py** - Spring rebound screening engine:
- Async task-based screening (5000+ stocks)
- Multi-filter: decline depth, stability signals, volume anomaly, MA support, K-line patterns
- Composite scoring model

**services/crypto_trader.py** - Binance trading bot:
- Paper trading (simulation) and Live modes
- Spring rebound strategy with entry/exit signals
- Risk management: tiered take-profit, fixed stop-loss
- Thread-based continuous operation

**services/crypto_backtest.py** - Backtest engine:
- Historical K-line simulation (1h/4h/1d intervals)
- Bar-by-bar strategy execution
- Performance metrics: return, Sharpe ratio, max drawdown, win rate
