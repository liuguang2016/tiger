"""
弹簧反弹选股引擎 v3
核心理论升级：平台底部识别 + 下探收涨确认 + 连续抵抗信号
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

from services import signal_engine as sig

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
# 全A股快照缓存（兜底）
# ============================
_SNAPSHOT_CACHE_LOCK = threading.Lock()
_SNAPSHOT_CACHE: Dict[str, object] = {
    "df": None,   # Optional[pd.DataFrame]
    "ts": 0.0,    # last update time
    "source": "", # data source name for debug
}
_SNAPSHOT_CACHE_TTL_SEC = 30 * 60  # 30分钟：避免数据源短时封禁/波动导致“筛选结果为0”

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


def fetch_snapshot_for_strategies() -> Optional[pd.DataFrame]:
    """
    供策略选股使用：获取全A股实时行情，与参数选股相同数据源
    返回列: code, name, close, change_pct, open, high, low
    """
    df = _fetch_all_stocks_snapshot()
    if df is None or df.empty:
        return None
    cols = ["code", "name", "close", "change_pct", "open", "high", "low"]
    return df[[c for c in cols if c in df.columns]].copy()


def fetch_kline_for_strategies(code: str, days: int = 90) -> Optional[pd.DataFrame]:
    """
    供策略选股使用：获取单只股票K线，与参数选股相同数据源（含当日补充）
    返回列: date, open, close, high, low, volume
    """
    return _fetch_stock_kline(code, days=days)


# ============================
# 筛选主流程（后台线程）
# ============================

def _run_screening(task_id: str, params: dict):
    """后台线程执行筛选"""
    drop_pct_threshold = params.get("drop_pct", 15) / 100.0
    volume_ratio_threshold = params.get("volume_ratio", 1.2)
    min_turnover = params.get("min_turnover", 1.0)
    mv_range = params.get("mv_range", "all")
    ma_filter = params.get("ma_filter", "none")
    min_platform_days = params.get("min_platform_days", 1)
    use_probe_confirm = params.get("use_probe_confirm", True)

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

        candidates = snapshot_df[
            (~snapshot_df["name"].str.contains("ST|退|N|C", na=False)) &
            (snapshot_df["volume"] > 0) &
            (snapshot_df["turnover"] >= min_turnover) &
            (snapshot_df["change_pct"] > -9.5) &
            (snapshot_df["change_pct"] < 9.5) &
            (snapshot_df["total_mv"] > 2e9)
        ].copy()

        if mv_range == "small":
            candidates = candidates[(candidates["total_mv"] >= 2e9) & (candidates["total_mv"] <= 100e9)]
        elif mv_range == "mid":
            candidates = candidates[(candidates["total_mv"] > 100e9) & (candidates["total_mv"] <= 500e9)]
        elif mv_range == "all":
            candidates = candidates[candidates["total_mv"] <= 500e9]

        # 量比从硬性门槛改为软过滤：保留量比 >= 0.8 的（太低的直接排除）
        candidates = candidates[candidates["volume_ratio"] >= 0.8]
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
                    min_platform_days, use_probe_confirm,
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
    获取全部 A 股实时数据，优先 akshare（东财/新浪），东方财富直连失效时自动切换
    """
    max_rounds = 3
    last_err: Optional[str] = None

    for round_idx in range(max_rounds):
        # 1. 优先 akshare 东财接口（与直连 push2 可能不同）
        df = _fetch_all_stocks_snapshot_akshare_em()
        if df is not None and not df.empty:
            with _SNAPSHOT_CACHE_LOCK:
                _SNAPSHOT_CACHE["df"] = df.copy()
                _SNAPSHOT_CACHE["ts"] = time.time()
                _SNAPSHOT_CACHE["source"] = "akshare_em"
            return df

        # 2. 备选：akshare 新浪接口（缺 turnover/volume_ratio/total_mv 时用默认值）
        df = _fetch_all_stocks_snapshot_akshare_sina()
        if df is not None and not df.empty:
            logger.info("使用新浪数据源获取A股快照（换手率/量比/市值为估计值）")
            with _SNAPSHOT_CACHE_LOCK:
                _SNAPSHOT_CACHE["df"] = df.copy()
                _SNAPSHOT_CACHE["ts"] = time.time()
                _SNAPSHOT_CACHE["source"] = "akshare_sina"
            return df

        last_err = "akshare快照连续失败（可能被限流/返回HTML）"
        delay = min(2 ** round_idx, 8)  # 1s/2s/4s/8s
        if round_idx < max_rounds - 1:
            logger.warning("全A股快照获取失败，等待 %ss 后重试（第 %d/%d）", delay, round_idx + 1, max_rounds)
            time.sleep(delay)

    # 最后兜底：返回最近一次成功结果，避免筛选结果为0
    with _SNAPSHOT_CACHE_LOCK:
        cache_df = _SNAPSHOT_CACHE.get("df")  # type: ignore[assignment]
        cache_ts = float(_SNAPSHOT_CACHE.get("ts") or 0.0)  # type: ignore[arg-type]
        cache_source = str(_SNAPSHOT_CACHE.get("source") or "")

    if cache_df is not None and cache_ts > 0 and (time.time() - cache_ts) <= _SNAPSHOT_CACHE_TTL_SEC:
        logger.warning("使用缓存A股快照兜底（source=%s，缓存未过期）", cache_source)
        return cache_df.copy()

    logger.warning("全A股快照获取失败且缓存不可用：%s", last_err)
    return None


