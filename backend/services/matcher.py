"""
买卖配对与盈亏计算模块
使用 FIFO（先进先出）方法配对买入和卖出交易
"""

from collections import defaultdict, deque
from datetime import datetime
from typing import List, Dict


def match_trades(records: List[Dict]) -> Dict:
    """
    将交易记录按 FIFO 方式配对买入和卖出

    Args:
        records: parser.parse_csv 返回的标准化交易记录列表

    Returns:
        {
            'trades': list[dict],       # 所有已配对的完整交易
            'profitable': list[dict],   # 盈利交易
            'losing': list[dict],       # 亏损交易
            'open_positions': list[dict],  # 未平仓（只有买入没卖出的）
            'stats': dict,              # 统计信息
        }
    """
    # 按股票代码分组
    grouped = defaultdict(list)
    for record in records:
        grouped[record['stock_code']].append(record)

    all_trades = []

    for stock_code, stock_records in grouped.items():
        # 按日期排序
        stock_records.sort(key=lambda x: x['trade_date'])

        # FIFO 队列：存放待配对的买入记录
        buy_queue = deque()

        for record in stock_records:
            if record['direction'] == '买入':
                buy_queue.append({
                    'date': record['trade_date'],
                    'price': record['price'],
                    'quantity': record['quantity'],
                    'amount': record['amount'],
                    'fee': record['total_fee'],
                    'stock_code': record['stock_code'],
                    'stock_name': record['stock_name'],
                    'remaining': record['quantity'],  # 剩余未配对数量
                })
            elif record['direction'] == '卖出':
                sell_quantity = record['quantity']
                sell_price = record['price']
                sell_date = record['trade_date']
                sell_fee = record['total_fee']
                sell_amount = record['amount']

                # 按 FIFO 配对
                while sell_quantity > 0 and buy_queue:
                    buy = buy_queue[0]
                    match_qty = min(buy['remaining'], sell_quantity)

                    if match_qty <= 0:
                        buy_queue.popleft()
                        continue

                    # 计算配对交易的盈亏
                    buy_cost = buy['price'] * match_qty
                    sell_revenue = sell_price * match_qty

                    # 按比例分摊手续费
                    buy_fee_ratio = match_qty / buy['quantity'] if buy['quantity'] > 0 else 0
                    sell_fee_ratio = match_qty / record['quantity'] if record['quantity'] > 0 else 0
                    buy_fee_share = buy['fee'] * buy_fee_ratio
                    sell_fee_share = sell_fee * sell_fee_ratio
                    total_fee = buy_fee_share + sell_fee_share

                    profit = sell_revenue - buy_cost - total_fee
                    profit_pct = (profit / buy_cost * 100) if buy_cost > 0 else 0

                    # 计算持仓天数
                    try:
                        buy_dt = datetime.strptime(buy['date'], '%Y-%m-%d')
                        sell_dt = datetime.strptime(sell_date, '%Y-%m-%d')
                        holding_days = (sell_dt - buy_dt).days
                    except ValueError:
                        holding_days = 0

                    trade = {
                        'stock_code': stock_code,
                        'stock_name': buy['stock_name'],
                        'buy_date': buy['date'],
                        'buy_price': round(buy['price'], 3),
                        'sell_date': sell_date,
                        'sell_price': round(sell_price, 3),
                        'quantity': int(match_qty),
                        'buy_amount': round(buy_cost, 2),
                        'sell_amount': round(sell_revenue, 2),
                        'total_fee': round(total_fee, 2),
                        'profit': round(profit, 2),
                        'profit_pct': round(profit_pct, 2),
                        'holding_days': holding_days,
                    }
                    all_trades.append(trade)

                    # 更新剩余数量
                    buy['remaining'] -= match_qty
                    sell_quantity -= match_qty

                    if buy['remaining'] <= 0:
                        buy_queue.popleft()

    # 按卖出日期排序
    all_trades.sort(key=lambda x: x['sell_date'], reverse=True)

    # 分离盈利和亏损交易
    profitable = [t for t in all_trades if t['profit'] > 0]
    losing = [t for t in all_trades if t['profit'] <= 0]

    # 计算统计信息
    stats = _compute_stats(all_trades, profitable, losing)

    return {
        'trades': all_trades,
        'profitable': profitable,
        'losing': losing,
        'stats': stats,
    }


def _compute_stats(all_trades: list, profitable: list, losing: list) -> dict:
    """计算交易统计信息"""
    if not all_trades:
        return {
            'total_trades': 0,
            'profitable_count': 0,
            'losing_count': 0,
            'win_rate': 0,
            'total_profit': 0,
            'total_loss': 0,
            'net_profit': 0,
            'avg_profit': 0,
            'avg_loss': 0,
            'avg_profit_pct': 0,
            'avg_holding_days': 0,
            'max_profit': 0,
            'max_loss': 0,
            'monthly_stats': {},
            'stock_stats': {},
        }

    total_profit = sum(t['profit'] for t in profitable) if profitable else 0
    total_loss = sum(t['profit'] for t in losing) if losing else 0
    net_profit = total_profit + total_loss

    avg_profit = total_profit / len(profitable) if profitable else 0
    avg_loss = total_loss / len(losing) if losing else 0
    avg_profit_pct = (
        sum(t['profit_pct'] for t in profitable) / len(profitable)
        if profitable else 0
    )
    avg_holding_days = (
        sum(t['holding_days'] for t in profitable) / len(profitable)
        if profitable else 0
    )

    max_profit = max((t['profit'] for t in profitable), default=0)
    max_loss = min((t['profit'] for t in losing), default=0)

    # 按月份统计（仅盈利交易）
    monthly_stats = defaultdict(lambda: {'count': 0, 'profit': 0})
    for t in profitable:
        month = t['sell_date'][:7]  # YYYY-MM
        monthly_stats[month]['count'] += 1
        monthly_stats[month]['profit'] += t['profit']

    # 四舍五入月度统计
    monthly_stats = {
        k: {'count': v['count'], 'profit': round(v['profit'], 2)}
        for k, v in sorted(monthly_stats.items())
    }

    # 按个股统计（盈利交易）
    stock_stats = defaultdict(lambda: {'count': 0, 'profit': 0, 'stock_name': ''})
    for t in profitable:
        code = t['stock_code']
        stock_stats[code]['count'] += 1
        stock_stats[code]['profit'] += t['profit']
        stock_stats[code]['stock_name'] = t['stock_name']

    # 按盈利金额排序
    stock_stats = dict(
        sorted(stock_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    )
    stock_stats = {
        k: {'count': v['count'], 'profit': round(v['profit'], 2), 'stock_name': v['stock_name']}
        for k, v in stock_stats.items()
    }

    return {
        'total_trades': len(all_trades),
        'profitable_count': len(profitable),
        'losing_count': len(losing),
        'win_rate': round(len(profitable) / len(all_trades) * 100, 1) if all_trades else 0,
        'total_profit': round(total_profit, 2),
        'total_loss': round(total_loss, 2),
        'net_profit': round(net_profit, 2),
        'avg_profit': round(avg_profit, 2),
        'avg_loss': round(avg_loss, 2),
        'avg_profit_pct': round(avg_profit_pct, 2),
        'avg_holding_days': round(avg_holding_days, 1),
        'max_profit': round(max_profit, 2),
        'max_loss': round(max_loss, 2),
        'monthly_stats': monthly_stats,
        'stock_stats': stock_stats,
    }
