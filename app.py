"""
A 股盈利交易技术分析系统 - Flask 主应用
"""

from flask import Flask, request, jsonify, send_from_directory
import os
import json

from services.parser import parse_csv
from services.matcher import match_trades
from services.stock_data import fetch_kline_data

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 上传限制

# 全局存储当前会话的交易数据（单用户简化版）
_session_data = {
    'records': [],       # 解析后的原始交易记录
    'trade_result': {},  # 配对后的交易结果
}


@app.route('/')
def index():
    """首页"""
    return send_from_directory('static', 'index.html')


@app.route('/api/upload', methods=['POST'])
def upload_csv():
    """
    上传交割单 CSV 文件
    返回解析结果和盈利交易列表
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

    # 存储到会话
    _session_data['records'] = records
    _session_data['trade_result'] = trade_result

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
    trade_type = request.args.get('type', 'profitable')
    trade_result = _session_data.get('trade_result', {})

    if not trade_result:
        return jsonify({'success': False, 'message': '请先上传交割单'}), 400

    if trade_type == 'profitable':
        trades = trade_result.get('profitable', [])
    elif trade_type == 'losing':
        trades = trade_result.get('losing', [])
    else:
        trades = trade_result.get('trades', [])

    return jsonify({
        'success': True,
        'trades': trades,
        'stats': trade_result.get('stats', {}),
    })


@app.route('/api/kline')
def get_kline():
    """
    获取指定交易的 K 线数据
    参数:
        stock_code: 股票代码
        buy_date: 买入日期
        sell_date: 卖出日期
    """
    stock_code = request.args.get('stock_code', '').strip()
    buy_date = request.args.get('buy_date', '').strip()
    sell_date = request.args.get('sell_date', '').strip()

    if not all([stock_code, buy_date, sell_date]):
        return jsonify({
            'success': False,
            'message': '缺少参数：stock_code, buy_date, sell_date',
        }), 400

    # 获取 K 线数据
    kline_data = fetch_kline_data(stock_code, buy_date, sell_date)

    if not kline_data['success']:
        return jsonify(kline_data), 500

    # 附带买入/卖出标记信息
    kline_data['buy_date'] = buy_date
    kline_data['sell_date'] = sell_date

    return jsonify(kline_data)


if __name__ == '__main__':
    print("=" * 50)
    print("  A 股盈利交易技术分析系统")
    print("  访问地址: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, host='127.0.0.1', port=5000)
