"""
K 线数据获取模块
使用 akshare 获取 A 股历史 K 线数据，计算均线指标
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import functools
import hashlib
import json

# 简单的内存缓存
_cache = {}


def _cache_key(stock_code: str, start_date: str, end_date: str) -> str:
    """生成缓存键"""
    return f"{stock_code}_{start_date}_{end_date}"


def _get_market_prefix(stock_code: str) -> str:
    """
    根据股票代码判断市场
    沪市：60开头
    深市：00, 30开头
    北交所：4, 8开头
    """
    if stock_code.startswith('6'):
        return 'sh'
    elif stock_code.startswith(('0', '3')):
        return 'sz'
    elif stock_code.startswith(('4', '8')):
        return 'bj'
    return 'sz'  # 默认深市


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

    Returns:
        {
            'success': bool,
            'stock_code': str,
            'dates': list[str],
            'ohlcv': list[list],  # [[open, close, low, high, volume], ...]
            'ma5': list,
            'ma10': list,
            'ma20': list,
            'ma60': list,
            'message': str,
        }
    """
    try:
        # 计算时间范围（多取一些数据用于计算均线）
        buy_dt = datetime.strptime(buy_date, '%Y-%m-%d')
        sell_dt = datetime.strptime(sell_date, '%Y-%m-%d')

        # 多取 60 天用于 MA60 计算预热
        start_dt = buy_dt - timedelta(days=before_days + 90)
        end_dt = sell_dt + timedelta(days=after_days)

        start_str = start_dt.strftime('%Y%m%d')
        end_str = end_dt.strftime('%Y%m%d')

        # 检查缓存
        cache_key = _cache_key(stock_code, start_str, end_str)
        if cache_key in _cache:
            return _cache[cache_key]

        # 通过 akshare 获取日 K 线数据
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_str,
            end_date=end_str,
            adjust="qfq",  # 前复权
        )

        if df is None or df.empty:
            return {
                'success': False,
                'stock_code': stock_code,
                'dates': [],
                'ohlcv': [],
                'ma5': [],
                'ma10': [],
                'ma20': [],
                'ma60': [],
                'message': f'未获取到 {stock_code} 的 K 线数据',
            }

        # 标准化列名（akshare 返回的列名是中文）
        col_map = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
        }
        df = df.rename(columns=col_map)

        # 确保数据类型正确
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        for col in ['open', 'close', 'high', 'low']:
            df[col] = df[col].astype(float)
        df['volume'] = df['volume'].astype(float)

        # 计算均线
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()

        # 裁剪到需要的显示范围（去掉均线预热的数据）
        display_start = (buy_dt - timedelta(days=before_days)).strftime('%Y-%m-%d')
        display_end = end_dt.strftime('%Y-%m-%d')
        df = df[(df['date'] >= display_start) & (df['date'] <= display_end)]

        if df.empty:
            return {
                'success': False,
                'stock_code': stock_code,
                'dates': [],
                'ohlcv': [],
                'ma5': [],
                'ma10': [],
                'ma20': [],
                'ma60': [],
                'message': f'{stock_code} 在指定时间范围内无交易数据',
            }

        # 构造返回数据
        dates = df['date'].tolist()
        # ECharts K 线数据格式: [open, close, low, high]
        ohlcv = df[['open', 'close', 'low', 'high']].round(2).values.tolist()
        volumes = df['volume'].tolist()

        # 均线数据（None 替代 NaN）
        ma5 = [round(v, 2) if pd.notna(v) else None for v in df['ma5'].tolist()]
        ma10 = [round(v, 2) if pd.notna(v) else None for v in df['ma10'].tolist()]
        ma20 = [round(v, 2) if pd.notna(v) else None for v in df['ma20'].tolist()]
        ma60 = [round(v, 2) if pd.notna(v) else None for v in df['ma60'].tolist()]

        result = {
            'success': True,
            'stock_code': stock_code,
            'dates': dates,
            'ohlcv': ohlcv,
            'volumes': volumes,
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'ma60': ma60,
            'message': f'获取到 {len(dates)} 条 K 线数据',
        }

        # 写入缓存
        _cache[cache_key] = result
        return result

    except Exception as e:
        return {
            'success': False,
            'stock_code': stock_code,
            'dates': [],
            'ohlcv': [],
            'volumes': [],
            'ma5': [],
            'ma10': [],
            'ma20': [],
            'ma60': [],
            'message': f'获取 K 线数据失败：{str(e)}',
        }


def clear_cache():
    """清除缓存"""
    global _cache
    _cache = {}
