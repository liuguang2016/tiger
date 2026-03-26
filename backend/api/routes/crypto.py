"""
Cryptocurrency API routes.
Endpoints: /api/crypto/*
"""
import pandas as pd
from datetime import datetime as dt
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.crypto_trader import get_bot
from services.binance_client import BinanceClient
from services import database as db
from api.response import success_response, error_response

router = APIRouter()


@router.get("/crypto/config")
async def get_crypto_config():
    """Get crypto configuration (API keys masked)."""
    cfg = db.get_crypto_config()
    if not cfg:
        return success_response(config=None)

    masked_key = cfg['api_key'][-4:].rjust(len(cfg['api_key']), '*') if cfg['api_key'] else ''
    return success_response(
        config={
            'api_key': masked_key,
            'has_secret': bool(cfg['api_secret']),
            'is_running': cfg['is_running'],
            'params': cfg['config'],
            'updated_at': cfg['updated_at'],
        }
    )


@router.post("/crypto/config")
async def save_crypto_config(
    api_key: str = None,
    api_secret: str = None,
    params: dict = None,
):
    """Save API keys and strategy parameters."""
    if params is None:
        params = {}
    # Handle both form data and JSON
    if not api_key:
        api_key = params.get('api_key', '').strip()
    if not api_secret:
        api_secret = params.get('api_secret', '').strip()

    if not api_key or not api_secret:
        return error_response(message="请输入 API Key 和 Secret", status_code=400)

    db.save_crypto_config(api_key, api_secret, params)

    bot = get_bot()
    bot.configure(api_key, api_secret, params)

    connected = bot.client.test_connectivity() if bot.client else False
    auth_ok = bot.client.test_auth() if connected and bot.client else False

    return success_response(connected=connected, auth_ok=auth_ok)


@router.post("/crypto/bot/start")
async def start_crypto_bot(params: dict = None):
    """Start trading bot."""
    if params is None:
        params = {}

    bot = get_bot()

    if params.get('params'):
        cfg = db.get_crypto_config()
        if cfg:
            bot.configure(cfg['api_key'], cfg['api_secret'], params['params'])
            db.save_crypto_config(cfg['api_key'], cfg['api_secret'], params['params'])

    ok = bot.start()
    if not ok:
        return error_response(message=bot.error_msg, status_code=400)
    return success_response()


@router.post("/crypto/bot/stop")
async def stop_crypto_bot():
    """Stop trading bot."""
    bot = get_bot()
    bot.stop()
    return success_response()


@router.get("/crypto/bot/status")
async def crypto_bot_status():
    """Get bot status."""
    bot = get_bot()
    status = bot.get_status()
    return success_response(**status)


@router.post("/crypto/bot/scan")
async def crypto_manual_scan():
    """Manually scan for trading signals."""
    bot = get_bot()
    if not bot.client:
        return error_response(message="请先配置 API Key", status_code=400)
    signals = bot.manual_scan()
    return success_response(signals=signals)


@router.get("/crypto/trades")
async def get_crypto_trades(
    limit: int = Query(100),
    symbol: str = Query(None),
):
    """Get crypto trade history."""
    trades = db.get_crypto_trades(limit=limit, symbol=symbol)
    stats = db.get_crypto_trade_stats()
    return success_response(trades=trades, stats=stats)


@router.get("/crypto/kline")
async def get_crypto_kline(
    symbol: str = Query(...),
    interval: str = Query("4h"),
    limit: int = Query(200),
):
    """Get crypto K-line data."""
    if not symbol:
        return error_response(message="缺少 symbol 参数", status_code=400)

    try:
        client = BinanceClient()
        raw = client.get_klines(symbol, interval, limit)
        if not raw:
            return error_response(message="无K线数据", status_code=404)

        dates = []
        ohlcv = []
        volumes = []
        closes_arr = []

        for k in raw:
            ts = int(k[0]) / 1000
            date_str = dt.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            o, h, l, c, v = float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])
            dates.append(date_str)
            ohlcv.append([o, c, l, h])
            volumes.append(v)
            closes_arr.append(c)

        s = pd.Series(closes_arr)
        ma7 = s.rolling(7).mean().round(4).tolist()
        ma25 = s.rolling(25).mean().round(4).tolist()
        ma99 = s.rolling(99).mean().round(4).tolist()

        ma7 = [None if pd.isna(v) else v for v in ma7]
        ma25 = [None if pd.isna(v) else v for v in ma25]
        ma99 = [None if pd.isna(v) else v for v in ma99]

        return JSONResponse(content={
            'success': True,
            'symbol': symbol,
            'dates': dates,
            'ohlcv': ohlcv,
            'volumes': volumes,
            'ma7': ma7,
            'ma25': ma25,
            'ma99': ma99,
        })
    except Exception as e:
        return error_response(message=str(e), status_code=500)
