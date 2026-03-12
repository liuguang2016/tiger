"""
A 股盈利交易技术分析系统 - Flask 主应用
"""

from flask import Flask, request, jsonify, send_from_directory
import os
import logging

from services.parser import parse_csv
from services.matcher import match_trades
from services.stock_data import fetch_kline_data
from services.analyzer import analyze_trading_style
from services.screener import start_screening, get_screening_status, fetch_index_info
from services.crypto_trader import get_bot
from services.crypto_backtest import start_backtest, get_backtest_status
from services.binance_client import BinanceClient
from services import database as db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
)

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 上传限制

# 启动时初始化数据库
db.init_db()


@app.route('/')
def index():
    """首页"""
    return send_from_directory('static', 'index.html')


@app.route('/api/upload', methods=['POST'])
def upload_csv():
    """
    上传交割单 CSV 文件
    每次上传先清空旧数据，然后解析 -> 配对 -> 存入 SQLite
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '请上传 CSV 文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({'success': False, 'message': '请上传 CSV 格式文件'}), 400

    # 读取文件内容
    file_content = file.read()

    # 解析 CSV
    parse_result = parse_csv(file_content)

    if not parse_result['success']:
        return jsonify(parse_result), 400

    # 配对交易并计算盈亏
    records = parse_result['data']
    trade_result = match_trades(records)

    # ---- 写入数据库（先清空旧数据）----
    db.clear_all()
    db.save_raw_records(records)
    db.save_matched_trades(trade_result['trades'])
    db.save_stats(trade_result['stats'])

    return jsonify({
        'success': True,
        'message': parse_result['message'],
        'parse_info': {
            'total_rows': parse_result['total_rows'],
            'valid_rows': parse_result['valid_rows'],
        },
        'trades': trade_result['profitable'],  # 默认只返回盈利交易
        'stats': trade_result['stats'],
    })


@app.route('/api/trades')
def get_trades():
    """
    获取交易列表
    参数: type=profitable|losing|all (默认 profitable)
    """
    if not db.has_data():
        return jsonify({'success': False, 'message': '请先上传交割单'}), 400

    trade_type = request.args.get('type', 'profitable')
    trades = db.get_trades(trade_type)
    stats = db.get_stats() or {}

    return jsonify({
        'success': True,
        'trades': trades,
        'stats': stats,
    })


@app.route('/api/kline')
def get_kline():
    """
    获取指定交易的 K 线数据
    参数:
        stock_code: 股票代码（必需）
        buy_date: 买入日期（可选，选股模式下不传）
        sell_date: 卖出日期（可选，选股模式下不传）
    """
    stock_code = request.args.get('stock_code', '').strip()
    buy_date = request.args.get('buy_date', '').strip()
    sell_date = request.args.get('sell_date', '').strip()

    if not stock_code:
        return jsonify({
            'success': False,
            'message': '缺少参数：stock_code',
        }), 400

    if not buy_date or not sell_date:
        from datetime import datetime, timedelta
        sell_date = datetime.now().strftime('%Y-%m-%d')
        buy_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

    kline_data = fetch_kline_data(stock_code, buy_date, sell_date)

    if not kline_data['success']:
        return jsonify(kline_data), 500

    kline_data['buy_date'] = request.args.get('buy_date', '').strip() or ''
    kline_data['sell_date'] = request.args.get('sell_date', '').strip() or ''

    return jsonify(kline_data)


@app.route('/api/report')
def get_report():
    """
    生成交易风格分析报告
    从数据库读取交易数据，调用 analyzer 分析
    """
    if not db.has_data():
        return jsonify({'success': False, 'message': '请先上传交割单'}), 400

    trade_result = db.get_trade_result_for_report()
    report = analyze_trading_style(trade_result)
    return jsonify({'success': True, 'report': report})


@app.route('/api/screener/run', methods=['POST'])
def run_screener():
    """启动弹簧选股筛选任务"""
    params = request.get_json(silent=True) or {}
    task_id = start_screening(params)
    return jsonify({'success': True, 'task_id': task_id})


_screener_saved_task_id = None

@app.route('/api/screener/status')
def screener_status():
    """获取筛选任务进度和结果"""
    global _screener_saved_task_id
    status = get_screening_status()

    if status['status'] == 'done' and status['results'] and \
       status.get('task_id') != _screener_saved_task_id:
        db.save_pool_stocks(status['results'])
        _screener_saved_task_id = status.get('task_id')

    return jsonify({
        'success': True,
        'status': status['status'],
        'progress': status['progress'],
        'total': status['total'],
        'found': status['found'],
        'message': status['message'],
        'index_info': status.get('index_info', {}),
        'results': status['results'] if status['status'] == 'done' else [],
    })


@app.route('/api/screener/index')
def get_index():
    """获取大盘指数信息"""
    info = fetch_index_info()
    return jsonify({'success': True, 'index': info})


@app.route('/api/screener/pool')
def get_pool():
    """获取交易池列表"""
    stocks = db.get_pool_stocks()
    return jsonify({'success': True, 'stocks': stocks})


@app.route('/api/screener/pool/<stock_code>', methods=['DELETE'])
def remove_from_pool(stock_code):
    """从交易池移除一只股票"""
    db.remove_pool_stock(stock_code)
    return jsonify({'success': True})


@app.route('/api/screener/pool', methods=['DELETE'])
def clear_pool_api():
    """清空交易池"""
    db.clear_pool()
    return jsonify({'success': True})


# ============================
# 数字货币 API
# ============================

@app.route('/api/crypto/config', methods=['GET'])
def get_crypto_config():
    """获取加密货币配置（密钥脱敏）"""
    cfg = db.get_crypto_config()
    if not cfg:
        return jsonify({'success': True, 'config': None})
    masked_key = cfg['api_key'][-4:].rjust(len(cfg['api_key']), '*') if cfg['api_key'] else ''
    return jsonify({
        'success': True,
        'config': {
            'api_key': masked_key,
            'has_secret': bool(cfg['api_secret']),
            'is_running': cfg['is_running'],
            'params': cfg['config'],
            'updated_at': cfg['updated_at'],
        },
    })


@app.route('/api/crypto/config', methods=['POST'])
def save_crypto_config():
    """保存 API 密钥和策略参数"""
    data = request.get_json(silent=True) or {}
    api_key = data.get('api_key', '').strip()
    api_secret = data.get('api_secret', '').strip()
    params = data.get('params', {})

    if not api_key or not api_secret:
        return jsonify({'success': False, 'message': '请输入 API Key 和 Secret'}), 400

    db.save_crypto_config(api_key, api_secret, params)

    bot = get_bot()
    bot.configure(api_key, api_secret, params)

    connected = bot.client.test_connectivity() if bot.client else False
    auth_ok = bot.client.test_auth() if connected and bot.client else False

    return jsonify({
        'success': True,
        'connected': connected,
        'auth_ok': auth_ok,
    })


@app.route('/api/crypto/bot/start', methods=['POST'])
def start_crypto_bot():
    """启动交易机器人"""
    data = request.get_json(silent=True) or {}
    bot = get_bot()

    if data.get('params'):
        cfg = db.get_crypto_config()
        if cfg:
            bot.configure(cfg['api_key'], cfg['api_secret'], data['params'])
            db.save_crypto_config(cfg['api_key'], cfg['api_secret'], data['params'])

    ok = bot.start()
    if not ok:
        return jsonify({'success': False, 'message': bot.error_msg}), 400
    return jsonify({'success': True})


@app.route('/api/crypto/bot/stop', methods=['POST'])
def stop_crypto_bot():
    """停止交易机器人"""
    bot = get_bot()
    bot.stop()
    return jsonify({'success': True})


@app.route('/api/crypto/bot/status')
def crypto_bot_status():
    """获取机器人状态"""
    bot = get_bot()
    status = bot.get_status()
    return jsonify({'success': True, **status})


@app.route('/api/crypto/bot/scan', methods=['POST'])
def crypto_manual_scan():
    """手动扫描信号"""
    bot = get_bot()
    if not bot.client:
        return jsonify({'success': False, 'message': '请先配置 API Key'}), 400
    signals = bot.manual_scan()
    return jsonify({'success': True, 'signals': signals})


@app.route('/api/crypto/trades')
def get_crypto_trades():
    """获取加密货币交易记录"""
    limit = request.args.get('limit', 100, type=int)
    symbol = request.args.get('symbol', '').strip() or None
    trades = db.get_crypto_trades(limit=limit, symbol=symbol)
    stats = db.get_crypto_trade_stats()
    return jsonify({'success': True, 'trades': trades, 'stats': stats})


@app.route('/api/crypto/kline')
def get_crypto_kline():
    """获取加密货币K线数据"""
    symbol = request.args.get('symbol', '').strip()
    interval = request.args.get('interval', '4h').strip()
    limit = request.args.get('limit', 200, type=int)

    if not symbol:
        return jsonify({'success': False, 'message': '缺少 symbol 参数'}), 400

    try:
        client = BinanceClient()
        raw = client.get_klines(symbol, interval, limit)
        if not raw:
            return jsonify({'success': False, 'message': '无K线数据'}), 404

        dates = []
        ohlcv = []
        volumes = []
        closes_arr = []

        for k in raw:
            from datetime import datetime as dt
            ts = int(k[0]) / 1000
            date_str = dt.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            o, h, l, c, v = float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])
            dates.append(date_str)
            ohlcv.append([o, c, l, h])
            volumes.append(v)
            closes_arr.append(c)

        import pandas as pd
        s = pd.Series(closes_arr)
        ma7 = s.rolling(7).mean().round(4).tolist()
        ma25 = s.rolling(25).mean().round(4).tolist()
        ma99 = s.rolling(99).mean().round(4).tolist()

        ma7 = [None if pd.isna(v) else v for v in ma7]
        ma25 = [None if pd.isna(v) else v for v in ma25]
        ma99 = [None if pd.isna(v) else v for v in ma99]

        return jsonify({
            'success': True,
            'symbol': symbol,
            'dates': dates,
            'ohlcv': ohlcv,
            'volumes': volumes,
            'ma7': ma7,
            'ma25': ma25,
            'ma99': ma99,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================
# 回测 API
# ============================

@app.route('/api/crypto/backtest/run', methods=['POST'])
def run_backtest_api():
    """启动回测任务"""
    params = request.get_json(silent=True) or {}
    run_id = start_backtest(params)
    return jsonify({'success': True, 'run_id': run_id})


@app.route('/api/crypto/backtest/status')
def backtest_status_api():
    """回测进度和结果"""
    status = get_backtest_status()
    return jsonify({
        'success': True,
        'status': status['status'],
        'progress': status['progress'],
        'total': status['total'],
        'message': status['message'],
        'summary': status['summary'] if status['status'] == 'done' else {},
        'equity': status['equity'] if status['status'] == 'done' else [],
        'trades': status['trades'] if status['status'] == 'done' else [],
    })


@app.route('/api/crypto/backtest/history')
def backtest_history_api():
    """历史回测记录"""
    limit = request.args.get('limit', 20, type=int)
    runs = db.get_backtest_history(limit=limit)
    return jsonify({'success': True, 'runs': runs})


@app.route('/api/crypto/backtest/<run_id>')
def backtest_detail_api(run_id):
    """获取某次回测的详细结果"""
    run = db.get_backtest_run(run_id)
    if not run:
        return jsonify({'success': False, 'message': '回测记录不存在'}), 404
    trades = db.get_backtest_trades(run_id)
    run['trades'] = trades
    return jsonify({'success': True, 'run': run})


if __name__ == '__main__':
    print("=" * 50)
    print("  Tigger - A 股 & 数字货币交易分析系统")
    print("  访问地址: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host='127.0.0.1', port=5000)