def _fetch_all_stocks_snapshot_akshare_em() -> Optional[pd.DataFrame]:
    """akshare 东方财富 - 沪深京 A 股实时行情"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return None
        df = df.rename(columns={
            "代码": "code",
            "名称": "name",
            "最新价": "close",
            "涨跌幅": "change_pct",
            "成交量": "volume",
            "成交额": "amount",
            "换手率": "turnover",
            "量比": "volume_ratio",
            "最高": "high",
            "最低": "low",
            "今开": "open",
            "总市值": "total_mv",
        })
        df["code"] = df["code"].astype(str).str.zfill(6)
        for col in ["turnover", "volume_ratio"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df["total_mv"] = pd.to_numeric(df["total_mv"], errors="coerce").fillna(0)
        return df[["code", "name", "close", "change_pct", "volume", "amount",
                   "turnover", "volume_ratio", "high", "low", "open", "total_mv"]].copy()
    except Exception as e:
        logger.warning("akshare stock_zh_a_spot_em 失败: %s", e)
        return None


def _fetch_all_stocks_snapshot_akshare_sina() -> Optional[pd.DataFrame]:
    """akshare 新浪 - 沪深京 A 股实时行情（无换手率/量比/总市值，用默认值）"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot()
        if df is None or df.empty:
            return None
        # 新浪代码格式 sh600000/sz000001/bj430047，提取 6 位
        df["code"] = df["代码"].astype(str).str.replace(
            r"^(sh|sz|bj)", "", case=False, regex=True
        ).str.zfill(6)
        df = df.rename(columns={
            "名称": "name",
            "最新价": "close",
            "涨跌幅": "change_pct",
            "成交量": "volume",
            "成交额": "amount",
            "最高": "high",
            "最低": "low",
            "今开": "open",
        })
        # 成交量：新浪为股，转手（÷100）
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0) / 100
        df["turnover"] = 1.0
        df["volume_ratio"] = 1.0
        # 150e9 使 mid(100~500亿)、all(<=500亿) 通过筛选；small(2~100亿) 会被排除
        df["total_mv"] = 150e9
        return df[["code", "name", "close", "change_pct", "volume", "amount",
                   "turnover", "volume_ratio", "high", "low", "open", "total_mv"]].copy()
    except Exception as e:
        logger.warning("akshare stock_zh_a_spot (新浪) 失败: %s", e)
        return None


# ============================
# Stage 2: 逐股多维度分析
# ============================

def _build_snapshot_from_kline(kline_df: pd.DataFrame) -> pd.Series:
    """从 K 线最后一行构建模拟 snapshot_row，用于回测"""
    closes = kline_df["close"].values
    volumes = kline_df["volume"].values
    change_pct = (closes[-1] / closes[-2] - 1) * 100 if len(closes) >= 2 else 0
    vol_ratio = 1.2
    if len(volumes) >= 23:
        avg_20 = np.mean(volumes[-23:-3])
        vol_ratio = volumes[-1] / avg_20 if avg_20 > 0 else 1.2
    return pd.Series({
        "close": closes[-1], "change_pct": change_pct,
        "volume_ratio": round(vol_ratio, 2),
    })


