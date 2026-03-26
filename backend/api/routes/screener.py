"""
Stock screener API routes.
Endpoints: /api/screener/*
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from services.screener import start_screening, get_screening_status, fetch_index_info
from services.strategy_loader import list_strategies, run_strategy
from services import database as db
from api.response import success_response, error_response

router = APIRouter()

# Track saved task ID to avoid duplicate saves
_screener_saved_task_id = None


@router.post("/screener/run")
async def run_screener(params: dict = None):
    """Start spring stock screening task."""
    if params is None:
        params = {}
    task_id = start_screening(params)
    return success_response(task_id=task_id)


@router.get("/screener/status")
async def screener_status():
    """Get screening task progress and results."""
    global _screener_saved_task_id
    status = get_screening_status()

    if status['status'] == 'done' and status['results'] and \
       status.get('task_id') != _screener_saved_task_id:
        db.save_pool_stocks(status['results'])
        _screener_saved_task_id = status.get('task_id')

    return JSONResponse(content={
        'success': True,
        'status': status['status'],
        'progress': status['progress'],
        'total': status['total'],
        'found': status['found'],
        'message': status['message'],
        'index_info': status.get('index_info', {}),
        'results': status['results'] if status['status'] == 'done' else [],
    })


@router.get("/screener/index")
async def get_index():
    """Get market index information (SH, SZ, CYB)."""
    info = fetch_index_info()
    return success_response(index=info)


@router.get("/screener/pool")
async def get_pool():
    """Get stock pool list."""
    stocks = db.get_pool_stocks()
    return success_response(stocks=stocks)


@router.delete("/screener/pool/{stock_code}")
async def remove_from_pool(stock_code: str):
    """Remove a stock from the pool."""
    db.remove_pool_stock(stock_code)
    return success_response()


@router.delete("/screener/pool")
async def clear_pool():
    """Clear the entire stock pool."""
    db.clear_pool()
    return success_response()


@router.get("/screener/strategies")
async def get_strategies():
    """List available strategies."""
    strategies = list_strategies()
    return success_response(strategies=strategies)


@router.post("/screener/strategy/run")
async def run_strategy_api(body: dict = None):
    """
    Run a specific strategy for stock selection.
    Strategy ID passed in JSON body.
    """
    if body is None:
        body = {}
    strategy_id = body.get('strategy_id', '')

    if not strategy_id:
        return error_response(message="缺少 strategy_id", status_code=400)

    try:
        results = run_strategy(strategy_id)
        db.save_pool_stocks(results)
        return success_response(count=len(results))
    except FileNotFoundError as e:
        return error_response(message=str(e), status_code=404)
    except (ValueError, TypeError) as e:
        return error_response(message=str(e), status_code=400)
    except Exception as e:
        return error_response(message=str(e), status_code=500)
