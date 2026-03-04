"""
数字货币策略历史回测引擎
复用 crypto_trader 的信号逻辑，用历史K线逐根模拟交易
异步执行 + 进度轮询，与 screener 模式一致
"""

import threading
import math
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from services.binance_client import BinanceClient
from services import database as db
from services import signal_engine as sig

logger = logging.getLogger(__name__)

# 全局回测状态（同时只跑一个回测）
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

FEE_RATE = 0.001


def start_backtest(params: dict) -> str:
    """启动回测任务（后台线程），返回 run_id"""
    with _bt_lock:
        if _bt_state["status"] == "running":
            return _bt_state["run_id"]

        run_id = uuid.uuid4().hex[:12]
        _bt_state.update({
            "status": "running",
            "run_id": run_id,
            "progress": 0,
            "total": 0,
            "message": "初始化回测...",
            "summary": {},
            "equity": [],
            "trades": [],
        })

    db.save_backtest_run(run_id, params, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    t = threading.Thread(target=_run_backtest, args=(run_id, params), daemon=True)
    t.start()
    return run_id


def get_backtest_status() -> dict:
    with _bt_lock:
        return dict(_bt_state)


def _update(key, value):
    with _bt_lock:
        _bt_state[key] = value


def _update_multi(**kw):
    with _bt_lock:
        _bt_state.update(kw)


# ==================================================================
# 回测主流程
# ==================================================================

def _run_backtest(run_id: str, params: dict):
    try:
        symbols = params.get("symbols", [])
        initial_capital = float(params.get("initial_capital", 10000))
        drop_pct = float(params.get("drop_pct", 15)) / 100.0
        stop_loss_pct = float(params.get("stop_loss_pct", 5)) / 100.0
        max_pos_pct = float(params.get("max_position_pct", 10)) / 100.0
        max_positions = int(params.get("max_positions", 5))
        interval = params.get("interval", "4h")
        days = int(params.get("days", 180))

        client = BinanceClient()

        if not symbols:
            _update("message", "获取 TOP20 币种...")
            try:
                symbols = client.get_top_symbols(20)
            except Exception as e:
                _update_multi(status="error", message=f"获取币种失败: {e}")
                return

        total_symbols = len(symbols)
        _update_multi(total=total_symbols, message=f"开始回测 {total_symbols} 个币种...")

        end_ms = int(datetime.now().timestamp() * 1000)
        start_ms = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        all_klines: Dict[str, pd.DataFrame] = {}
        for i, symbol in enumerate(symbols):
            _update_multi(progress=i, message=f"拉取K线 ({i+1}/{total_symbols}): {symbol}")
            try:
                raw = client.get_klines(symbol, interval, 1000,
                                        start_time=start_ms, end_time=end_ms)
                if raw and len(raw) > 30:
                    df = pd.DataFrame(raw, columns=[
                        "open_time", "open", "high", "low", "close", "volume",
                        "close_time", "qv", "trades", "tbb", "tbq", "ignore",
                    ])
                    for col in ["open", "high", "low", "close", "volume"]:
                        df[col] = df[col].astype(float)
                    df["date"] = pd.to_datetime(df["open_time"], unit="ms")
                    all_klines[symbol] = df
            except Exception as e:
                logger.debug("拉取 %s K线失败: %s", symbol, e)

        if not all_klines:
            _update_multi(status="error", message="无有效K线数据")
            return

        use_atr_stop = params.get("use_atr_stop", True)
        use_trailing = params.get("use_trailing", True)
        use_exit_reversal = params.get("use_exit_reversal", True)
        min_platform_candles = params.get("min_platform_candles", 20)
        use_platform = params.get("use_platform_bottom", True)
        use_probe = params.get("use_probe_confirm", True)

        _update("message", "逐根K线模拟交易...")

        all_dates = set()
        for df in all_klines.values():
            all_dates.update(df["open_time"].tolist())
        timeline = sorted(all_dates)

        balance = initial_capital
        positions: Dict[str, dict] = {}
        closed_trades: List[Dict] = []
        equity_curve: List[Dict] = []
        total_bars = len(timeline)

        for bar_idx, ts in enumerate(timeline):
            if bar_idx % max(1, total_bars // 50) == 0:
                pct = int(bar_idx / total_bars * 100)
                _update_multi(progress=pct, message=f"模拟中... {pct}%")

            date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")

            # 1) 检查止损止盈
            for sym in list(positions.keys()):
                if sym not in all_klines:
                    continue
                kdf = all_klines[sym]
                bar = kdf[kdf["open_time"] == ts]
                if bar.empty:
                    continue
                high = bar.iloc[0]["high"]
                low = bar.iloc[0]["low"]
                close = bar.iloc[0]["close"]
                pos = positions[sym]
                entry_price = pos["entry_price"]

                # 更新最高价追踪
                if close > pos.get("highest_price", entry_price):
                    pos["highest_price"] = close

                atr_val = pos.get("atr", 0)

                # 出场反转信号（十字星+放量 / 长上影+放量 at 前高 / 上涨幅度收窄+压力）
                if use_exit_reversal:
                    hist = kdf[kdf["open_time"] <= ts].tail(25)
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
                            sell_price = close
                            fee = sell_price * pos["quantity"] * FEE_RATE
                            pnl = (sell_price - entry_price) * pos["quantity"]
                            balance += sell_price * pos["quantity"] - fee
                            closed_trades.append({
                                "symbol": sym, "side": "ROUND",
                                "entry_time": pos["entry_time"], "entry_price": entry_price,
                                "exit_time": date_str, "exit_price": round(sell_price, 6),
                                "quantity": pos["quantity"],
                                "pnl": round(pnl - fee, 2),
                                "pnl_pct": round((sell_price / entry_price - 1) * 100, 2),
                                "exit_reason": reason,
                            })
                            del positions[sym]
                            continue

                # ATR 动态止损 或 固定百分比止损
                if use_atr_stop and atr_val > 0:
                    stop_price = entry_price - 2 * atr_val
                else:
                    stop_price = entry_price * (1 - stop_loss_pct)

                # 移动止损（盈利后上移）
                if use_trailing and atr_val > 0:
                    pnl_atr = (close - entry_price) / atr_val if atr_val > 0 else 0
                    if pnl_atr >= 2:
                        trailing = pos.get("highest_price", entry_price) - 1.5 * atr_val
                        stop_price = max(stop_price, trailing)
                    elif pnl_atr >= 1:
                        stop_price = max(stop_price, entry_price)

                if low <= stop_price:
                    sell_price = max(stop_price, low)
                    pnl = (sell_price - entry_price) * pos["quantity"]
                    fee = sell_price * pos["quantity"] * FEE_RATE
                    balance += sell_price * pos["quantity"] - fee
                    reason = "ATR止损" if use_atr_stop and atr_val > 0 else "止损"
                    if use_trailing and sell_price > entry_price:
                        reason = "移动止损"
                    closed_trades.append({
                        "symbol": sym, "side": "ROUND",
                        "entry_time": pos["entry_time"], "entry_price": entry_price,
                        "exit_time": date_str, "exit_price": round(sell_price, 6),
                        "quantity": pos["quantity"],
                        "pnl": round(pnl - fee, 2),
                        "pnl_pct": round((sell_price / entry_price - 1) * 100, 2),
                        "exit_reason": reason,
                    })
                    del positions[sym]
                    continue

            # 2) 扫描入场信号（完整版，与实盘对齐）
            if len(positions) < max_positions:
                for sym, kdf in all_klines.items():
                    if sym in positions:
                        continue
                    if len(positions) >= max_positions:
                        break
                    idx_mask = kdf["open_time"] <= ts
                    window = kdf[idx_mask]
                    if len(window) < 30:
                        continue

                    signal = _analyze_entry_full(
                        window, drop_pct,
                        min_platform_candles=min_platform_candles,
                        use_platform=use_platform,
                        use_probe=use_probe,
                    )
                    if signal:
                        price = window.iloc[-1]["close"]
                        order_amount = min(balance * max_pos_pct, balance)
                        if order_amount < 10:
                            continue
                        qty = order_amount / price
                        fee = order_amount * FEE_RATE
                        balance -= (order_amount + fee)
                        positions[sym] = {
                            "entry_price": price,
                            "quantity": qty,
                            "entry_time": date_str,
                            "highest_price": price,
                            "atr": signal.get("atr", 0),
                        }

            # 3) 记录资金曲线
            unrealized = 0.0
            for sym, pos in positions.items():
                kdf = all_klines[sym]
                bar = kdf[kdf["open_time"] == ts]
                if not bar.empty:
                    cur_price = bar.iloc[0]["close"]
                    unrealized += (cur_price - pos["entry_price"]) * pos["quantity"]

            if bar_idx % max(1, total_bars // 200) == 0 or bar_idx == total_bars - 1:
                equity_curve.append({
                    "date": date_str,
                    "equity": round(balance + unrealized, 2),
                    "balance": round(balance, 2),
                })

        # 收尾：强平所有持仓
        for sym, pos in list(positions.items()):
            kdf = all_klines[sym]
            if kdf.empty:
                continue
            last_close = kdf.iloc[-1]["close"]
            last_date = datetime.fromtimestamp(
                kdf.iloc[-1]["open_time"] / 1000
            ).strftime("%Y-%m-%d %H:%M")
            fee = last_close * pos["quantity"] * FEE_RATE
            pnl = (last_close - pos["entry_price"]) * pos["quantity"] - fee
            balance += last_close * pos["quantity"] - fee
            closed_trades.append({
                "symbol": sym, "side": "ROUND",
                "entry_time": pos["entry_time"], "entry_price": pos["entry_price"],
                "exit_time": last_date, "exit_price": last_close,
                "quantity": pos["quantity"],
                "pnl": round(pnl, 2),
                "pnl_pct": round((last_close / pos["entry_price"] - 1) * 100, 2),
                "exit_reason": "回测结束",
            })

        summary = _calc_summary(closed_trades, initial_capital, balance, days)

        db.save_backtest_trades(run_id, closed_trades)
        db.update_backtest_run(
            run_id, "done", summary, equity_curve,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        _update_multi(
            status="done",
            progress=100,
            message=f"回测完成! {len(closed_trades)} 笔交易",
            summary=summary,
            equity=equity_curve,
            trades=closed_trades,
        )
        logger.info("回测 %s 完成: %d 笔交易, 总收益 %.2f%%",
                     run_id, len(closed_trades), summary.get("total_return_pct", 0))

    except Exception as e:
        logger.error("回测异常: %s", e, exc_info=True)
        _update_multi(status="error", message=f"回测失败: {e}")
        db.update_backtest_run(
            run_id, "error", {"error": str(e)}, [],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )


# ==================================================================
# 信号判断（v3 与实盘 _analyze_signal 完全对齐：平台底部 + 下探收涨）
# ==================================================================

def _analyze_entry_full(
    window: pd.DataFrame,
    drop_threshold: float,
    min_platform_candles: int = 20,
    use_platform: bool = True,
    use_probe: bool = True,
) -> Optional[Dict]:
    """
    完整入场信号分析 v3，与 crypto_trader._analyze_signal 对齐
    平台底部 + 下探收涨 + score_crypto_signal_v3
    """
    closes = window["close"].values
    highs = window["high"].values
    lows = window["low"].values
    volumes = window["volume"].values
    opens = window["open"].values

    platform_info = {"platform_days": 0, "drop_from_high": 0, "score": 0, "tag": ""}
    if use_platform:
        has_platform, platform_info = sig.check_platform_bottom(
            closes, lows, highs, min_platform_days=min_platform_candles
        )
        if not has_platform:
            high_60d = max(highs[-60:]) if len(highs) >= 60 else max(highs)
            drop_pct = (high_60d - closes[-1]) / high_60d
            if drop_pct < drop_threshold:
                return None
            platform_info = {
                "platform_days": 0,
                "drop_from_high": round(drop_pct * 100, 1),
                "score": 0,
                "tag": "",
            }
    else:
        high_period = max(highs[-60:]) if len(highs) >= 60 else max(highs)
        drop_pct = (high_period - closes[-1]) / high_period
        if drop_pct < drop_threshold:
            return None
        platform_info = {
            "platform_days": 0,
            "drop_from_high": round(drop_pct * 100, 1),
            "score": min(drop_pct / 0.4 * 10, 20),
            "tag": "",
        }

    probe_score, probe_tags = sig.check_probe_and_close_up(
        opens, closes, highs, lows, volumes
    )
    if use_probe and probe_score < 8:
        if platform_info.get("score", 0) < 12:
            return None

    stabilized, stab_confidence = sig.check_stabilized(closes, lows, highs, volumes)
    vol_spike, vol_ratio = sig.check_volume_spike(volumes)
    if not vol_spike and vol_ratio < 1.5:
        return None

    ma_score, ma_tags = sig.check_ma_support_crypto(closes)
    pattern_score, pattern_name = sig.check_kline_pattern(opens, closes, highs, lows)
    atr = sig.calculate_atr(highs, lows, closes, 14)

    result = sig.score_crypto_signal_v3(
        opens, closes, highs, lows, volumes,
        platform_info=platform_info,
        probe_score=probe_score,
        probe_tags=probe_tags,
        stab_confidence=stab_confidence,
        vol_ratio=vol_ratio,
        ma_score=ma_score,
        ma_tags=ma_tags,
        pattern_score=pattern_score,
        pattern_name=pattern_name,
        btc_score=0,
        htf_score=0,
        min_score=40,
    )

    if result is None:
        return None

    result["atr"] = atr
    return result


# ==================================================================
# 统计指标计算
# ==================================================================

def _calc_summary(trades: List[Dict], initial: float, final_balance: float,
                  days: int) -> Dict:
    if not trades:
        return {
            "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
            "total_return_pct": 0, "annualized_return_pct": 0,
            "max_drawdown_pct": 0, "profit_factor": 0, "sharpe_ratio": 0,
            "max_consecutive_losses": 0, "avg_pnl": 0, "avg_win": 0,
            "avg_loss": 0, "final_balance": round(final_balance, 2),
        }

    round_trades = [t for t in trades if t["side"] == "ROUND"]
    pnls = [t["pnl"] for t in round_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_return = (final_balance / initial - 1) * 100
    years = max(days / 365, 0.01)
    annualized = ((final_balance / initial) ** (1 / years) - 1) * 100

    # 最大回撤（从 pnl 序列）
    max_dd = 0
    peak = initial
    running = initial
    for p in pnls:
        running += p
        if running > peak:
            peak = running
        dd = (peak - running) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # 盈亏比
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else 999

    # 夏普比率（简化）
    if len(pnls) > 1:
        returns = np.array(pnls) / initial
        sharpe = (np.mean(returns) / np.std(returns)) * math.sqrt(252) if np.std(returns) > 0 else 0
    else:
        sharpe = 0

    # 最大连亏
    max_consec = 0
    cur_consec = 0
    for p in pnls:
        if p <= 0:
            cur_consec += 1
            max_consec = max(max_consec, cur_consec)
        else:
            cur_consec = 0

    return {
        "total_trades": len(round_trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(round_trades) * 100, 1) if round_trades else 0,
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(annualized, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": round(pf, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_consecutive_losses": max_consec,
        "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
        "final_balance": round(final_balance, 2),
    }