def analyze_candidate_for_backtest(
    code: str,
    name: str,
    kline_df: pd.DataFrame,
    index_kline: Optional[pd.DataFrame],
    market_score: float,
    market_env: str,
    drop_threshold: float,
    ma_filter: str,
    min_platform_days: int = 1,
    use_probe_confirm: bool = True,
) -> Optional[Dict]:
    """
    回测用：对单只股票进行多维度技术分析，使用已获取的 K 线（不拉取实时数据）
    """
    if kline_df is None or len(kline_df) < 30:
        return None
    snapshot_row = _build_snapshot_from_kline(kline_df)
    return _analyze_candidate(
        code, name, snapshot_row, index_kline, market_score, market_env,
        drop_threshold, ma_filter, min_platform_days, use_probe_confirm,
        kline_df=kline_df,
    )


def _analyze_candidate(
    code: str,
    name: str,
    snapshot_row: pd.Series,
    index_kline: Optional[pd.DataFrame],
    market_score: float,
    market_env: str,
    drop_threshold: float,
    ma_filter: str,
    min_platform_days: int = 1,
    use_probe_confirm: bool = True,
    kline_df: Optional[pd.DataFrame] = None,
) -> Optional[Dict]:
    """
    对单只股票进行多维度技术分析 v3
    评分维度（7维）：
      平台底部质量(20) + 下探收涨信号(25) + 企稳质量(10) +
      量能配合(15) + 均线位置(10) + K线形态(10) + 大盘环境(10)
    kline_df: 可选，回测时传入，不传则拉取实时
    """
    if kline_df is None:
        kline_df = _fetch_stock_kline(code, days=90)
    if kline_df is None or len(kline_df) < 30:
        return None

    opens = kline_df["open"].values
    closes = kline_df["close"].values
    highs = kline_df["high"].values
    lows = kline_df["low"].values
    volumes = kline_df["volume"].values

    # ===== 硬性条件 =====

    # 条件1: 平台底部（替代简单跌幅百分比）
    has_platform, platform_info = sig.check_platform_bottom(
        closes, lows, highs, min_platform_days=min_platform_days
    )
    if not has_platform:
        # 回退：如果没有平台底部，仍检查跌幅是否足够大（兼容旧逻辑）
        high_60d = max(highs[-60:]) if len(highs) >= 60 else max(highs)
        drop_pct = (high_60d - closes[-1]) / high_60d
        if drop_pct < drop_threshold:
            return None
        # 有跌幅但无平台 → 平台分为 0，继续评分
        platform_info = {
            "platform_days": 0, "drop_from_high": round(drop_pct * 100, 1),
            "platform_range_pct": 0, "score": 0, "tag": ""
        }

    # 条件2: 下探收涨信号（核心买入信号）
    probe_score, probe_tags = sig.check_probe_and_close_up(opens, closes, highs, lows, volumes)
    if use_probe_confirm and probe_score < 8:
        # 下探收涨是核心信号，低于 8 分说明没有明显的抵抗承接
        # 但如果平台底部很强（>= 12），仍可通过
        if platform_info["score"] < 12:
            return None

    # 条件3: 均线过滤（可选）
    ma_score, ma_tags = _check_ma_support(closes)
    if ma_filter == "ma5_turn" and "MA5拐头" not in ma_tags:
        return None
    if ma_filter == "golden_cross" and "金叉" not in ma_tags:
        return None

    # ===== 多维度加权评分（满分 100） =====

    score = 0.0
    reasons = []
    tags = []

    # 维度1: 平台底部质量（满分 20）
    plat_score = min(platform_info["score"], 20)
    score += plat_score
    if platform_info["tag"]:
        tags.append(platform_info["tag"])
    if platform_info["platform_days"] > 0:
        reasons.append(f"平台{platform_info['platform_days']}天")
    reasons.append(f"高点回落{platform_info['drop_from_high']}%")

    # 维度2: 下探收涨信号（满分 25）— 最核心维度
    probe_capped = min(probe_score, 25)
    score += probe_capped
    tags.extend(probe_tags)
    if probe_tags:
        reasons.append("；".join(probe_tags))

    # 维度3: 企稳质量（满分 10，降权因平台底部已含企稳信息）
    stabilized, stab_confidence = _check_stabilized(closes, lows, highs, volumes)
    stab_score = min(stab_confidence * 3.3, 10) if stabilized else 0
    score += stab_score

    # 维度4: 量能配合（满分 15）— 从硬性条件改为加分项
    vol_spike, vol_ratio_actual = _check_volume_spike(volumes, snapshot_row)
    vr = snapshot_row.get("volume_ratio", 0)
    vol_score = 0.0
    if vol_spike:
        vol_score += 8
    if vr >= 2.0:
        vol_score += 7
    elif vr >= 1.5:
        vol_score += 5
    elif vr >= 1.2:
        vol_score += 3
    vol_score = min(vol_score, 15)
    score += vol_score
    reasons.append(f"量比{round(max(vol_ratio_actual, vr), 2)}")

    # 维度5: 均线位置（满分 10）
    ma_capped = min(ma_score, 10)
    score += ma_capped
    tags.extend(ma_tags)

    # 维度6: K线形态（满分 10）
    pattern_score, pattern_name = _check_kline_pattern(opens, closes, highs, lows)
    pattern_capped = min(pattern_score, 10)
    score += pattern_capped
    if pattern_name:
        tags.append(pattern_name)
        reasons.append(pattern_name)

    # 维度7: 大盘环境（满分 10）
    env_score = max(min(market_score, 10), -10)
    if market_env == "weak":
        stock_change = snapshot_row.get("change_pct", 0) / 100.0
        if stock_change > 0:
            env_score += 5
    score += env_score

    score = round(max(min(score, 100), 0), 1)

    # 总分低于 30 不入选
    if score < 30:
        return None

    drop_pct_display = platform_info.get("drop_from_high", 0)

    return {
        "stock_code": code,
        "stock_name": name,
        "score": score,
        "drop_pct": drop_pct_display,
        "volume_ratio": round(max(vol_ratio_actual, vr), 2),
        "close": closes[-1],
        "change_pct": snapshot_row.get("change_pct", 0),
        "reason": "；".join(reasons),
        "tags": tags,
        "pattern": pattern_name,
        "ma_tags": ma_tags,
        "stab_confidence": stab_confidence if stabilized else 0,
        "market_env": market_env,
        "platform_days": platform_info.get("platform_days", 0),
        "probe_score": probe_capped,
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
    """获取单只股票近N天K线，优先东财直连，失败则 akshare"""
    end_str = datetime.now().strftime("%Y%m%d")
    start_str = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")

    # 1. 东方财富直连
    df = _fetch_stock_kline_eastmoney(code, start_str, end_str)
    if df is not None and not df.empty:
        df = _maybe_append_today_snapshot(df, code)
        return df

    # 2. akshare 备选
    try:
        import akshare as ak
        adf = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start_str, end_date=end_str, adjust="qfq",
        )
        if adf is not None and not adf.empty:
            df = adf.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume",
            })
            df = df[["date", "open", "close", "high", "low", "volume"]].copy()
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            df = _maybe_append_today_snapshot(df, code)
            return df
    except Exception as e:
        logger.debug("akshare K线 %s 失败: %s", code, e)
    return None


