"""
弹簧反弹选股引擎 v2
基于价格行为学理论：大幅下跌后企稳 + 量能异变 + 均线支撑 + K线形态 + 大盘参考
两阶段筛选：快速快照过滤 → 逐股K线多维度分析 → 加权评分排序
"""

import threading
import time
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

import numpy as np
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
    min_turnover = params.get("min_turnover", 1.0)
    mv_range = params.get("mv_range", "all")
    ma_filter = params.get("ma_filter", "none")

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
        market_score, market_env = _evaluate_market_env(index_kline)

        # --- Stage 1: 批量获取全A股快照 ---
        _update("message", "正在获取全A股实时数据（约5000+只）...")
        snapshot_df = _fetch_all_stocks_snapshot()
        if snapshot_df is None or snapshot_df.empty:
            _update_multi(status="error", message="获取A股数据失败")
            return

        logger.info("获取到 %d 只A股数据", len(snapshot_df))

        # 增强过滤：排除 ST/退市/新股/注册制首日/停牌/涨跌停/微盘股
        candidates = snapshot_df[
            (~snapshot_df["name"].str.contains("ST|退|N|C", na=False)) &
            (snapshot_df["volume"] > 0) &
            (snapshot_df["turnover"] >= min_turnover) &
            (snapshot_df["change_pct"] > -9.5) &
            (snapshot_df["change_pct"] < 9.5) &
            (snapshot_df["total_mv"] > 2e9)
        ].copy()

        # 市值范围过滤
        if mv_range == "small":
            candidates = candidates[(candidates["total_mv"] >= 2e9) & (candidates["total_mv"] <= 100e9)]
        elif mv_range == "mid":
            candidates = candidates[(candidates["total_mv"] > 100e9) & (candidates["total_mv"] <= 500e9)]
        elif mv_range == "all":
            candidates = candidates[candidates["total_mv"] <= 500e9]

        # 量比过滤
        candidates = candidates[candidates["volume_ratio"] >= volume_ratio_threshold]
        logger.info("Stage 1 过滤后 %d 只候选股", len(candidates))

        if candidates.empty:
            _update_multi(status="done", message="没有符合初步条件的股票", results=[])
            return

        # --- Stage 2: 逐股详细分析 ---
        total = len(candidates)
        _update_multi(total=total, message=f"正在逐股分析 {total} 只候选股...")

        results = []
        for i, (_, row) in enumerate(candidates.iterrows()):
            if _task_state.get("task_id") != task_id:
                return

            code = str(row["code"]).zfill(6)
            _update_multi(progress=i + 1, message=f"分析中 ({i+1}/{total}): {code} {row['name']}")

            try:
                result = _analyze_candidate(
                    code, row["name"], row,
                    index_kline, market_score, market_env,
                    drop_pct_threshold, ma_filter,
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
# Stage 2: 逐股多维度分析
# ============================

def _analyze_candidate(
    code: str,
    name: str,
    snapshot_row: pd.Series,
    index_kline: Optional[pd.DataFrame],
    market_score: float,
    market_env: str,
    drop_threshold: float,
    ma_filter: str,
) -> Optional[Dict]:
    """
    对单只股票进行多维度技术分析
    评分维度：跌幅深度(25) + 企稳质量(20) + 量能异变(20) + 均线位置(15) + K线形态(10) + 大盘环境(10)
    """
    kline_df = _fetch_stock_kline(code, days=90)
    if kline_df is None or len(kline_df) < 30:
        return None

    opens = kline_df["open"].values
    closes = kline_df["close"].values
    highs = kline_df["high"].values
    lows = kline_df["low"].values
    volumes = kline_df["volume"].values

    high_60d = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    current_close = closes[-1]

    # ===== 硬性条件（不满足直接排除）=====

    # 条件1: 跌幅达标
    drop_pct = (high_60d - current_close) / high_60d
    if drop_pct < drop_threshold:
        return None

    # 条件2: 企稳信号（多维度确认）
    stabilized, stab_confidence = _check_stabilized(closes, lows, highs, volumes)
    if not stabilized:
        return None

    # 条件3: 量能异变
    vol_spike, vol_ratio_actual = _check_volume_spike(volumes, snapshot_row)
    if not vol_spike:
        return None

    # 条件4: 均线过滤（可选）
    ma_score, ma_tags = _check_ma_support(closes)
    if ma_filter == "ma5_turn" and "MA5拐头" not in ma_tags:
        return None
    if ma_filter == "golden_cross" and "金叉" not in ma_tags:
        return None

    # ===== 多维度加权评分 =====

    score = 0.0
    reasons = []
    tags = []

    # 维度1: 跌幅深度（满分25）
    drop_score = min(drop_pct / 0.5 * 25, 25)
    score += drop_score
    reasons.append(f"60日高点回落{drop_pct*100:.1f}%")

    # 维度2: 企稳质量（满分20）
    stab_score = min(stab_confidence * 6.7, 20)
    score += stab_score
    reasons.append(f"企稳置信{stab_confidence}/3")

    # 维度3: 量能异变（满分20）
    vr = snapshot_row.get("volume_ratio", 0)
    vol_score = min(max((vol_ratio_actual - 1) * 8, 0), 20)
    score += vol_score
    reasons.append(f"量比{vol_ratio_actual}")

    # 维度4: 均线位置（满分15）
    ma_capped = min(ma_score, 15)
    score += ma_capped
    tags.extend(ma_tags)

    # 维度5: K线形态（满分10）
    pattern_score, pattern_name = _check_kline_pattern(opens, closes, highs, lows)
    pattern_capped = min(pattern_score, 10)
    score += pattern_capped
    if pattern_name:
        tags.append(pattern_name)
        reasons.append(pattern_name)

    # 维度6: 大盘环境（满分10）
    env_score = max(min(market_score, 10), -10)
    # 弱势中逆势的个股额外加分
    if market_env == "weak":
        stock_change = snapshot_row.get("change_pct", 0) / 100.0
        if stock_change > 0:
            env_score += 5
    score += env_score

    score = round(max(min(score, 100), 0), 1)

    return {
        "stock_code": code,
        "stock_name": name,
        "score": score,
        "drop_pct": round(drop_pct * 100, 1),
        "volume_ratio": vol_ratio_actual,
        "close": current_close,
        "change_pct": snapshot_row.get("change_pct", 0),
        "reason": "；".join(reasons),
        "tags": tags,
        "pattern": pattern_name,
        "ma_tags": ma_tags,
        "stab_confidence": stab_confidence,
        "market_env": market_env,
    }


# ============================
# 技术分析子模块
# ============================

def _check_stabilized(closes, lows, highs, volumes) -> Tuple[bool, int]:
    """
    多维度企稳确认
    返回 (是否企稳, 置信度0-3)
    必选条件：不创新低
    加分条件：下跌减速 / 振幅收窄 / 底部放量
    """
    if len(closes) < 25:
        return False, 0

    # (a) 不创新低：最近5日低点 >= 此前20日低点
    recent_5d_low = min(lows[-5:])
    prev_20d_low = min(lows[-25:-5])
    no_new_low = recent_5d_low >= prev_20d_low * 0.99

    if not no_new_low:
        return False, 0

    confidence = 0

    # (b) 下跌速度放缓：最近5日跌幅 < 此前5日跌幅
    if len(closes) >= 10:
        recent_5d_drop = (closes[-1] - closes[-5]) / closes[-5]
        prev_5d_drop = (closes[-5] - closes[-10]) / closes[-10]
        if recent_5d_drop > prev_5d_drop:
            confidence += 1

    # (c) 振幅收窄：最近5日振幅 < 此前10日振幅
    if len(highs) >= 15:
        recent_range = (max(highs[-5:]) - min(lows[-5:])) / closes[-1]
        prev_range = (max(highs[-15:-5]) - min(lows[-15:-5])) / closes[-5]
        if recent_range < prev_range:
            confidence += 1

    # (d) 底部放量：最近3日均量 > 此前10日均量的1.3倍
    if len(volumes) >= 13:
        recent_avg_vol = volumes[-3:].mean()
        prev_avg_vol = volumes[-13:-3].mean()
        if prev_avg_vol > 0 and recent_avg_vol > prev_avg_vol * 1.3:
            confidence += 1

    return confidence >= 1, confidence


def _check_volume_spike(volumes, snapshot_row) -> Tuple[bool, float]:
    """
    量能异变检测
    返回 (是否放量, 实际量比)
    """
    vr = snapshot_row.get("volume_ratio", 0)

    if len(volumes) >= 23:
        avg_vol_20 = volumes[-23:-3].mean()
        if avg_vol_20 > 0:
            max_vol_3d = max(volumes[-3:])
            actual_ratio = round(max_vol_3d / avg_vol_20, 2)
            return max_vol_3d > avg_vol_20 * 2, actual_ratio

    return vr >= 1.5, round(vr, 2)


def _check_ma_support(closes) -> Tuple[float, List[str]]:
    """
    均线支撑分析
    返回 (评分, 标签列表)
    """
    if len(closes) < 20:
        return 0, []

    s = pd.Series(closes)
    ma5 = s.rolling(5).mean().values
    ma10 = s.rolling(10).mean().values
    ma20 = s.rolling(20).mean().values

    score = 0.0
    tags = []
    current = closes[-1]

    # MA5 拐头向上（短线反弹先兆）
    if len(ma5) >= 3 and not np.isnan(ma5[-3]):
        if ma5[-1] > ma5[-2] and ma5[-2] <= ma5[-3]:
            score += 6
            tags.append("MA5拐头")

    # 价格站上 MA5
    if not np.isnan(ma5[-1]) and current > ma5[-1]:
        score += 3

    # MA5 上穿 MA10（金叉）
    if len(ma5) >= 2 and not np.isnan(ma10[-2]):
        if ma5[-1] > ma10[-1] and ma5[-2] <= ma10[-2]:
            score += 6
            tags.append("金叉")

    # 均线密集（MA5/10/20 距离 < 3%）
    if not any(np.isnan(v) for v in [ma5[-1], ma10[-1], ma20[-1]]):
        ma_max = max(ma5[-1], ma10[-1], ma20[-1])
        ma_min = min(ma5[-1], ma10[-1], ma20[-1])
        if current > 0:
            spread = (ma_max - ma_min) / current
            if spread < 0.03:
                score += 5
                tags.append("均线密集")

    return score, tags


def _check_kline_pattern(opens, closes, highs, lows) -> Tuple[float, str]:
    """
    底部K线形态识别
    返回 (评分, 形态名称)
    """
    if len(closes) < 3:
        return 0, ""

    best_score = 0
    best_pattern = ""

    o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
    body = abs(c - o)
    total_range = h - l if h > l else 0.001

    # 锤子线：长下影线 > 实体2倍，上影线很短
    lower_shadow = min(o, c) - l
    upper_shadow = h - max(o, c)
    if body > 0 and lower_shadow > body * 2 and upper_shadow < body * 0.5:
        best_score = 8
        best_pattern = "锤子线"

    # 阳包阴（看涨吞没）
    if len(closes) >= 2:
        yo, yc = opens[-2], closes[-2]
        if yc < yo and c > o and c > yo and o < yc:
            if 10 > best_score:
                best_score = 10
                best_pattern = "阳包阴"

    # 早晨之星（三日反转）
    if len(closes) >= 3:
        o3, c3 = opens[-3], closes[-3]
        o2, c2 = opens[-2], closes[-2]
        big_body = abs(o3 - c3)
        if big_body > 0 and c3 < o3 and abs(c2 - o2) < big_body * 0.3 and c > o and c > (o3 + c3) / 2:
            if 10 > best_score:
                best_score = 10
                best_pattern = "早晨之星"

    return best_score, best_pattern


def _evaluate_market_env(index_kline: Optional[pd.DataFrame]) -> Tuple[float, str]:
    """
    大盘环境评估
    返回 (环境评分, 环境标签)
    """
    if index_kline is None or len(index_kline) < 10:
        return 0, "unknown"

    closes = index_kline["close"].values
    ma5 = pd.Series(closes).rolling(5).mean().values

    today_change = (closes[-1] / closes[-2] - 1) if len(closes) >= 2 else 0
    week_change = (closes[-1] / closes[-5] - 1) if len(closes) >= 5 else 0

    # 大盘企稳或反弹中
    if today_change > 0 and not np.isnan(ma5[-1]) and closes[-1] > ma5[-1]:
        return 10, "bullish"

    # 大盘弱势震荡
    if today_change < -0.005 and week_change < -0.02:
        return 5, "weak"

    # 大盘暴跌
    if today_change < -0.02:
        return -10, "crash"

    return 0, "neutral"


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
