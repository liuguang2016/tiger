"""
交割单 CSV 解析模块
支持常见券商交割单格式，自动识别列名并标准化
"""

import pandas as pd
import re
import io
from typing import Optional

# 标准字段名
STANDARD_COLUMNS = {
    'trade_date': '成交日期',
    'stock_code': '证券代码',
    'stock_name': '证券名称',
    'direction': '买卖方向',
    'price': '成交价格',
    'quantity': '成交数量',
    'amount': '成交金额',
    'commission': '手续费',
    'stamp_tax': '印花税',
    'transfer_fee': '过户费',
}

# 各券商可能使用的列名映射（模糊匹配）
COLUMN_ALIASES = {
    'trade_date': [
        '成交日期', '交易日期', '日期', '委托日期', '发生日期',
        '业务日期', '交割日期', 'date', 'trade_date',
    ],
    'stock_code': [
        '证券代码', '股票代码', '代码', '标的代码', '合同编号',
        'code', 'stock_code', 'symbol',
    ],
    'stock_name': [
        '证券名称', '股票名称', '名称', '证券简称', '标的名称',
        'name', 'stock_name',
    ],
    'direction': [
        '买卖标志', '买卖方向', '交易方向', '操作', '业务名称',
        '委托方向', '交易类型', '摘要', '业务标志', 'direction',
        'side', 'type',
    ],
    'price': [
        '成交价格', '成交均价', '价格', '成交价', '委托价格',
        'price', 'trade_price',
    ],
    'quantity': [
        '成交数量', '数量', '成交股数', '委托数量', '发生数量',
        'quantity', 'volume', 'qty',
    ],
    'amount': [
        '成交金额', '金额', '发生金额', '交易金额', '成交额',
        'amount', 'trade_amount',
    ],
    'commission': [
        '手续费', '佣金', '委托佣金', '交易佣金', '净佣金',
        'commission', 'fee',
    ],
    'stamp_tax': [
        '印花税', 'stamp_tax', 'tax',
    ],
    'transfer_fee': [
        '过户费', 'transfer_fee',
    ],
}

# 买入关键词
BUY_KEYWORDS = ['买入', '买', '证券买入', 'buy', 'B', '担保品买入', '融资买入']
# 卖出关键词
SELL_KEYWORDS = ['卖出', '卖', '证券卖出', 'sell', 'S', '担保品卖出', '融券卖出']


def _match_column(col_name: str, alias_list: list) -> bool:
    """检查列名是否匹配别名列表中的任何一个"""
    col_clean = col_name.strip().lower()
    for alias in alias_list:
        if alias.lower() == col_clean:
            return True
    return False


def _find_column_mapping(df_columns: list) -> dict:
    """
    根据 DataFrame 的列名，自动匹配到标准字段
    返回 {标准字段名: 原始列名} 的映射
    """
    mapping = {}
    used_columns = set()

    for std_name, aliases in COLUMN_ALIASES.items():
        for col in df_columns:
            if col in used_columns:
                continue
            if _match_column(col, aliases):
                mapping[std_name] = col
                used_columns.add(col)
                break

    return mapping


def _normalize_direction(value: str) -> Optional[str]:
    """将买卖方向标准化为 '买入' 或 '卖出'"""
    if not isinstance(value, str):
        return None
    value = value.strip()
    for keyword in BUY_KEYWORDS:
        if keyword in value:
            return '买入'
    for keyword in SELL_KEYWORDS:
        if keyword in value:
            return '卖出'
    return None


def _normalize_stock_code(code) -> str:
    """标准化股票代码为6位数字字符串"""
    code_str = str(code).strip()
    # 去除可能的前缀如 SH, SZ, .SH, .SZ 等
    code_str = re.sub(r'[.\-]?(SH|SZ|sh|sz|BJ|bj)', '', code_str)
    # 去除非数字字符
    code_str = re.sub(r'[^\d]', '', code_str)
    # 补齐到6位
    code_str = code_str.zfill(6)
    return code_str


def _parse_date(date_val) -> Optional[str]:
    """解析日期，统一输出 YYYY-MM-DD 格式"""
    if pd.isna(date_val):
        return None
    date_str = str(date_val).strip()
    # 尝试多种日期格式
    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%Y.%m.%d',
                '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S']:
        try:
            dt = pd.to_datetime(date_str, format=fmt)
            return dt.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            continue
    # 最后尝试 pandas 自动解析
    try:
        dt = pd.to_datetime(date_str)
        return dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return None


