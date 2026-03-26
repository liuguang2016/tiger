"""
Trade-related API routes.
Endpoints: /api/upload, /api/trades, /api/kline, /api/report
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, Query, HTTPException
from fastapi.responses import JSONResponse

from services.parser import parse_csv
from services.matcher import match_trades
from services.stock_data import fetch_kline_data
from services.analyzer import analyze_trading_style
from services import database as db
from api.response import success_response, error_response

router = APIRouter()


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload delivery order CSV file.
    Clears old data, parses, matches trades, saves to SQLite.
    """
    if not file.filename:
        return error_response(message="请上传 CSV 文件", status_code=400)

    if not file.filename.lower().endswith('.csv'):
        return error_response(message="请上传 CSV 格式文件", status_code=400)

    # Read file content
    file_content = await file.read()

    # Parse CSV
    parse_result = parse_csv(file_content)
    if not parse_result['success']:
        return error_response(message=parse_result['message'], status_code=400)

    # Match trades and calculate P&L
    records = parse_result['data']
    trade_result = match_trades(records)

    # Save to database (clear old data first)
    db.clear_all()
    db.save_raw_records(records)
    db.save_matched_trades(trade_result['trades'])
    db.save_stats(trade_result['stats'])

    return success_response(
        message=parse_result['message'],
        parse_info={
            'total_rows': parse_result['total_rows'],
            'valid_rows': parse_result['valid_rows'],
        },
        trades=trade_result['profitable'],
        stats=trade_result['stats'],
    )


@router.get("/trades")
async def get_trades(type: str = Query("profitable")):
    """
    Get trade list.
    Query param: type=profitable|losing|all (default: profitable)
    """
    if not db.has_data():
        return error_response(message="请先上传交割单", status_code=400)

    trades = db.get_trades(type)
    stats = db.get_stats() or {}

    return success_response(trades=trades, stats=stats)


@router.get("/kline")
async def get_kline(
    stock_code: str = Query(...),
    buy_date: Optional[str] = Query(None),
    sell_date: Optional[str] = Query(None),
):
    """
    Get K-line data for a specific trade.
    Query params:
        stock_code: Stock code (required)
        buy_date: Buy date (optional)
        sell_date: Sell date (optional)
    """
    if not stock_code:
        return error_response(message="缺少参数：stock_code", status_code=400)

    if not buy_date or not sell_date:
        sell_date = datetime.now().strftime('%Y-%m-%d')
        buy_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

    kline_data = fetch_kline_data(stock_code, buy_date, sell_date)

    if not kline_data['success']:
        return JSONResponse(content=kline_data, status_code=500)

    kline_data['buy_date'] = buy_date or ''
    kline_data['sell_date'] = sell_date or ''

    return JSONResponse(content=kline_data)


@router.get("/report")
async def get_report():
    """Generate trading style analysis report."""
    if not db.has_data():
        return error_response(message="请先上传交割单", status_code=400)

    trade_result = db.get_trade_result_for_report()
    report = analyze_trading_style(trade_result)
    return success_response(report=report)
