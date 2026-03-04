"""
统一信号分析引擎 v2
供 crypto_trader、crypto_backtest、screener 共用
包含：企稳判断、量能检测、均线分析、K线形态、反转确认、ATR 计算、多时间框架、BTC 联动
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ==================================================================
# ATR 计算
# ==================================================================

def calculate_atr(highs, lows, closes, period: int = 14) -> float:
    """计算 Average True Range"""
    if len(closes) < period + 1:
        return 0
    tr_values = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)
    if len(tr_values) < period:
        return 0
    return sum(tr_values[-period:]) / period


# ==================================================================
# 企稳信号
# ==================================================================

def check_stabilized(closes, lows, highs, volumes) -> Tuple[bool, int]:
    """
    多维度企稳确认
    必选：不创新低
    加分：下跌减速 / 振幅收窄 / 底部放量
    返回 (是否企稳, 置信度 0-3)
    """
    if len(closes) < 25:
        return False, 0

    recent_5d_low = min(lows[-5:])
    prev_20d_low = min(lows[-25:-5])
    if recent_5d_low < prev_20d_low * 0.99:
        return False, 0

    confidence = 0

    if len(closes) >= 10:
        recent_drop = (closes[-1] - closes[-5]) / closes[-5]
        prev_drop = (closes[-5] - closes[-10]) / closes[-10]
        if recent_drop > prev_drop:
            confidence += 1

    if len(highs) >= 15:
        recent_range = (max(highs[-5:]) - min(lows[-5:])) / closes[-1]
        prev_range = (max(highs[-15:-5]) - min(lows[-15:-5])) / closes[-5]
        if recent_range < prev_range:
            confidence += 1

    if len(volumes) >= 13:
        recent_vol = volumes[-3:].mean()
        prev_vol = volumes[-13:-3].mean()
        if prev_vol > 0 and recent_vol > prev_vol * 1.3:
            confidence += 1

    return confidence >= 1, confidence


# ==================================================================
# 量能异变
# ==================================================================

def check_volume_spike(volumes) -> Tuple[bool, float]:
    """
    量能异变检测（纯 K 线版本）
    返回 (是否放量, 量比)
    """
    if len(volumes) >= 23:
        avg_vol = volumes[-23:-3].mean()
        if avg_vol > 0:
            max_vol = max(volumes[-3:])
            ratio = round(max_vol / avg_vol, 2)
            return max_vol > avg_vol * 2, ratio
    return False, 0


def check_volume_spike_with_snapshot(volumes, snapshot_row) -> Tuple[bool, float]:
    """量能异变检测（A 股带 snapshot 版本）"""
    vr = snapshot_row.get("volume_ratio", 0)
    if len(volumes) >= 23:
        avg_vol_20 = volumes[-23:-3].mean()
        if avg_vol_20 > 0:
            max_vol_3d = max(volumes[-3:])
            actual_ratio = round(max_vol_3d / avg_vol_20, 2)
            return max_vol_3d > avg_vol_20 * 2, actual_ratio
    return vr >= 1.5, round(vr, 2)


# ==================================================================
# 均线支撑（加密货币版 MA7/MA25）
# ==================================================================

def check_ma_support_crypto(closes) -> Tuple[float, List[str]]:
    """加密货币均线支撑 (MA7/MA25)"""
    if len(closes) < 25:
        return 0, []

    s = pd.Series(closes)
    ma7 = s.rolling(7).mean().values
    ma25 = s.rolling(25).mean().values

    score = 0.0
    tags = []
    current = closes[-1]

    if len(ma7) >= 3 and not np.isnan(ma7[-3]):
        if ma7[-1] > ma7[-2] and ma7[-2] <= ma7[-3]:
            score += 6
            tags.append("MA7拐头")

    if not np.isnan(ma7[-1]) and current > ma7[-1]:
        score += 3

    if len(ma7) >= 2 and not np.isnan(ma25[-2]):
        if ma7[-1] > ma25[-1] and ma7[-2] <= ma25[-2]:
            score += 6
            tags.append("金叉")

    return score, tags


# ==================================================================
# 均线支撑（A 股版 MA5/MA10/MA20）
# ==================================================================

def check_ma_support_stock(closes) -> Tuple[float, List[str]]:
    """A 股均线支撑 (MA5/MA10/MA20)"""
    if len(closes) < 20:
        return 0, []

    s = pd.Series(closes)
    ma5 = s.rolling(5).mean().values
    ma10 = s.rolling(10).mean().values
    ma20 = s.rolling(20).mean().values

    score = 0.0
    tags = []
    current = closes[-1]

    if len(ma5) >= 3 and not np.isnan(ma5[-3]):
        if ma5[-1] > ma5[-2] and ma5[-2] <= ma5[-3]:
            score += 6
            tags.append("MA5拐头")

    if not np.isnan(ma5[-1]) and current > ma5[-1]:
        score += 3

    if len(ma5) >= 2 and not np.isnan(ma10[-2]):
        if ma5[-1] > ma10[-1] and ma5[-2] <= ma10[-2]:
            score += 6
            tags.append("金叉")

    if not any(np.isnan(v) for v in [ma5[-1], ma10[-1], ma20[-1]]):
        ma_max = max(ma5[-1], ma10[-1], ma20[-1])
        ma_min = min(ma5[-1], ma10[-1], ma20[-1])
        if current > 0:
            spread = (ma_max - ma_min) / current
            if spread < 0.03:
                score += 5
                tags.append("均线密集")

    return score, tags


# ==================================================================
# K 线形态识别
# ==================================================================

def check_kline_pattern(opens, closes, highs, lows) -> Tuple[float, str]:
    """底部 K 线形态识别"""
    if len(closes) < 3:
        return 0, ""

    best_score = 0
    best_pattern = ""

    o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
    body = abs(c - o)
    lower_shadow = min(o, c) - l
    upper_shadow = h - max(o, c)

    if body > 0 and lower_shadow > body * 2 and upper_shadow < body * 0.5:
        best_score = 8
        best_pattern = "锤子线"

    if len(closes) >= 2:
        yo, yc = opens[-2], closes[-2]
        if yc < yo and c > o and c > yo and o < yc:
            if 10 > best_score:
                best_score = 10
                best_pattern = "阳包阴"

    if len(closes) >= 3:
        o3, c3 = opens[-3], closes[-3]
        o2, c2 = opens[-2], closes[-2]
        big_body = abs(o3 - c3)
        if big_body > 0 and c3 < o3 and abs(c2 - o2) < big_body * 0.3 and c > o and c > (o3 + c3) / 2:
            if 10 > best_score:
                best_score = 10
                best_pattern = "早晨之星"

    return best_score, best_pattern


# ==================================================================
# 右侧反转确认（新增）
# ==================================================================

def check_reversal_confirmation(opens, closes, highs, lows, volumes) -> Tuple[float, List[str]]:
    """
    右侧反转确认 — 不只看跌够了，还要看开始涨了
    满分 15 分
    """
    if len(closes) < 6:
        return 0, []

    score = 0.0
    tags = []

    # (a) 突破近 5 日高点（多头发力）
    if closes[-1] > max(highs[-6:-1]):
        score += 6
        tags.append("突破5日高")

    # (b) 连续 2 根阳线且实体递增（多头加速）
    if len(opens) >= 2 and closes[-1] > opens[-1] and closes[-2] > opens[-2]:
        body_today = closes[-1] - opens[-1]
        body_yest = closes[-2] - opens[-2]
        if body_today > body_yest:
            score += 5
            tags.append("连阳递增")

    # (c) 放量上涨
    if len(volumes) >= 2 and volumes[-1] > volumes[-2] and closes[-1] > opens[-1]:
        score += 4
        tags.append("放量上涨")

    return score, tags


# ==================================================================
# 多时间框架过滤（新增）
# ==================================================================

def check_higher_timeframe(daily_closes) -> Tuple[float, str]:
    """
    日线级别趋势过滤
    输入：日线收盘价数组（至少 20 根）
    返回 (评分调整, 标签)
    """
    if len(daily_closes) < 20:
        return 0, "数据不足"

    ma7 = sum(daily_closes[-7:]) / 7
    ma20 = sum(daily_closes[-20:]) / 20
    current = daily_closes[-1]

    # 日线 MA7 < MA20 且价格在 MA20 下方 → 大趋势仍在下跌
    if ma7 < ma20 and current < ma20:
        prev_ma7 = sum(daily_closes[-8:-1]) / 7
        if ma7 < prev_ma7:
            return -15, "日线下行"
        return -8, "日线偏弱"

    # 日线 MA7 拐头且价格站上 MA7
    if current > ma7:
        prev_ma7 = sum(daily_closes[-8:-1]) / 7
        if ma7 > prev_ma7:
            return 10, "日线企稳"

    return 0, "日线中性"


# ==================================================================
# BTC 趋势联动（增强版）
# ==================================================================

def check_btc_trend_enhanced(btc_4h_closes, btc_daily_closes) -> Tuple[float, str]:
    """
    BTC 趋势联动 v2
    短期（4h 12 根 ≈ 2 天）+ 中期（日线 MA20）
    返回 (评分调整, 标签)
    """
    score = 0.0
    label = "BTC中性"

    # 短期动量
    if len(btc_4h_closes) >= 12:
        short_change = (btc_4h_closes[-1] / btc_4h_closes[-12] - 1)
        if short_change > 0.03:
            score += 6
            label = "BTC短期强"
        elif short_change > 0:
            score += 3
        elif short_change > -0.03:
            score -= 2
        else:
            score -= 6
            label = "BTC短期弱"

    # 中期趋势
    if len(btc_daily_closes) >= 20:
        ma20 = sum(btc_daily_closes[-20:]) / 20
        current = btc_daily_closes[-1]
        if current > ma20:
            score += 5
            if label == "BTC短期强":
                label = "BTC强势"
        else:
            prev_ma20 = sum(btc_daily_closes[-21:-1]) / 20
            if ma20 < prev_ma20:
                score -= 8
                label = "BTC熊市"
            else:
                score -= 3

    return score, label


# ==================================================================
# 综合信号评分（加密货币用）
# ==================================================================

def score_crypto_signal(
    opens, closes, highs, lows, volumes,
    drop_pct: float,
    stab_confidence: int,
    vol_ratio: float,
    ma_score: float,
    ma_tags: List[str],
    pattern_score: float,
    pattern_name: str,
    reversal_score: float,
    reversal_tags: List[str],
    btc_score: float,
    htf_score: float,
    min_score: float = 40,
) -> Optional[Dict]:
    """
    综合评分模型 v2（满分 120，归一化到 100）
    维度：跌幅(20) + 企稳(15) + 量能(15) + 均线(12) + 形态(8) + 反转确认(12) + BTC(10) + 多周期(8)
    """
    score = 0.0
    reasons = []
    tags = list(ma_tags)

    drop_s = min(drop_pct / 0.4 * 20, 20)
    score += drop_s
    reasons.append(f"回落{drop_pct*100:.1f}%")

    stab_s = min(stab_confidence * 5, 15)
    score += stab_s
    reasons.append(f"企稳{stab_confidence}/3")

    vol_s = min(max((vol_ratio - 1) * 6, 0), 15)
    score += vol_s
    reasons.append(f"量比{vol_ratio}")

    ma_capped = min(ma_score, 12)
    score += ma_capped

    pattern_capped = min(pattern_score, 8)
    score += pattern_capped
    if pattern_name:
        tags.append(pattern_name)
        reasons.append(pattern_name)

    reversal_capped = min(reversal_score, 12)
    score += reversal_capped
    tags.extend(reversal_tags)
    if reversal_tags:
        reasons.append("+".join(reversal_tags))

    btc_capped = max(min(btc_score, 10), -10)
    score += btc_capped

    htf_capped = max(min(htf_score, 8), -15)
    score += htf_capped

    score = round(max(min(score, 100), 0), 1)

    if score < min_score:
        return None

    return {
        "score": score,
        "tags": tags,
        "reason": "; ".join(reasons),
    }


# ==================================================================
# 平台底部识别
# ==================================================================

def check_platform_bottom(closes, lows, highs, min_platform_days: int = 10) -> Tuple[bool, Dict]:
    """
    平台底部识别：价格在一个狭窄区间内横盘筑底，之前有明显下跌。
    返回 (是否形成平台底, {platform_days, drop_from_high, platform_range_pct, score, tag})
    """
    result = {"platform_days": 0, "drop_from_high": 0, "platform_range_pct": 0, "score": 0, "tag": ""}

    if len(closes) < 30:
        return False, result

    high_60d = max(highs[-60:]) if len(highs) >= 60 else max(highs)
    current = closes[-1]
    drop_from_high = (high_60d - current) / high_60d
    result["drop_from_high"] = round(drop_from_high * 100, 1)

    if drop_from_high < 0.10:
        return False, result

    # 从最近的 K 线向前扫描，找出底部平台的长度
    # 平台定义：低点在一个 5% 的区间内波动
    recent_low = min(lows[-5:])
    platform_days = 0

    for i in range(5, min(len(lows), 60)):
        window_lows = lows[-i:]
        lo = min(window_lows)
        hi = max(window_lows)
        if lo <= 0:
            break
        spread = (hi - lo) / lo
        if spread < 0.08:
            platform_days = i
        else:
            break

    result["platform_days"] = platform_days

    if platform_days < min_platform_days:
        return False, result

    # 平台内的振幅（越窄越好）
    platform_lows = lows[-platform_days:]
    plo, phi = min(platform_lows), max(platform_lows)
    platform_range = (phi - plo) / plo if plo > 0 else 1
    result["platform_range_pct"] = round(platform_range * 100, 1)

    # 评分：平台天数 + 跌幅深度 + 平台紧凑度
    score = 0.0

    if platform_days >= 20:
        score += 10
    elif platform_days >= 15:
        score += 7
    else:
        score += 4

    if drop_from_high >= 0.30:
        score += 6
    elif drop_from_high >= 0.20:
        score += 4
    elif drop_from_high >= 0.15:
        score += 2

    if platform_range < 0.03:
        score += 4
        result["tag"] = "窄幅平台"
    elif platform_range < 0.05:
        score += 2
        result["tag"] = "平台底部"
    else:
        result["tag"] = "宽幅筑底"

    result["score"] = round(min(score, 20), 1)
    return True, result


# ==================================================================
# 下探收涨信号（核心买入信号）
# ==================================================================

def check_probe_and_close_up(opens, closes, highs, lows, volumes) -> Tuple[float, List[str]]:
    """
    下探收涨信号：日内向下探但收盘收涨，说明抛压被多头承接。
    连续出现则置信度更高。
    返回 (评分 0-25, 标签列表)
    """
    if len(closes) < 3:
        return 0, []

    score = 0.0
    tags = []
    probe_count = 0
    probe_indices = []

    # 扫描最近 5 根 K 线
    scan_range = min(5, len(closes))
    for i in range(1, scan_range + 1):
        idx = -i
        o, c, h, l = opens[idx], closes[idx], highs[idx], lows[idx]
        body = c - o
        lower_shadow = min(o, c) - l

        # 下探收涨条件：
        # 1. 收阳线 (close > open)
        # 2. 下影线 >= 实体的 1.2 倍（向下探过）
        # 3. 下影线占总振幅的比例 >= 40%
        total_range = h - l if h > l else 0.001
        is_bullish = c > o
        has_long_lower = lower_shadow > abs(body) * 1.2 if abs(body) > 0 else lower_shadow > total_range * 0.3
        lower_ratio = lower_shadow / total_range

        if is_bullish and has_long_lower and lower_ratio >= 0.4:
            probe_count += 1
            probe_indices.append(i)

    if probe_count == 0:
        return 0, []

    # 最近一天就是下探收涨
    if 1 in probe_indices:
        score += 12
        tags.append("下探收涨")

        # 成交量配合（放量下探收涨更有力度）
        if len(volumes) >= 2 and volumes[-1] > volumes[-2] * 1.2:
            score += 3
            tags.append("放量承接")

    # 连续 2 天下探收涨 → 双重确认
    if 1 in probe_indices and 2 in probe_indices:
        score += 8
        tags.append("连续确认")
    elif probe_count >= 2:
        score += 4
        tags.append("多次探底")

    # 下探后收盘价逐日抬高（多头加力）
    if len(closes) >= 3 and closes[-1] > closes[-2] > closes[-3]:
        if closes[-1] > opens[-1] and closes[-2] > opens[-2]:
            score += 3
            if "底部抬升" not in tags:
                tags.append("底部抬升")

    return round(min(score, 25), 1), tags
