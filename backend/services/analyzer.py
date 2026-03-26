"""
交易风格分析引擎
接收 match_trades() 返回的交易数据，计算多维度分析指标 + 自动生成文字总结
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List


def analyze_trading_style(trade_result: Dict) -> Dict:
    """
    分析交易风格，返回结构化报告数据

    Args:
        trade_result: match_trades() 返回的完整结果

    Returns:
        包含各维度分析数据和文字总结的 dict
    """
    all_trades = trade_result.get('trades', [])
    profitable = trade_result.get('profitable', [])
    losing = trade_result.get('losing', [])
    stats = trade_result.get('stats', {})

    if not all_trades:
        return {'empty': True, 'message': '没有交易数据可供分析'}

    report = {
        'empty': False,
        'holding_days_dist': _calc_holding_days_dist(all_trades),
        'profit_pct_dist': _calc_profit_pct_dist(all_trades),
        'monthly_pnl': _calc_monthly_pnl(all_trades),
        'amount_trend': _calc_amount_trend(all_trades),
        'board_pref': _calc_board_preference(all_trades),
        'stock_top10': _calc_stock_top10(all_trades),
        'core_metrics': _calc_core_metrics(all_trades, profitable, losing, stats),
        'tags': _generate_tags(all_trades, profitable, losing, stats),
        'summary': _generate_summary(all_trades, profitable, losing, stats),
    }

    return report


def _calc_holding_days_dist(trades: List[Dict]) -> List[Dict]:
    """持仓天数分布"""
    buckets = [
        ('T+1 (1天)', lambda d: d <= 1),
        ('2-3天', lambda d: 2 <= d <= 3),
        ('4-7天', lambda d: 4 <= d <= 7),
        ('7天以上', lambda d: d > 7),
    ]

    total = len(trades)
    result = []
    for label, pred in buckets:
        count = sum(1 for t in trades if pred(t['holding_days']))
        pct = round(count / total * 100, 1) if total > 0 else 0
        result.append({'label': label, 'count': count, 'pct': pct})

    return result


def _calc_profit_pct_dist(trades: List[Dict]) -> List[Dict]:
    """盈亏幅度分布（7 档）"""
    buckets = [
        ('亏>10%', lambda p: p < -10),
        ('亏5~10%', lambda p: -10 <= p < -5),
        ('亏0~5%', lambda p: -5 <= p < 0),
        ('盈0~5%', lambda p: 0 <= p < 5),
        ('盈5~10%', lambda p: 5 <= p < 10),
        ('盈10~20%', lambda p: 10 <= p < 20),
        ('盈>20%', lambda p: p >= 20),
    ]

    result = []
    for label, pred in buckets:
        count = sum(1 for t in trades if pred(t['profit_pct']))
        result.append({'label': label, 'count': count})

    return result


def _calc_monthly_pnl(trades: List[Dict]) -> List[Dict]:
    """月度盈亏统计"""
    monthly = defaultdict(lambda: {'profit': 0, 'loss': 0, 'count': 0})

    for t in trades:
        month = t['sell_date'][:7]
        monthly[month]['count'] += 1
        if t['profit'] > 0:
            monthly[month]['profit'] += t['profit']
        else:
            monthly[month]['loss'] += t['profit']  # 负数

    result = []
    for month in sorted(monthly.keys()):
        d = monthly[month]
        net = d['profit'] + d['loss']
        result.append({
            'month': month,
            'profit': round(d['profit'], 2),
            'loss': round(d['loss'], 2),
            'net': round(net, 2),
            'count': d['count'],
        })

    return result


def _calc_amount_trend(trades: List[Dict]) -> List[Dict]:
    """按月平均单笔资金规模演变"""
    monthly = defaultdict(list)

    for t in trades:
        month = t['buy_date'][:7]
        monthly[month].append(t['buy_amount'])

    result = []
    for month in sorted(monthly.keys()):
        amounts = monthly[month]
        avg = round(sum(amounts) / len(amounts), 0)
        result.append({'month': month, 'avg_amount': avg})

    return result


def _calc_board_preference(trades: List[Dict]) -> List[Dict]:
    """板块偏好"""
    boards = {
        '沪市主板': 0,
        '深市主板': 0,
        '创业板': 0,
        '中小板': 0,
        '其他': 0,
    }

    for t in trades:
        code = t['stock_code']
        if code.startswith('6'):
            boards['沪市主板'] += 1
        elif code.startswith('002'):
            boards['中小板'] += 1
        elif code.startswith('30'):
            boards['创业板'] += 1
        elif code.startswith('00'):
            boards['深市主板'] += 1
        else:
            boards['其他'] += 1

    total = len(trades)
    result = []
    for label, count in boards.items():
        if count > 0:
            pct = round(count / total * 100, 1) if total > 0 else 0
            result.append({'label': label, 'count': count, 'pct': pct})

    return result


def _calc_stock_top10(trades: List[Dict]) -> List[Dict]:
    """个股盈亏 TOP10（按总盈亏绝对值排序）"""
    stock_map = defaultdict(lambda: {'name': '', 'count': 0, 'profit': 0})

    for t in trades:
        code = t['stock_code']
        stock_map[code]['name'] = t['stock_name'] or code
        stock_map[code]['count'] += 1
        stock_map[code]['profit'] += t['profit']

    items = []
    for code, d in stock_map.items():
        items.append({
            'name': d['name'],
            'code': code,
            'count': d['count'],
            'profit': round(d['profit'], 2),
        })

    # 按盈利金额降序
    items.sort(key=lambda x: x['profit'], reverse=True)
    return items[:10]


def _calc_core_metrics(trades, profitable, losing, stats) -> Dict:
    """核心指标汇总"""
    avg_profit_pct = (
        sum(t['profit_pct'] for t in profitable) / len(profitable)
        if profitable else 0
    )
    avg_loss_pct = (
        sum(t['profit_pct'] for t in losing) / len(losing)
        if losing else 0
    )
    pnl_ratio = round(abs(avg_profit_pct / avg_loss_pct), 2) if avg_loss_pct != 0 else 0

    avg_holding_all = (
        sum(t['holding_days'] for t in trades) / len(trades)
        if trades else 0
    )

    max_profit_trade = max(trades, key=lambda t: t['profit']) if trades else None
    max_loss_trade = min(trades, key=lambda t: t['profit']) if trades else None

    return {
        'win_rate': stats.get('win_rate', 0),
        'pnl_ratio': pnl_ratio,
        'avg_profit_pct': round(avg_profit_pct, 2),
        'avg_loss_pct': round(avg_loss_pct, 2),
        'avg_holding_days': round(avg_holding_all, 1),
        'total_trades': len(trades),
        'total_stocks': len(set(t['stock_code'] for t in trades)),
        'max_profit_trade': {
            'name': max_profit_trade['stock_name'],
            'profit': max_profit_trade['profit'],
            'profit_pct': max_profit_trade['profit_pct'],
        } if max_profit_trade else None,
        'max_loss_trade': {
            'name': max_loss_trade['stock_name'],
            'profit': max_loss_trade['profit'],
            'profit_pct': max_loss_trade['profit_pct'],
        } if max_loss_trade else None,
    }


def _generate_tags(trades, profitable, losing, stats) -> List[str]:
    """生成风格标签（3-5 个）"""
    tags = []
    total = len(trades)

    # 1. 持仓风格
    t1_count = sum(1 for t in trades if t['holding_days'] <= 1)
    short_count = sum(1 for t in trades if 2 <= t['holding_days'] <= 7)
    if t1_count / total > 0.6:
        tags.append('超短线')
    elif (t1_count + short_count) / total > 0.8:
        tags.append('短线交易')
    else:
        tags.append('波段交易')

    # 2. 胜率
    win_rate = stats.get('win_rate', 0)
    if win_rate >= 70:
        tags.append('高胜率')
    elif win_rate >= 55:
        tags.append('中等胜率')
    else:
        tags.append('低胜率')

    # 3. 盈亏比
    avg_p = sum(t['profit_pct'] for t in profitable) / len(profitable) if profitable else 0
    avg_l = sum(t['profit_pct'] for t in losing) / len(losing) if losing else 0
    if avg_l != 0:
        ratio = abs(avg_p / avg_l)
        if ratio >= 1.5:
            tags.append('高盈亏比')
        elif ratio < 0.8:
            tags.append('盈亏比偏低')

    # 4. 仓位趋势
    half = total // 2
    if half > 0:
        sorted_trades = sorted(trades, key=lambda t: t['buy_date'])
        early_avg = sum(t['buy_amount'] for t in sorted_trades[:half]) / half
        late_avg = sum(t['buy_amount'] for t in sorted_trades[half:]) / (total - half)
        if early_avg > 0 and late_avg / early_avg > 2:
            tags.append('仓位递增')
        elif early_avg > 0 and late_avg / early_avg < 0.5:
            tags.append('仓位递减')

    # 5. 交易频率
    if total > 0:
        dates = sorted(set(t['sell_date'] for t in trades))
        if len(dates) >= 2:
            d1 = datetime.strptime(dates[0], '%Y-%m-%d')
            d2 = datetime.strptime(dates[-1], '%Y-%m-%d')
            span_days = max((d2 - d1).days, 1)
            freq = total / (span_days / 30)
            if freq > 12:
                tags.append('高频交易')

    return tags


def _generate_summary(trades, profitable, losing, stats) -> Dict:
    """生成文字总结：优势 + 建议"""
    strengths = []
    suggestions = []
    total = len(trades)

    # 胜率分析
    win_rate = stats.get('win_rate', 0)
    if win_rate >= 60:
        strengths.append(f'胜率达到 {win_rate}%，选股成功率较高')
    else:
        suggestions.append(f'当前胜率 {win_rate}%，可进一步优化选股策略提升胜率')

    # 纪律性 - 持仓时间
    t1_count = sum(1 for t in trades if t['holding_days'] <= 1)
    t1_pct = t1_count / total * 100 if total > 0 else 0
    if t1_pct > 60:
        strengths.append(f'{t1_pct:.0f}% 的交易在 T+1 了结，执行纪律性强，不拖泥带水')

    # 盈亏比
    avg_p = sum(t['profit_pct'] for t in profitable) / len(profitable) if profitable else 0
    avg_l = sum(t['profit_pct'] for t in losing) / len(losing) if losing else 0
    if avg_l != 0:
        ratio = abs(avg_p / avg_l)
        if ratio >= 1.5:
            strengths.append(f'盈亏比 {ratio:.1f}，盈利交易的收益显著高于亏损幅度')
        elif ratio < 1.1:
            suggestions.append(
                f'盈亏比仅 {ratio:.2f}（平均盈 +{avg_p:.1f}% vs 平均亏 {avg_l:.1f}%），'
                f'建议拉大止盈空间或收紧止损位'
            )

    # 止损
    max_loss_pct = min((t['profit_pct'] for t in losing), default=0)
    if max_loss_pct < -20:
        suggestions.append(
            f'最大单笔亏损达 {max_loss_pct:.1f}%，建议设置 5~8% 的硬止损线，'
            f'避免单笔巨亏侵蚀整体盈利'
        )
    elif max_loss_pct < -10:
        suggestions.append(
            f'最大单笔亏损 {max_loss_pct:.1f}%，止损基本到位，可进一步收紧至 5~8%'
        )

    # 仓位管理
    half = total // 2
    if half > 0:
        sorted_trades = sorted(trades, key=lambda t: t['buy_date'])
        early_avg = sum(t['buy_amount'] for t in sorted_trades[:half]) / half
        late_avg = sum(t['buy_amount'] for t in sorted_trades[half:]) / (total - half)
        if early_avg > 0 and late_avg / early_avg > 2:
            suggestions.append(
                f'后期平均单笔金额({late_avg:.0f}元)是前期({early_avg:.0f}元)的 '
                f'{late_avg/early_avg:.1f} 倍，仓位增长过快，'
                f'建议控制单笔金额不超过总资金的固定比例'
            )

    # 分散度
    stock_count = len(set(t['stock_code'] for t in trades))
    if stock_count > total * 0.7:
        strengths.append(f'涉及 {stock_count} 只不同股票，选股范围广，不过度集中')

    # 交易频率
    dates = sorted(set(t['sell_date'] for t in trades))
    if len(dates) >= 2:
        d1 = datetime.strptime(dates[0], '%Y-%m-%d')
        d2 = datetime.strptime(dates[-1], '%Y-%m-%d')
        span_months = max((d2 - d1).days / 30, 1)
        freq = total / span_months
        if freq > 15:
            suggestions.append(
                f'交易频率较高（月均 {freq:.0f} 笔），频繁交易会增加手续费成本，'
                f'建议适当精选交易机会'
            )

    return {
        'strengths': strengths,
        'suggestions': suggestions,
    }
