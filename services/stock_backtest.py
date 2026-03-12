"""
个人选股策略历史回测引擎
买入：选股默认条件（screener 平台底部 + 下探收涨 + 7维评分）
卖出：数字货币策略（出场反转、上涨收窄、ATR/固定止损、移动止损）
异步执行 + 进度轮询
"""

import math
import threading
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from services import database as db
from services import signal_engine as sig
from services import stock_data
from services import screener

logger = logging.getLogger(__name__)

_bt_lock = threading.Lock()
_bt_state: Dict = {
    "status": "idle",
    "run_id": None,
    "progress": 0,
    "total": 0,
    "message": "",
    "summary": {},
    "equity": [],
    "trades": [],
}

# A股费用：佣金万分之2.5(买卖各)，印花税千分之1(仅卖出)
FEE_BUY = 0.00025
FEE_SELL = 0.00025 + 0.001


def start_backtest(params: dict) -> str:
    """启动回测，返回 run_id"""
    with _bt_lock:
        if _bt_state["status"] == "running":
            return _bt_state["run_id"]

        run_id = uuid.uuid4().hex[:12]
        _bt_state.update({
            "status": "running",
            "run_id": run_id,
            "progress": 0,
            "total": 0,
            "message": "初始化...",
            "summary": {},
            "equity": [],
            "trades": [],
        })

    t = threading.Thread(target=_run_backtest, args=(run_id, params), daemon=True)
    t.start()
    return run_id


def get_backtest_status() -> dict:
    with _bt_lock:
        return dict(_bt_state)


def _update(k, v):
    with _bt_lock:
        _bt_state[k] = v


def _update_multi(**kw):
    with _bt_lock:
        _bt_state.update(kw)


def _evaluate_market(index_kline: Optional[pd.DataFrame]) -> Tuple[float, str]:
    """大盘环境评估，与 screener 一致"""
    if index_kline is None or len(index_kline) < 10:
        return 5.0, "neutral"
    closes = index_kline["close"].values.astype(float)
    recent = closes[-5:]
    prev = closes[-10:-5]
    if len(prev) < 5:
        return 5.0, "neutral"
    chg = (recent[-1] / prev[-1] - 1) * 100
    if chg > 2:
        return 8, "strong"
    if chg < -2:
        return 2, "weak"
    return 5, "neutral"


