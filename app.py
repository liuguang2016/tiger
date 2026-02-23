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


if __name__ == '__main__':
    print("=" * 50)
    print("  A 股盈利交易技术分析系统")
    print("  访问地址: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host='127.0.0.1', port=5000)
