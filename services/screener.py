"""
弹簧反弹选股引擎
基于价格行为学理论：大幅下跌后企稳 + 量能异变 + 大盘参考
两阶段筛选：快速快照过滤 → 逐股K线详细分析
"""

import threading
import time
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ============================
# 全局筛选任务状态
# ============================
_task_lock = threading.Lock()
_task_state: Dict = {
    "status": "idle",       # idle / running / done / error
    "task_id": None,
    "progress": 0,
    "total": 0,
    "found": 0,
    "message": "",
    "results": [],
    "index_info": {},
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}

# ============================
# 公共接口
# ============================

def start_screening(params: dict) -> str:
    """启动筛选任务（后台线程），返回 task_id"""
    with _task_lock:
        if _task_state["status"] == "running":
            return _task_state["task_id"]

        task_id = uuid.uuid4().hex[:12]
        _task_state.update({
            "status": "running",
            "task_id": task_id,
            "progress": 0,
            "total": 0,
            "found": 0,
            "message": "正在获取全A股数据...",
            "results": [],
            "index_info": {},
        })

    t = threading.Thread(target=_run_screening, args=(task_id, params), daemon=True)
    t.start()
    return task_id


def get_screening_status() -> dict:
    """获取当前筛选任务状态"""
    with _task_lock:
        return dict(_task_state)


def fetch_index_info() -> dict:
    """获取大盘指数信息（上证+深证）供前端显示"""
    try:
        return _fetch_index_snapshot()
    except Exception as e:
        logger.warning("获取大盘指数失败: %s", e)
        return {}


# ============================
# 筛选主流程（后台线程）
# ============================

def _run_screening(task_id: str, params: dict):
    """后台线程执行筛选"""
    drop_pct_threshold = params.get("drop_pct", 25) / 100.0
    volume_ratio_threshold = params.get("volume_ratio", 1.5)

    try:
        # --- 获取大盘指数 ---
        _update("message", "正在获取大盘指数...")
        index_info = _fetch_index_snapshot()
        _update("index_info", index_info)

        sh_change = index_info.get("sh_change_pct", 0)
        if sh_change < -3:
            _update_multi(status="done", message=f"大盘暴跌 {sh_change}%，今日不宜筛选", results=[])
            return

        index_kline = _fetch_index_kline()

        # --- Stage 1: 批量获取全A股快照 ---
        _update("message", "正在获取全A股实时数据（约5000+只）...")
        snapshot_df = _fetch_all_stocks_snapshot()
        if snapshot_df is None or snapshot_df.empty:
            _update_multi(status="error", message="获取A股数据失败")
            return

        logger.info("获取到 %d 只A股数据", len(snapshot_df))

        # 排除 ST / 停牌 / 新股
        candidates = snapshot_df[
            (~snapshot_df["name"].str.contains("ST|退", na=False)) &
            (snapshot_df["volume"] > 0) &
            (snapshot_df["total_mv"] > 0)
        ].copy()

        # 初步过滤：量比 > 阈值
        candidates = candidates[candidates["volume_ratio"] >= volume_ratio_threshold]
        logger.info("初步过滤后 %d 只候选股", len(candidates))

        if candidates.empty:
            _update_multi(status="done", message="没有符合量比条件的股票", results=[])
            return

        # --- Stage 2: 逐股详细分析 ---
        total = len(candidates)
        _update_multi(total=total, message=f"正在逐股分析 {total} 只候选股...")

        results = []
        for i, (_, row) in enumerate(candidates.iterrows()):
            if _task_state.get("task_id") != task_id:
                return  # 被新任务取代

            code = str(row["code"]).zfill(6)
            _update_multi(progress=i + 1, message=f"分析中 ({i+1}/{total}): {code} {row['name']}")

            try:
                result = _analyze_candidate(
                    code, row["name"], row,
                    index_kline, drop_pct_threshold, volume_ratio_threshold,
                )
                if result:
                    results.append(result)
                    _update("found", len(results))
            except Exception as e:
                logger.debug("分析 %s 失败: %s", code, e)

            time.sleep(0.3)

        results.sort(key=lambda x: x["score"], reverse=True)
        _update_multi(
            status="done",
            progress=total,
            results=results,
            message=f"筛选完成！从 {total} 只候选股中筛出 {len(results)} 只"
        )
        logger.info("筛选完成: %d 只符合条件", len(results))

    except Exception as e:
        logger.error("筛选异常: %s", e, exc_info=True)
        _update_multi(status="error", message=f"筛选失败: {str(e)}")