def _run_backtest(run_id: str, params: dict):
    try:
        days = int(params.get("days", 180))
        initial_capital = float(params.get("initial_capital", 100000))
        stop_loss_pct = float(params.get("stop_loss_pct", 5)) / 100.0
        max_pos_pct = float(params.get("max_position_pct", 10)) / 100.0
        max_positions = int(params.get("max_positions", 5))
        drop_pct = float(params.get("drop_pct", 15)) / 100.0
        ma_filter = params.get("ma_filter", "none")
        min_platform_days = int(params.get("min_platform_days", 1))
        use_probe_confirm = params.get("use_probe_confirm", True)
        use_atr_stop = params.get("use_atr_stop", True)
        use_trailing = params.get("use_trailing", True)
        use_exit_reversal = params.get("use_exit_reversal", True)

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days + 120)).strftime("%Y-%m-%d")

        universe = params.get("universe", "pool")  # pool | all

        # 1) 获取股票列表
        if universe == "pool":
            pool_stocks = db.get_pool_stocks()
            if not pool_stocks:
                _update_multi(status="error", message="请先在交易池中添加股票再运行回测")
                return
            symbols = [(s["stock_code"], s["stock_name"]) for s in pool_stocks]
        else:
            # 全A股：拉取快照，过滤后取成交额靠前的股票（控制规模，避免过慢）
            _update("message", "获取全A股列表...")
            snapshot_df = screener._fetch_all_stocks_snapshot()
            if snapshot_df is None or snapshot_df.empty:
                _update_multi(status="error", message="获取全A股列表失败")
                return
            # 过滤：排除 ST、停牌、新股等，与选股 Stage1 类似
            mask = (
                (snapshot_df["volume"] > 0) &
                (snapshot_df["turnover"] >= 0.5) &
                (snapshot_df["change_pct"] >= -9.5) &
                (snapshot_df["change_pct"] <= 9.5) &
                (snapshot_df["total_mv"] >= 2e9)
            )
            df = snapshot_df[mask].copy()
            df = df.sort_values("amount", ascending=False).head(800)  # 成交额前 800
            symbols = [(str(row["code"]), str(row["name"])) for _, row in df.iterrows()]
            if not symbols:
                _update_multi(status="error", message="无符合条件的股票")
                return

        _update_multi(total=len(symbols), message=f"拉取 {len(symbols)} 只股票K线...")

        # 2) 拉取各股及指数历史K线
        all_klines: Dict[str, pd.DataFrame] = {}
        for i, (code, name) in enumerate(symbols):
            _update_multi(progress=int(i / len(symbols) * 30), message=f"K线 ({i+1}/{len(symbols)}): {code}")
            df = stock_data.fetch_stock_kline_range(code, start_date, end_date)
            if df is not None and len(df) >= 30:
                all_klines[code] = df

        if not all_klines:
            _update_multi(status="error", message="无有效K线数据")
            return

        index_kline_full = stock_data.fetch_index_kline_range(start_date, end_date)
        if index_kline_full is None:
            index_kline_full = pd.DataFrame()

        # 3) 构建交易日时间线
        all_dates = set()
        for df in all_klines.values():
            all_dates.update(df["date"].tolist())
        timeline = sorted(all_dates)
        # 限制在回测天数内
        cut_off = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        timeline = [d for d in timeline if d >= cut_off]
        if not timeline:
            _update_multi(status="error", message="无有效交易日")
            return

        _update("message", "逐日模拟交易...")

        balance = initial_capital
        positions: Dict[str, dict] = {}
        closed_trades: List[Dict] = []
        equity_curve: List[Dict] = []
        total_days = len(timeline)

        for day_idx, date_str in enumerate(timeline):
            if day_idx % max(1, total_days // 50) == 0:
                pct = 30 + int(day_idx / total_days * 70)
                _update_multi(progress=pct, message=f"模拟 {date_str}...")

            # 指数 K 线截至当日
            idx_mask = index_kline_full["date"] <= date_str if not index_kline_full.empty else pd.Series(dtype=bool)
            index_kline_today = index_kline_full[idx_mask] if not index_kline_full.empty else None
            market_score, market_env = _evaluate_market(index_kline_today)

            # 1) 检查持仓止损/止盈/出场
            for code in list(positions.keys()):
                if code not in all_klines:
                    continue
                kdf = all_klines[code]
                bar = kdf[kdf["date"] == date_str]
                if bar.empty:
                    continue
                row = bar.iloc[0]
                high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
                pos = positions[code]
                entry_price = pos["entry_price"]

                if close > pos.get("highest_price", entry_price):
                    pos["highest_price"] = close

                atr_val = pos.get("atr", 0)

                # 出场反转 / 上涨收窄
                if use_exit_reversal:
                    hist = kdf[kdf["date"] <= date_str].tail(25)
                    if len(hist) >= 10:
                        o_arr = hist["open"].values.astype(float)
                        c_arr = hist["close"].values.astype(float)
                        h_arr = hist["high"].values.astype(float)
                        l_arr = hist["low"].values.astype(float)
                        v_arr = hist["volume"].values.astype(float)
                        recent_high = max(h_arr[-21:-1]) if len(h_arr) >= 21 else max(h_arr[:-1])
                        triggered, reason = sig.check_exit_reversal_at_high(
                            o_arr, c_arr, h_arr, l_arr, v_arr, recent_high
                        )
                        if not (triggered and reason):
                            triggered, reason = sig.check_momentum_narrowing(
                                o_arr, c_arr, h_arr, l_arr, v_arr
                            )
                        if triggered and reason:
                            balance = _close_position(
                                code, pos, date_str, close,
                                balance, positions, closed_trades, reason, FEE_SELL
                            )
                            continue

                # 止损
                if use_atr_stop and atr_val > 0:
                    stop_price = entry_price - 2 * atr_val
                else:
                    stop_price = entry_price * (1 - stop_loss_pct)
                if use_trailing and atr_val > 0:
                    pnl_atr = (close - entry_price) / atr_val if atr_val > 0 else 0
                    if pnl_atr >= 2:
                        stop_price = max(stop_price, pos.get("highest_price", entry_price) - 1.5 * atr_val)
                    elif pnl_atr >= 1:
                        stop_price = max(stop_price, entry_price)

                if low <= stop_price:
                    sell_p = max(stop_price, low)
                    reason = "ATR止损" if use_atr_stop and atr_val > 0 else "止损"
                    if use_trailing and sell_p > entry_price:
                        reason = "移动止损"
                    balance = _close_position(
                        code, pos, date_str, sell_p, balance,
                        positions, closed_trades, reason, FEE_SELL
                    )
                    continue

            # 2) 扫描入场（T+1：前一日信号，当日开盘买）
            if len(positions) < max_positions:
                date_idx = timeline.index(date_str)
                if date_idx == 0:
                    pass  # 首日无前一日，跳过
                else:
                    prev_date = timeline[date_idx - 1]
                    idx_prev = index_kline_full["date"] <= prev_date if not index_kline_full.empty else pd.Series(dtype=bool)
                    index_up_to_prev = index_kline_full[idx_prev] if not index_kline_full.empty else None
                    mkt_score, mkt_env = _evaluate_market(index_up_to_prev)

                    for code, name in symbols:
                        if code in positions or code not in all_klines:
                            continue
                        if len(positions) >= max_positions:
                            break
                        kdf = all_klines[code]
                        window = kdf[kdf["date"] <= prev_date].tail(90)
                        if len(window) < 30:
                            continue

                        result = screener.analyze_candidate_for_backtest(
                            code, name, window, index_up_to_prev,
                            mkt_score, mkt_env, drop_pct, ma_filter,
                            min_platform_days, use_probe_confirm,
                        )
                        if result is None:
                            continue

                        next_bar = kdf[kdf["date"] == date_str]
                        if next_bar.empty:
                            continue
                        open_price = float(next_bar.iloc[0]["open"])
                        order_amount = min(balance * max_pos_pct, balance * 0.95)
                        if order_amount < 100:
                            continue

                        highs = window["high"].values.astype(float)
                        lows = window["low"].values.astype(float)
                        closes_w = window["close"].values.astype(float)
                        atr_val = sig.calculate_atr(highs, lows, closes_w, 14)

                        qty = int(order_amount / open_price / 100) * 100
                        if qty < 100:
                            continue
                        cost = qty * open_price
                        fee = cost * FEE_BUY
                        balance -= cost + fee

                        positions[code] = {
                            "entry_price": open_price,
                            "quantity": qty,
                            "entry_time": date_str,
                            "entry_date": date_str,
                            "highest_price": open_price,
                            "atr": float(atr_val) if not (np.isnan(atr_val) or atr_val <= 0) else 0,
                            "stock_name": name,
                        }

            # 3) 资金曲线
            unrealized = 0.0
            for code, pos in positions.items():
                kdf = all_klines.get(code)
                if kdf is None:
                    continue
                bar = kdf[kdf["date"] == date_str]
                if not bar.empty:
                    cur = float(bar.iloc[0]["close"])
                    unrealized += (cur - pos["entry_price"]) * pos["quantity"]

            if day_idx % max(1, total_days // 200) == 0 or day_idx == total_days - 1:
                equity_curve.append({
                    "date": date_str,
                    "equity": round(balance + unrealized, 2),
                    "balance": round(balance, 2),
                })

        # 强平
        for code, pos in list(positions.items()):
            kdf = all_klines.get(code)
            if kdf is None:
                continue
            last_row = kdf.iloc[-1]
            last_date = last_row["date"]
            last_close = float(last_row["close"])
            balance = _close_position(
                code, pos, last_date, last_close,
                balance, positions, closed_trades, "回测结束", FEE_SELL
            )

        summary = _calc_summary(closed_trades, initial_capital, balance, days)
        _update_multi(
            status="done", progress=100,
            message=f"回测完成！{len(closed_trades)} 笔交易",
            summary=summary, equity=equity_curve, trades=closed_trades,
        )
        logger.info("股票回测 %s 完成: %d 笔, 收益 %.2f%%", run_id, len(closed_trades), summary.get("total_return_pct", 0))

    except Exception as e:
        logger.exception("回测异常: %s", e)
        _update_multi(status="error", message=f"回测失败: {e}")


def _close_position(
    code: str, pos: dict, exit_date: str, sell_price: float,
    balance: float, positions: Dict, closed_trades: List,
    reason: str, fee_rate: float,
) -> float:
    """平仓并更新 balance"""
    entry_price = pos["entry_price"]
    qty = pos["quantity"]
    pnl = (sell_price - entry_price) * qty
    fee = sell_price * qty * fee_rate
    balance += sell_price * qty - fee
    closed_trades.append({
        "symbol": code,
        "stock_name": pos.get("stock_name", ""),
        "side": "ROUND",
        "entry_time": pos["entry_time"],
        "entry_price": entry_price,
        "exit_time": exit_date,
        "exit_price": round(sell_price, 2),
        "quantity": qty,
        "pnl": round(pnl - fee, 2),
        "pnl_pct": round((sell_price / entry_price - 1) * 100, 2),
        "exit_reason": reason,
    })
    del positions[code]
    return balance


def _calc_summary(trades: List[Dict], initial: float, final_balance: float, days: int) -> Dict:
    """计算回测统计"""
    if not trades:
        return {
            "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
            "total_return_pct": 0, "annualized_return_pct": 0,
            "max_drawdown_pct": 0, "profit_factor": 0, "sharpe_ratio": 0,
            "max_consecutive_losses": 0, "avg_pnl": 0, "avg_win": 0,
            "avg_loss": 0, "final_balance": round(final_balance, 2),
        }
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_return = (final_balance / initial - 1) * 100
    years = max(days / 365, 0.01)
    annualized = ((final_balance / initial) ** (1 / years) - 1) * 100

    max_dd, peak, running = 0, initial, initial
    for p in pnls:
        running += p
        if running > peak:
            peak = running
        dd = (peak - running) / peak * 100
        if dd > max_dd:
            max_dd = dd

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else 999

    if len(pnls) > 1:
        returns = np.array(pnls) / initial
        sharpe = (np.mean(returns) / np.std(returns)) * math.sqrt(252) if np.std(returns) > 0 else 0
    else:
        sharpe = 0

    max_consec, cur = 0, 0
    for p in pnls:
        if p <= 0:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0

    return {
        "total_trades": len(trades), "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(annualized, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": round(pf, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_consecutive_losses": max_consec,
        "avg_pnl": round(sum(pnls) / len(pnls), 2),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
        "final_balance": round(final_balance, 2),
    }