def _to_float(val, default=0.0) -> float:
    """安全转换为浮点数"""
    if pd.isna(val):
        return default
    try:
        # 处理可能的千分位逗号
        if isinstance(val, str):
            val = val.replace(',', '').strip()
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_csv(file_content: bytes, encoding: str = None) -> dict:
    """
    解析交割单 CSV 文件内容

    Args:
        file_content: CSV 文件的二进制内容
        encoding: 文件编码，为 None 时自动检测

    Returns:
        {
            'success': bool,
            'data': list[dict],  # 标准化后的交易记录
            'unmapped_columns': list,  # 未能映射的标准字段
            'original_columns': list,  # 原始列名
            'total_rows': int,
            'valid_rows': int,
            'message': str,
        }
    """
    # 尝试不同编码读取
    encodings = [encoding] if encoding else ['utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-8-sig']
    df = None

    for enc in encodings:
        if enc is None:
            continue
        try:
            df = pd.read_csv(io.BytesIO(file_content), encoding=enc, dtype=str)
            if len(df.columns) >= 3:  # 至少有3列才认为解析成功
                break
            df = None
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    if df is None:
        return {
            'success': False,
            'data': [],
            'unmapped_columns': [],
            'original_columns': [],
            'total_rows': 0,
            'valid_rows': 0,
            'message': '无法解析 CSV 文件，请检查文件格式和编码',
        }

    # 清理列名（去除空白）
    df.columns = [str(c).strip() for c in df.columns]
    original_columns = list(df.columns)

    # 自动匹配列名
    column_mapping = _find_column_mapping(df.columns)

    # 检查必要字段
    required_fields = ['trade_date', 'stock_code', 'direction', 'price', 'quantity']
    unmapped = [f for f in required_fields if f not in column_mapping]

    if unmapped:
        return {
            'success': False,
            'data': [],
            'unmapped_columns': [STANDARD_COLUMNS.get(f, f) for f in unmapped],
            'original_columns': original_columns,
            'total_rows': len(df),
            'valid_rows': 0,
            'message': f'无法自动识别以下字段：{", ".join(STANDARD_COLUMNS.get(f, f) for f in unmapped)}。原始列名为：{", ".join(original_columns)}',
        }

    # 标准化数据
    records = []
    for _, row in df.iterrows():
        # 解析买卖方向
        direction_raw = row.get(column_mapping.get('direction', ''), '')
        direction = _normalize_direction(str(direction_raw))
        if direction is None:
            continue  # 跳过非买卖记录（如分红、转账等）

        # 解析日期
        trade_date = _parse_date(row.get(column_mapping.get('trade_date', ''), ''))
        if trade_date is None:
            continue

        # 解析股票代码
        stock_code = _normalize_stock_code(row.get(column_mapping.get('stock_code', ''), ''))
        if not stock_code or stock_code == '000000':
            continue

        # 解析其他字段
        stock_name = str(row.get(column_mapping.get('stock_name', ''), '')).strip() if 'stock_name' in column_mapping else ''
        price = _to_float(row.get(column_mapping.get('price', ''), 0))
        quantity = abs(_to_float(row.get(column_mapping.get('quantity', ''), 0)))
        amount = abs(_to_float(row.get(column_mapping.get('amount', ''), 0)))
        commission = abs(_to_float(row.get(column_mapping.get('commission', ''), 0)))
        stamp_tax = abs(_to_float(row.get(column_mapping.get('stamp_tax', ''), 0)))
        transfer_fee = abs(_to_float(row.get(column_mapping.get('transfer_fee', ''), 0)))

        if price <= 0 or quantity <= 0:
            continue

        # 如果没有成交金额，用价格*数量计算
        if amount == 0:
            amount = price * quantity

        total_fee = commission + stamp_tax + transfer_fee

        records.append({
            'trade_date': trade_date,
            'stock_code': stock_code,
            'stock_name': stock_name,
            'direction': direction,
            'price': round(price, 3),
            'quantity': int(quantity),
            'amount': round(amount, 2),
            'commission': round(commission, 2),
            'stamp_tax': round(stamp_tax, 2),
            'transfer_fee': round(transfer_fee, 2),
            'total_fee': round(total_fee, 2),
        })

    return {
        'success': True,
        'data': records,
        'unmapped_columns': [],
        'original_columns': original_columns,
        'total_rows': len(df),
        'valid_rows': len(records),
        'message': f'成功解析 {len(records)} 条交易记录（共 {len(df)} 行）',
    }
