"""
K 线数据获取模块
多数据源获取 A 股历史 K 线数据，计算均线指标
优先使用腾讯财经API，备选东方财富(akshare)
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import time
import logging
import json

logger = logging.getLogger(__name__)

# 简单的内存缓存
_cache = {}

# 上次请求时间戳，用于控制请求频率
_last_request_time = 0
_MIN_REQUEST_INTERVAL = 0.5

# 重试配置
_MAX_RETRIES = 3
_RETRY_DELAYS = [1, 2, 4]


def _cache_key(stock_code: str, start_date: str, end_date: str) -> str:
    """生成缓存键"""
    return f"{stock_code}_{start_date}_{end_date}"


def _get_market_prefix(stock_code: str) -> str:
    """根据股票代码判断市场前缀"""
    if stock_code.startswith('6'):
        return 'sh'
    elif stock_code.startswith(('0', '3')):
        return 'sz'
    elif stock_code.startswith(('4', '8')):
        return 'bj'
    return 'sz'


def _throttle():
    """控制请求频率"""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _get_eastmoney_secid(stock_code: str) -> str:
    """生成东方财富 secid: 1.代码(沪) 或 0.代码(深)"""
    if stock_code.startswith('6'):
        return f"1.{stock_code}"
    else:
        return f"0.{stock_code}"


def _fetch_today_snapshot(stock_code: str) -> Optional[Dict]:
    """
    获取当日实时行情快照（东方财富 push2 API）
    用于补充历史 K 线 API 不包含的当日数据
    f43: 最新价, f44: 最高, f45: 最低, f46: 开盘, f47: 成交量(手)
    价格需除以 100；成交量单位已是手，与历史 K 线 API 一致，不再转换
    """
    secid = _get_eastmoney_secid(stock_code)
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": secid,
        "fields": "f43,f44,f45,f46,f47",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }
    try:
        _throttle()
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        d = data.get("data")
        if not d or d.get("f43") is None:
            return None
        # 价格存为整数(分)，需除以100；f47 成交量单位已是手，与历史 K 线一致
        open_p = (d.get("f46") or 0) / 100
        high_p = (d.get("f44") or 0) / 100
        low_p = (d.get("f45") or 0) / 100
        close_p = (d.get("f43") or 0) / 100
        vol = float(d.get("f47") or 0)
        if open_p <= 0 or close_p <= 0:
            return None
        return {
            "open": open_p, "high": high_p, "low": low_p,
            "close": close_p, "volume": vol,
        }
    except Exception as e:
        logger.debug("获取 %s 当日快照失败: %s", stock_code, e)
        return None


def _fetch_from_eastmoney_by_secid(secid: str, start_str: str, end_str: str) -> Optional[pd.DataFrame]:
    """按 secid 获取 K 线（用于上证指数 1.000001）"""
    return _fetch_eastmoney_kline_impl(secid, start_str, end_str)


def _fetch_from_eastmoney(stock_code: str, start_str: str, end_str: str) -> Optional[pd.DataFrame]:
    """直接调用东方财富 HTTP API 获取 K 线数据"""
    secid = _get_eastmoney_secid(stock_code)
    return _fetch_eastmoney_kline_impl(secid, start_str, end_str)


def _fetch_eastmoney_kline_impl(secid: str, start_str: str, end_str: str) -> Optional[pd.DataFrame]:
    """东方财富 K 线 API 实现"""
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",       # 日K
        "fqt": "1",         # 前复权
        "beg": start_str,
        "end": end_str,
        "ut": "7eea3edcaed734bea9004fcfb7d7c8c5",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/",
        "Accept": "application/json, text/plain, */*",
    }
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("data") or not data["data"].get("klines"):
        return None

    rows = []
    for line in data["data"]["klines"]:
        parts = line.split(",")
        # 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
        rows.append({
            "date": parts[0],
            "open": float(parts[1]),
            "close": float(parts[2]),
            "high": float(parts[3]),
            "low": float(parts[4]),
            "volume": float(parts[5]),
        })

    return pd.DataFrame(rows)


def _fetch_from_tencent(stock_code: str, start_str: str, end_str: str) -> Optional[pd.DataFrame]:
    """
    调用腾讯财经 API 获取日 K 线数据（前复权）
    腾讯接口稳定，无需特殊认证
    start_str / end_str 格式: YYYYMMDD
    """
    prefix = _get_market_prefix(stock_code)
    symbol = f"{prefix}{stock_code}"

    # 计算需要多少个交易日（粗略估算：自然日 * 0.75）
    try:
        s_dt = datetime.strptime(start_str, "%Y%m%d")
        e_dt = datetime.strptime(end_str, "%Y%m%d")
        natural_days = (e_dt - s_dt).days
        num_bars = max(int(natural_days * 0.75), 100)
    except ValueError:
        num_bars = 500

    # 腾讯接口需要 YYYY-MM-DD 格式的日期
    start_fmt = f"{start_str[:4]}-{start_str[4:6]}-{start_str[6:8]}"
    end_fmt = f"{end_str[:4]}-{end_str[4:6]}-{end_str[6:8]}"

    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {
        "param": f"{symbol},day,{start_fmt},{end_fmt},{num_bars},qfq",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://web.sqt.gtimg.cn/",
    }

    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()

    # 腾讯返回的可能是 JSONP 或纯 JSON
    text = resp.text
    json_start = text.find("{")
    if json_start < 0:
        return None
    json_str = text[json_start:]

    data = json.loads(json_str)

    # data 可能是 dict 或 list，做安全处理
    data_body = data.get("data", {})
    if isinstance(data_body, list):
        # 空列表表示无数据
        if not data_body:
            return None
        # 有时腾讯返回 list 格式，取第一个元素
        data_body = data_body[0] if isinstance(data_body[0], dict) else {}

    stock_data = data_body.get(symbol, {})
    if isinstance(stock_data, list):
        # 再做一层安全处理
        return None

    # 优先取前复权数据 qfqday，其次 day
    klines = stock_data.get("qfqday") or stock_data.get("day")
    if not klines:
        return None

    rows = []
    for k in klines:
        # [日期, 开盘, 收盘, 最高, 最低, 成交量, ...]
        if len(k) < 6:
            continue
        rows.append({
            "date": k[0],
            "open": float(k[1]),
            "close": float(k[2]),
            "high": float(k[3]),
            "low": float(k[4]),
            "volume": float(k[5]),
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    # 过滤日期范围
    df = df[(df["date"] >= start_fmt) & (df["date"] <= end_fmt)]

    return df if not df.empty else None


def _fetch_with_fallback(stock_code: str, start_str: str, end_str: str) -> pd.DataFrame:
    """
    多数据源获取，带重试：
    1. 先尝试腾讯财经 API（稳定）
    2. 失败再尝试东方财富直连 API
    3. 最后尝试 akshare
    """
    sources = [
        ("腾讯财经", lambda: _fetch_from_tencent(stock_code, start_str, end_str)),
        ("东方财富", lambda: _fetch_from_eastmoney(stock_code, start_str, end_str)),
    ]

    # 尝试导入 akshare 作为最后备选
    try:
        import akshare as ak
        def _akshare_fetch():
            return ak.stock_zh_a_hist(
                symbol=stock_code, period="daily",
                start_date=start_str, end_date=end_str, adjust="qfq",
            ).rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
            })
        sources.append(("akshare", _akshare_fetch))
    except ImportError:
        pass

    last_error = None
    for source_name, fetch_fn in sources:
        for attempt in range(_MAX_RETRIES):
            try:
                _throttle()
                logger.info(f"[{source_name}] 获取 {stock_code} K线 (尝试 {attempt + 1}/{_MAX_RETRIES})")
                df = fetch_fn()
                if df is not None and not df.empty:
                    logger.info(f"[{source_name}] 获取 {stock_code} 成功, {len(df)} 条数据")
                    return df
                else:
                    logger.warning(f"[{source_name}] 获取 {stock_code} 返回空数据")
                    break  # 空数据不重试，换下一个源
            except Exception as e:
                last_error = e
                logger.warning(f"[{source_name}] 获取 {stock_code} 失败 (尝试 {attempt + 1}): {e}")
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_DELAYS[attempt]
                    logger.info(f"等待 {delay} 秒后重试...")
                    time.sleep(delay)

    if last_error:
        raise last_error
    raise Exception(f"所有数据源均无法获取 {stock_code} 的数据")


def fetch_kline_data(
    stock_code: str,
    buy_date: str,
    sell_date: str,
    before_days: int = 90,
    after_days: int = 30,
) -> Dict:
    """
    获取指定股票在交易期间的 K 线数据

    Args:
        stock_code: 6位股票代码
        buy_date: 买入日期 YYYY-MM-DD
        sell_date: 卖出日期 YYYY-MM-DD
        before_days: 买入日期前多少自然日
        after_days: 卖出日期后多少自然日
    """
    try:
        buy_dt = datetime.strptime(buy_date, '%Y-%m-%d')
        sell_dt = datetime.strptime(sell_date, '%Y-%m-%d')

        # 多取 120 天用于 MA99 计算预热
        start_dt = buy_dt - timedelta(days=before_days + 120)
        end_dt = sell_dt + timedelta(days=after_days)

        start_str = start_dt.strftime('%Y%m%d')
        end_str = end_dt.strftime('%Y%m%d')

        # 检查缓存
        cache_key = _cache_key(stock_code, start_str, end_str)
        if cache_key in _cache:
            return _cache[cache_key]

        # 多数据源获取
        df = _fetch_with_fallback(stock_code, start_str, end_str)

        if df is None or df.empty:
            return {
                'success': False, 'stock_code': stock_code,
                'dates': [], 'ohlcv': [], 'volumes': [],
                'ma7': [], 'ma25': [], 'ma99': [],
                'message': f'未获取到 {stock_code} 的 K 线数据',
            }

        # 确保数据类型正确
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        for col in ['open', 'close', 'high', 'low']:
            df[col] = df[col].astype(float)
        df['volume'] = df['volume'].astype(float)

        # 按日期排序去重
        df = df.sort_values('date').drop_duplicates(subset='date').reset_index(drop=True)

        # 补充当日实时数据：历史 K 线 API 通常只到昨天，交易日可拉取当日快照
        today_str = datetime.now().strftime('%Y-%m-%d')
        if df['date'].iloc[-1] < today_str and datetime.now().weekday() < 5:
            snapshot = _fetch_today_snapshot(stock_code)
            if snapshot:
                new_row = pd.DataFrame([{
                    'date': today_str,
                    'open': snapshot['open'],
                    'close': snapshot['close'],
                    'high': snapshot['high'],
                    'low': snapshot['low'],
                    'volume': snapshot['volume'],
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                df = df.sort_values('date').reset_index(drop=True)
                logger.info("已补充 %s 当日实时数据", stock_code)

        # 计算均线
        df['ma7'] = df['close'].rolling(window=7).mean()
        df['ma25'] = df['close'].rolling(window=25).mean()
        df['ma99'] = df['close'].rolling(window=99).mean()

        # 裁剪到需要的显示范围（去掉均线预热的数据）
        display_start = (buy_dt - timedelta(days=before_days)).strftime('%Y-%m-%d')
        display_end = end_dt.strftime('%Y-%m-%d')
        df = df[(df['date'] >= display_start) & (df['date'] <= display_end)]

        if df.empty:
            return {
                'success': False, 'stock_code': stock_code,
                'dates': [], 'ohlcv': [], 'volumes': [],
                'ma7': [], 'ma25': [], 'ma99': [],
                'message': f'{stock_code} 在指定时间范围内无交易数据',
            }

        # 构造返回数据
        dates = df['date'].tolist()
        ohlcv = df[['open', 'close', 'low', 'high']].round(2).values.tolist()
        volumes = df['volume'].tolist()

        ma7 = [round(v, 2) if pd.notna(v) else None for v in df['ma7'].tolist()]
        ma25 = [round(v, 2) if pd.notna(v) else None for v in df['ma25'].tolist()]
        ma99 = [round(v, 2) if pd.notna(v) else None for v in df['ma99'].tolist()]

        result = {
            'success': True, 'stock_code': stock_code,
            'dates': dates, 'ohlcv': ohlcv, 'volumes': volumes,
            'ma7': ma7, 'ma25': ma25, 'ma99': ma99,
            'message': f'获取到 {len(dates)} 条 K 线数据',
        }

        _cache[cache_key] = result
        return result

    except Exception as e:
        return {
            'success': False, 'stock_code': stock_code,
            'dates': [], 'ohlcv': [], 'volumes': [],
            'ma7': [], 'ma25': [], 'ma99': [],
            'message': f'获取 K 线数据失败：{str(e)}',
        }


def fetch_today_snapshot(stock_code: str) -> Optional[Dict]:
    """获取当日实时行情快照，供其他模块调用"""
    return _fetch_today_snapshot(stock_code)


def fetch_stock_kline_range(stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    获取指定日期范围内的日K线，用于回测（不含当日实时补充）
    start_date/end_date: YYYY-MM-DD
    """
    start_str = start_date.replace("-", "")
    end_str = end_date.replace("-", "")
    try:
        df = _fetch_with_fallback(stock_code, start_str, end_str)
        if df is None or df.empty:
            return None
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = df[col].astype(float)
        return df.sort_values('date').drop_duplicates(subset='date').reset_index(drop=True)
    except Exception:
        return None


def fetch_index_kline_range(start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """获取上证指数指定日期范围内K线（secid=1.000001）"""
    start_str = start_date.replace("-", "")
    end_str = end_date.replace("-", "")
    try:
        df = _fetch_from_eastmoney_by_secid("1.000001", start_str, end_str)
        if df is None:
            return None
        df = df.copy()
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = df[col].astype(float)
        return df.sort_values('date').drop_duplicates(subset='date').reset_index(drop=True)
    except Exception:
        return None


def clear_cache():
    """清除缓存"""
    global _cache
    _cache = {}
