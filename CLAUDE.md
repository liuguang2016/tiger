# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Tigger** - A股与数字货币交易分析系统 (A-Share & Crypto Trading Analysis System)

A comprehensive trading assistant combining delivery order analysis, spring rebound stock screening, and cryptocurrency quantitative trading based on price action theory.

## Commands

### Docker Deployment (Recommended)

```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env, set POSTGRES_PASSWORD

# 2. Build frontend
cd frontend && pnpm install && pnpm run build && cd ..

# 3. Start all services
docker compose up -d

# 4. Access the application
# Frontend: http://localhost:8080
# API: http://localhost:8080/api/*
# API docs: http://localhost:8080/docs
```

### Traditional Installation (without Docker)

```bash
# Install dependencies
cd backend
pip install -r requirements.txt
cd ..

# Run the application (FastAPI - recommended)
cd backend
uvicorn main:app --reload --port 8002

# Access the web interface
# http://127.0.0.1:8002

# API documentation (FastAPI auto-generated)
# http://127.0.0.1:8002/docs
```

## Architecture

### Technology Stack
- **Backend**: Python 3.14 + FastAPI 0.115+
- **Data Processing**: pandas, numpy
- **A-Share Data**: 东方财富 API / 腾讯财经 API (via akshare)
- **Crypto**: Binance REST API (HMAC-SHA256)
- **Frontend**: ECharts for charts
- **Database**: PostgreSQL (Docker container)
- **Containerization**: Docker + Docker Compose + Nginx

### Project Structure
```
tigger/
├── backend/
│   ├── main.py                 # FastAPI main application entry point
│   ├── app.py                  # Flask main application (kept for comparison)
│   ├── api/                    # API route modules
│   │   ├── response.py         # Response helpers (success_response, error_response)
│   │   └── routes/
│   │       ├── trades.py       # /api/upload, /api/trades, /api/kline, /api/report
│   │       ├── screener.py     # /api/screener/* (9 endpoints)
│   │       ├── crypto.py       # /api/crypto/* (9 endpoints)
│   │       └── backtest.py     # /api/crypto/backtest/*, /api/stock/backtest/* (5 endpoints)
│   ├── requirements.txt         # Python dependencies
│   ├── services/               # Business logic
│   │   ├── parser.py          # CSV delivery order parsing
│   │   ├── matcher.py         # FIFO trade matching & P&L calculation
│   │   ├── analyzer.py        # Trading style analysis
│   │   ├── stock_data.py      # A-share K-line data fetching
│   │   ├── database.py        # PostgreSQL data storage
│   │   ├── screener.py        # Spring rebound stock screener
│   │   ├── signal_engine.py   # Trading signal generation
│   │   ├── binance_client.py  # Binance REST API wrapper
│   │   ├── crypto_trader.py   # Crypto trading bot
│   │   ├── crypto_backtest.py # Crypto strategy backtest engine
│   │   └── stock_backtest.py  # Stock strategy backtest engine
│   └── strategies/            # Trading strategies
├── frontend/                   # Vue 3 frontend source
├── static/                     # Vue build output (served by Nginx)
├── docker/                     # Docker configuration
│   └── nginx/nginx.conf       # Nginx reverse proxy config
├── docker-compose.yml          # Docker Compose (dev)
├── docker-compose.prod.yml     # Docker Compose (prod)
├── Dockerfile                  # Backend Docker image
└── scripts/
    └── migrate_sqlite_to_pg.py # SQLite to PostgreSQL migration
```

### Core Modules

**services/database.py** - PostgreSQL abstraction layer with tables for:
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

## Active Technologies
- Python 3.14 + FastAPI 0.115+, uvicorn[standard], python-multipart (001-fastapi-migration)
- PostgreSQL (via Docker) - migrated from SQLite (002-docker-architecture)
- Docker + Docker Compose + Nginx (002-docker-architecture)

## Recent Changes
- 001-fastapi-migration: Added Python 3.14 + FastAPI 0.115+, uvicorn[standard], python-multipart
- 002-docker-architecture: Docker deployment with PostgreSQL, Nginx reverse proxy