# ============================
# Stage 1: 批量获取全A股快照
# ============================

def _fetch_all_stocks_snapshot() -> Optional[pd.DataFrame]:
    """
    调用东方财富行情接口，一次性获取全部 A 股实时数据
    返回 DataFrame 包含: code, name, close, change_pct, volume, volume_ratio, total_mv
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    all_rows = []

    for fs_code in ["m:0+t:6,m:0+t:80", "m:1+t:2,m:1+t:23"]:
        page = 1
        while True:
            params = {
                "pn": page,
                "pz": 5000,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": fs_code,
                "fields": "f2,f3,f5,f6,f8,f10,f12,f14,f15,f16,f17,f20",
            }
            try:
                resp = requests.get(url, params=params, headers=_HEADERS, timeout=20)
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data", {}).get("diff", [])
                if not items:
                    break
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    close = item.get("f2", "-")
                    if close == "-" or close is None:
                        continue
                    all_rows.append({
                        "code": str(item.get("f12", "")),
                        "name": item.get("f14", ""),
                        "close": float(close) if close != "-" else 0,
                        "change_pct": float(item.get("f3", 0) or 0),
                        "volume": float(item.get("f5", 0) or 0),
                        "amount": float(item.get("f6", 0) or 0),
                        "turnover": float(item.get("f8", 0) or 0),
                        "volume_ratio": float(item.get("f10", 0) or 0),
                        "high": float(item.get("f15", 0) or 0),
                        "low": float(item.get("f16", 0) or 0),
                        "open": float(item.get("f17", 0) or 0),
                        "total_mv": float(item.get("f20", 0) or 0),
                    })
                total_count = data.get("data", {}).get("total", 0)
                if page * 5000 >= total_count:
                    break
                page += 1
            except Exception as e:
                logger.warning("获取股票列表失败 (fs=%s, page=%d): %s", fs_code, page, e)
                break

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)


# ============================
# Stage 2: 逐股详细分析
# ============================

def _analyze_candidate(
    code: str,
    name: str,
    snapshot_row: pd.Series,
    index_kline: Optional[pd.DataFrame],
    drop_threshold: float,
    vol_ratio_threshold: float,
) -> Optional[Dict]:
    """
    对单只股票进行详细技术分析
    返回评分结果 dict 或 None（不符合条件）
    """
    kline_df = _fetch_stock_kline(code, days=90)
    if kline_df is None or len(kline_df) < 30:
        return None

    closes = kline_df["close"].values
    highs = kline_df["high"].values
    lows = kline_df["low"].values
    volumes = kline_df["volume"].values

    high_60d = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    current_close = closes[-1]

    # --- 条件1: 跌幅达标 ---
    drop_pct = (high_60d - current_close) / high_60d
    if drop_pct < drop_threshold:
        return None

    # --- 条件2: 企稳信号（最近5日不再创新低）---
    if len(lows) >= 25:
        recent_5d_low = min(lows[-5:])
        prev_20d_low = min(lows[-25:-5])
        stabilized = recent_5d_low >= prev_20d_low * 0.99
    else:
        stabilized = True

    if not stabilized:
        return None

    # --- 条件3: 量能异变（最近3日有放量）---
    if len(volumes) >= 23:
        avg_vol_20 = volumes[-23:-3].mean()
        recent_3d_vols = volumes[-3:]
        vol_spike = any(v > avg_vol_20 * 2 for v in recent_3d_vols) if avg_vol_20 > 0 else False
    else:
        vol_spike = snapshot_row.get("volume_ratio", 0) >= vol_ratio_threshold

    if not vol_spike:
        return None

    # --- 评分 ---
    score = 0.0

    # 跌幅越大，弹性越大（25~50%映射到20~40分）
    score += min(drop_pct * 80, 40)

    # 量比越高，异动越强（1.5~5映射到10~30分）
    vr = snapshot_row.get("volume_ratio", 0)
    score += min(max((vr - 1) * 10, 0), 30)

    # 企稳程度：最近5日振幅收窄加分
    if len(highs) >= 5:
        recent_range = (max(highs[-5:]) - min(lows[-5:])) / current_close
        if recent_range < 0.10:
            score += 15
        elif recent_range < 0.15:
            score += 10

    # 大盘加分：大盘弱而个股不跌加分
    if index_kline is not None and len(index_kline) > 0:
        idx_change = index_kline["close"].iloc[-1] / index_kline["close"].iloc[-2] - 1 \
            if len(index_kline) >= 2 else 0
        stock_change = snapshot_row.get("change_pct", 0) / 100.0
        if idx_change < 0 and stock_change > idx_change:
            score += 15

    score = round(min(score, 100), 1)

    max_vol_3d = max(volumes[-3:]) if len(volumes) >= 3 else 0
    avg_vol_20_val = volumes[-23:-3].mean() if len(volumes) >= 23 else 0
    actual_vol_ratio = round(max_vol_3d / avg_vol_20_val, 2) if avg_vol_20_val > 0 else vr

    reasons = []
    reasons.append(f"60日高点回落{drop_pct*100:.1f}%")
    reasons.append(f"近期企稳不创新低")
    reasons.append(f"量比{actual_vol_ratio}")

    return {
        "stock_code": code,
        "stock_name": name,
        "score": score,
        "drop_pct": round(drop_pct * 100, 1),
        "volume_ratio": actual_vol_ratio,
        "close": current_close,
        "change_pct": snapshot_row.get("change_pct", 0),
        "reason": "；".join(reasons),
    }


# ============================
# 数据获取辅助函数
# ============================

def _fetch_stock_kline(code: str, days: int = 90) -> Optional[pd.DataFrame]:
    """获取单只股票近N天K线"""
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    end_str = datetime.now().strftime("%Y%m%d")
    start_str = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": start_str,
        "end": end_str,
        "ut": "7eea3edcaed734bea9004fcfb7d7c8c5",
    }
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        klines = data.get("data", {}).get("klines", [])
        if not klines:
            return None

        rows = []
        for line in klines:
            parts = line.split(",")
            rows.append({
                "date": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": float(parts[5]),
            })
        return pd.DataFrame(rows)
    except Exception as e:
        logger.debug("获取 %s K线失败: %s", code, e)
        return None


def _fetch_index_snapshot() -> dict:
    """获取上证指数和深证成指实时快照"""
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    params = {
        "fltt": 2,
        "fields": "f2,f3,f4,f12,f14",
        "secids": "1.000001,0.399001",
    }
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("diff", [])

        result = {}
        for item in items:
            code = item.get("f12", "")
            if code == "000001":
                result["sh_name"] = "上证指数"
                result["sh_close"] = item.get("f2", 0)
                result["sh_change_pct"] = item.get("f3", 0)
                result["sh_change"] = item.get("f4", 0)
            elif code == "399001":
                result["sz_name"] = "深证成指"
                result["sz_close"] = item.get("f2", 0)
                result["sz_change_pct"] = item.get("f3", 0)
                result["sz_change"] = item.get("f4", 0)
        return result
    except Exception as e:
        logger.warning("获取指数快照失败: %s", e)
        return {}


def _fetch_index_kline() -> Optional[pd.DataFrame]:
    """获取上证指数近30日K线"""
    return _fetch_stock_kline_by_secid("1.000001", days=30)


def _fetch_stock_kline_by_secid(secid: str, days: int = 30) -> Optional[pd.DataFrame]:
    """按 secid 获取K线"""
    end_str = datetime.now().strftime("%Y%m%d")
    start_str = (datetime.now() - timedelta(days=days + 10)).strftime("%Y%m%d")

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": start_str,
        "end": end_str,
        "ut": "7eea3edcaed734bea9004fcfb7d7c8c5",
    }
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        klines = data.get("data", {}).get("klines", [])
        if not klines:
            return None
        rows = []
        for line in klines:
            parts = line.split(",")
            rows.append({
                "date": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": float(parts[5]),
            })
        return pd.DataFrame(rows)
    except Exception as e:
        logger.debug("获取指数K线失败: %s", e)
        return None


# ============================
# 状态更新辅助
# ============================

def _update(key: str, value):
    with _task_lock:
        _task_state[key] = value


def _update_multi(**kwargs):
    with _task_lock:
        _task_state.update(kwargs)
