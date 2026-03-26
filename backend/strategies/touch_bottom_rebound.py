"""
触底反弹策略（与同花顺条件选股逻辑对齐）
条件：
1. 行情收盘价低位且行情收盘价上移
2. 近3个交易日的区间涨跌幅>0%且<=5%
3. 涨跌幅>0%

数据获取复用参数选股的 screener 模块，保证数据源一致。
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import pandas as pd

from services.screener import fetch_snapshot_for_strategies, fetch_kline_for_strategies

NAME = "触底反弹"

logger = logging.getLogger(__name__)

# 低位定义：与同花顺一致。收盘价处于近N日【收盘价】序列的较低位置（行情收盘价低位）
LOOKBACK_DAYS = 20  # 与同花顺短期选股一致
LOW_PERCENTILE = 0.50  # 处于收盘价序列下 50% 视为低位

# 请求间隔，避免被限流
_REQUEST_INTERVAL = 0.35

# 同花顺结果校验：策略应能筛出这些股票
VERIFY_CODES = frozenset({"300482", "920187", "920626"})


def _append_today_if_needed(
    kline: pd.DataFrame, code: str, snap_row: pd.Series
) -> pd.DataFrame:
    """若K线最后一条非今日，用快照补充当日数据（与同花顺实时一致）"""
    if kline is None or kline.empty:
        return kline
    today_str = datetime.now().strftime("%Y-%m-%d")
    last_date = kline["date"].iloc[-1]
    if last_date >= today_str:
        return kline
    # 仅交易日内补充
    if datetime.now().weekday() >= 5:
        return kline
    new_row = pd.DataFrame([{
        "date": today_str,
        "open": float(snap_row.get("open", snap_row["close"])),
        "close": float(snap_row["close"]),
        "high": float(snap_row.get("high", snap_row["close"])),
        "low": float(snap_row.get("low", snap_row["close"])),
        "volume": 0,
    }])
    return pd.concat([kline, new_row], ignore_index=True)


def _check_conditions(
    df: pd.DataFrame, change_pct_today: float, code: str = ""
) -> Tuple[bool, str]:
    """
    检查触底反弹三条件（与同花顺逻辑对齐）
    """
    if df is None or len(df) < 4:
        if code in VERIFY_CODES:
            logger.info("[%s] 条件: K线不足(需至少4根)", code)
        return False, ""

    closes = df["close"].values

    # 条件3：涨跌幅>0%
    if change_pct_today <= 0:
        if code in VERIFY_CODES:
            logger.info("[%s] 条件: 涨跌幅=%.2f%% 不>0", code, change_pct_today)
        return False, ""

    # 条件2：近3个交易日区间涨跌幅 >0% 且 <=5%
    if len(closes) < 4:
        if code in VERIFY_CODES:
            logger.info("[%s] 条件: K线不足4根", code)
        return False, ""
    change_3d = (closes[-1] / closes[-4] - 1) * 100
    if change_3d <= 0 or change_3d > 5:
        if code in VERIFY_CODES:
            logger.info("[%s] 条件: 3日涨跌幅=%.2f%% 不在(0,5]", code, change_3d)
        return False, ""

    # 条件1：行情收盘价低位且行情收盘价上移
    n = min(LOOKBACK_DAYS, len(closes))
    close_min = min(closes[-n:])
    close_max = max(closes[-n:])
    if close_max <= close_min:
        if code in VERIFY_CODES:
            logger.info("[%s] 条件: 收盘价无波动", code)
        return False, ""
    position = (closes[-1] - close_min) / (close_max - close_min)
    at_low = position < LOW_PERCENTILE
    moving_up = closes[-1] > closes[-2]
    if not (at_low and moving_up):
        if code in VERIFY_CODES:
            logger.info(
                "[%s] 条件: 低位=%s(位置%.2f) 上移=%s",
                code, at_low, position, moving_up,
            )
        return False, ""

    reason = f"低位上移；3日涨{change_3d:.1f}%；今日涨{change_pct_today:.1f}%"
    return True, reason


def run() -> List[Dict]:
    """
    触底反弹选股：满足三条件的股票列表
    数据获取复用参数选股的 screener 模块
    """
    snapshot = fetch_snapshot_for_strategies()
    if snapshot is None or snapshot.empty:
        return []

    # 预筛：涨跌幅>0%
    candidates = snapshot[snapshot["change_pct"] > 0]
    if candidates.empty:
        return []

    results = []
    for i, (_, row) in enumerate(candidates.iterrows()):
        code = str(row["code"]).zfill(6)
        name = str(row["name"]).strip()
        # 排除 ST、退市、新股
        if "ST" in name or "退" in name or name.startswith("N") or name.startswith("C"):
            continue

        if i > 0:
            time.sleep(_REQUEST_INTERVAL)
        kline = fetch_kline_for_strategies(code, days=90)
        if kline is not None and len(kline) >= 4:
            kline = _append_today_if_needed(kline, code, row)
        ok, reason = _check_conditions(
            kline, float(row["change_pct"]), code=code
        )
        if ok:
            score = min(80 + float(row["change_pct"]), 100)  # 根据当日涨幅给分
            results.append({
                "stock_code": code,
                "stock_name": name,
                "score": round(score, 1),
                "drop_pct": 0,
                "volume_ratio": 0,
                "reason": reason,
                "tags": ["触底反弹", "低位上移"],
            })

    # 按 score 降序
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