def _fetch_stock_kline_eastmoney(code: str, start_str: str, end_str: str) -> Optional[pd.DataFrame]:
    """东财直连获取 K 线"""
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "1",
        "beg": start_str, "end": end_str,
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
        logger.debug("东财 K线 %s 失败: %s", code, e)
        return None


def _maybe_append_today_snapshot(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """若为交易日且最后一条为昨日，尝试补充当日实时数据"""
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if not df.empty and df["date"].iloc[-1] < today_str and datetime.now().weekday() < 5:
            from services.stock_data import fetch_today_snapshot
            snap = fetch_today_snapshot(code)
            if snap:
                new_row = pd.DataFrame([{
                    "date": today_str,
                    "open": snap["open"],
                    "close": snap["close"],
                    "high": snap["high"],
                    "low": snap["low"],
                    "volume": snap["volume"],
                }])
                df = pd.concat([df, new_row], ignore_index=True)
    except Exception:
        pass
    return df


def _fetch_index_snapshot() -> dict:
    """获取上证指数、深证成指、创业板指实时快照，优先 akshare（东财/新浪）"""
    result = _fetch_index_snapshot_akshare()
    if result:
        # 转换为前端期望的格式
        return _convert_index_format(result)
    return {}


def _convert_index_format(raw: dict) -> dict:
    """将原始指数数据转换为前端期望的格式"""
    return {
        "sh": {
            "value": raw.get("sh_close", 0),
            "change": raw.get("sh_change_pct", 0)
        },
        "sz": {
            "value": raw.get("sz_close", 0),
            "change": raw.get("sz_change_pct", 0)
        },
        "cyb": {
            "value": raw.get("cyb_close", 0),
            "change": raw.get("cyb_change_pct", 0)
        }
    }


def _fetch_index_snapshot_akshare() -> dict:
    """akshare 获取指数快照：上证、深证、创业板指，先试新浪，失败则用东财"""
    # 1. 新浪：一次返回所有指数，含 sh000001、sz399001、sz399006（创业板）
    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_sina()
        if df is not None and not df.empty:
            result = {}
            codes = df["代码"].astype(str).str.lower()
            sh = df[codes.isin(["sh000001", "000001"])]
            sz = df[codes.isin(["sz399001", "399001"])]
            cyb = df[codes.isin(["sz399006", "399006"])]  # 创业板指
            if not sh.empty:
                row = sh.iloc[0]
                result["sh_name"] = "上证指数"
                result["sh_close"] = float(row.get("最新价", 0) or 0)
                result["sh_change_pct"] = float(row.get("涨跌幅", 0) or 0)
                result["sh_change"] = float(row.get("涨跌额", 0) or 0)
            if not sz.empty:
                row = sz.iloc[0]
                result["sz_name"] = "深证成指"
                result["sz_close"] = float(row.get("最新价", 0) or 0)
                result["sz_change_pct"] = float(row.get("涨跌幅", 0) or 0)
                result["sz_change"] = float(row.get("涨跌额", 0) or 0)
            if not cyb.empty:
                row = cyb.iloc[0]
                result["cyb_name"] = "创业板指"
                result["cyb_close"] = float(row.get("最新价", 0) or 0)
                result["cyb_change_pct"] = float(row.get("涨跌幅", 0) or 0)
                result["cyb_change"] = float(row.get("涨跌额", 0) or 0)
            if result:
                return result
    except Exception as e:
        logger.warning("akshare 指数快照(新浪) 失败: %s", e)

    # 2. 东财：分三次获取上证、深证、创业板
    try:
        import akshare as ak
        result = {}
        for symbol, code_key, name_key, name_val in [
            ("上证系列指数", "000001", "sh", "上证指数"),
            ("深证系列指数", "399001", "sz", "深证成指"),
            ("深证系列指数", "399006", "cyb", "创业板指"),
        ]:
            df = ak.stock_zh_index_spot_em(symbol=symbol)
            if df is not None and not df.empty:
                row = df[df["代码"].astype(str) == code_key]
                if not row.empty:
                    r = row.iloc[0]
                    result[f"{name_key}_name"] = name_val
                    result[f"{name_key}_close"] = float(r.get("最新价", 0) or 0)
                    result[f"{name_key}_change_pct"] = float(r.get("涨跌幅", 0) or 0)
                    result[f"{name_key}_change"] = float(r.get("涨跌额", 0) or 0)
        if result:
            return result
    except Exception as e:
        logger.warning("akshare 指数快照(东财) 失败: %s", e)

    return {}


def _fetch_index_kline() -> Optional[pd.DataFrame]:
    """获取上证指数近30日K线"""
    return _fetch_stock_kline_by_secid("1.000001", days=30)


def _fetch_stock_kline_by_secid(secid: str, days: int = 30) -> Optional[pd.DataFrame]:
    """按 secid 获取K线（用于上证指数 1.000001 等），失败则 akshare"""
    end_str = datetime.now().strftime("%Y%m%d")
    start_str = (datetime.now() - timedelta(days=days + 10)).strftime("%Y%m%d")

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "1",
        "beg": start_str, "end": end_str,
        "ut": "7eea3edcaed734bea9004fcfb7d7c8c5",
    }
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        klines = data.get("data", {}).get("klines", [])
        if klines:
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
        logger.debug("东财指数K线失败: %s", e)

    # akshare 备选：上证指数 1.000001 -> sh000001
    if secid == "1.000001":
        try:
            import akshare as ak
            adf = ak.stock_zh_index_daily_em(
                symbol="sh000001", start_date=start_str, end_date=end_str,
            )
            if adf is not None and not adf.empty:
                adf["date"] = pd.to_datetime(adf["date"]).dt.strftime("%Y-%m-%d")
                return adf[["date", "open", "close", "high", "low", "volume"]].copy()
        except Exception as e:
            logger.debug("akshare 指数K线失败: %s", e)
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
