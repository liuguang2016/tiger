"""
Backtest API routes.
Endpoints: /api/crypto/backtest/*, /api/stock/backtest/*
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.crypto_backtest import start_backtest, get_backtest_status
from services.stock_backtest import start_backtest as start_stock_backtest
from services.stock_backtest import get_backtest_status as get_stock_backtest_status
from services import database as db
from api.response import success_response, error_response

router = APIRouter()


@router.post("/crypto/backtest/run")
async def run_backtest_api(params: dict = None):
    """Start crypto backtest task."""
    if params is None:
        params = {}
    run_id = start_backtest(params)
    return success_response(run_id=run_id)


@router.get("/crypto/backtest/status")
async def backtest_status_api():
    """Get backtest progress and results."""
    status = get_backtest_status()
    return JSONResponse(content={
        'success': True,
        'status': status['status'],
        'progress': status['progress'],
        'total': status['total'],
        'message': status['message'],
        'summary': status['summary'] if status['status'] == 'done' else {},
        'equity': status['equity'] if status['status'] == 'done' else [],
        'trades': status['trades'] if status['status'] == 'done' else [],
    })


@router.get("/crypto/backtest/history")
async def backtest_history_api(limit: int = Query(20)):
    """Get historical backtest records."""
    runs = db.get_backtest_history(limit=limit)
    return success_response(runs=runs)


@router.get("/crypto/backtest/{run_id}")
async def backtest_detail_api(run_id: str):
    """Get detailed results of a specific backtest."""
    run = db.get_backtest_run(run_id)
    if not run:
        return error_response(message="回测记录不存在", status_code=404)
    trades = db.get_backtest_trades(run_id)
    run['trades'] = trades
    return success_response(run=run)


@router.post("/stock/backtest/run")
async def run_stock_backtest_api(params: dict = None):
    """Start stock backtest task."""
    if params is None:
        params = {}
    run_id = start_stock_backtest(params)
    return success_response(run_id=run_id)


@router.get("/stock/backtest/status")
async def stock_backtest_status_api():
    """Get stock backtest progress and results."""
    status = get_stock_backtest_status()
    return JSONResponse(content={
        'success': True,
        'status': status['status'],
        'progress': status['progress'],
        'total': status['total'],
        'message': status['message'],
        'summary': status.get('summary', {}),
        'equity': status.get('equity', []),
        'trades': status.get('trades', []),
    })
