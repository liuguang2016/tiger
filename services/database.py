"""
SQLite 数据库模块
存储交割单原始记录、配对交易、统计信息
"""

import sqlite3
import json
import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 数据库文件放在项目根目录下的 data 文件夹
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
DB_PATH = os.path.join(DB_DIR, 'trades.db')


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 让查询结果可按列名访问
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = _get_conn()
    try:
        conn.executescript("""
            -- 原始交易记录表
            CREATE TABLE IF NOT EXISTS raw_records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date  TEXT NOT NULL,
                stock_code  TEXT NOT NULL,
                stock_name  TEXT DEFAULT '',
                direction   TEXT NOT NULL,      -- '买入' / '卖出'
                price       REAL NOT NULL,
                quantity    INTEGER NOT NULL,
                amount      REAL NOT NULL,
                commission  REAL DEFAULT 0,
                stamp_tax   REAL DEFAULT 0,
                transfer_fee REAL DEFAULT 0,
                total_fee   REAL DEFAULT 0
            );

            -- 配对交易表
            CREATE TABLE IF NOT EXISTS matched_trades (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code   TEXT NOT NULL,
                stock_name   TEXT DEFAULT '',
                buy_date     TEXT NOT NULL,
                buy_price    REAL NOT NULL,
                sell_date    TEXT NOT NULL,
                sell_price   REAL NOT NULL,
                quantity     INTEGER NOT NULL,
                buy_amount   REAL NOT NULL,
                sell_amount  REAL NOT NULL,
                total_fee    REAL DEFAULT 0,
                profit       REAL NOT NULL,
                profit_pct   REAL NOT NULL,
                holding_days INTEGER NOT NULL
            );

            -- 统计信息表（只存一行，每次上传覆盖）
            CREATE TABLE IF NOT EXISTS trade_stats (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                stats_json      TEXT NOT NULL,       -- JSON 格式完整统计
                upload_time     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            -- 选股交易池表
            CREATE TABLE IF NOT EXISTS stock_pool (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code  TEXT NOT NULL,
                stock_name  TEXT DEFAULT '',
                add_date    TEXT NOT NULL DEFAULT (date('now','localtime')),
                score       REAL DEFAULT 0,
                drop_pct    REAL DEFAULT 0,
                volume_ratio REAL DEFAULT 0,
                close_price REAL DEFAULT 0,
                change_pct  REAL DEFAULT 0,
                reason      TEXT DEFAULT '',
                status      TEXT DEFAULT 'active',
                UNIQUE(stock_code, add_date)
            );

            -- 创建索引加速查询
            CREATE INDEX IF NOT EXISTS idx_matched_profit ON matched_trades(profit);
            CREATE INDEX IF NOT EXISTS idx_matched_sell_date ON matched_trades(sell_date);
            CREATE INDEX IF NOT EXISTS idx_matched_stock_code ON matched_trades(stock_code);
            CREATE INDEX IF NOT EXISTS idx_pool_status ON stock_pool(status);
            CREATE INDEX IF NOT EXISTS idx_pool_date ON stock_pool(add_date);
        """)
        conn.commit()
        logger.info("数据库初始化完成: %s", DB_PATH)
    finally:
        conn.close()


def clear_all():
    """清空所有数据（上传新交割单前调用）"""
    conn = _get_conn()
    try:
        conn.executescript("""
            DELETE FROM raw_records;
            DELETE FROM matched_trades;
            DELETE FROM trade_stats;
        """)
        conn.commit()
        logger.info("已清空所有旧数据")
    finally:
        conn.close()


def save_raw_records(records: List[Dict]):
    """批量写入原始交易记录"""
    conn = _get_conn()
    try:
        conn.executemany(
            """INSERT INTO raw_records
               (trade_date, stock_code, stock_name, direction,
                price, quantity, amount, commission, stamp_tax,
                transfer_fee, total_fee)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    r['trade_date'], r['stock_code'], r['stock_name'],
                    r['direction'], r['price'], r['quantity'], r['amount'],
                    r['commission'], r['stamp_tax'], r['transfer_fee'],
                    r['total_fee'],
                )
                for r in records
            ]
        )
        conn.commit()
        logger.info("写入 %d 条原始记录", len(records))
    finally:
        conn.close()


def save_matched_trades(trades: List[Dict]):
    """批量写入配对交易"""
    conn = _get_conn()
    try:
        conn.executemany(
            """INSERT INTO matched_trades
               (stock_code, stock_name, buy_date, buy_price,
                sell_date, sell_price, quantity, buy_amount,
                sell_amount, total_fee, profit, profit_pct, holding_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    t['stock_code'], t['stock_name'], t['buy_date'],
                    t['buy_price'], t['sell_date'], t['sell_price'],
                    t['quantity'], t['buy_amount'], t['sell_amount'],
                    t['total_fee'], t['profit'], t['profit_pct'],
                    t['holding_days'],
                )
                for t in trades
            ]
        )
        conn.commit()
        logger.info("写入 %d 条配对交易", len(trades))
    finally:
        conn.close()


def save_stats(stats: Dict):
    """保存统计信息（UPSERT）"""
    conn = _get_conn()
    try:
        stats_json = json.dumps(stats, ensure_ascii=False)
        conn.execute(
            """INSERT INTO trade_stats (id, stats_json)
               VALUES (1, ?)
               ON CONFLICT(id) DO UPDATE SET
                   stats_json = excluded.stats_json,
                   upload_time = datetime('now', 'localtime')""",
            (stats_json,)
        )
        conn.commit()
        logger.info("统计信息已保存")
    finally:
        conn.close()


# ====== 查询函数 ======

def has_data() -> bool:
    """检查数据库中是否有交易数据"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) FROM matched_trades").fetchone()
        return row[0] > 0
    finally:
        conn.close()


def get_trades(trade_type: str = 'profitable') -> List[Dict]:
    """
    获取配对交易列表

    Args:
        trade_type: 'profitable' | 'losing' | 'all'
    """
    conn = _get_conn()
    try:
        if trade_type == 'profitable':
            rows = conn.execute(
                "SELECT * FROM matched_trades WHERE profit > 0 ORDER BY sell_date DESC"
            ).fetchall()
        elif trade_type == 'losing':
            rows = conn.execute(
                "SELECT * FROM matched_trades WHERE profit <= 0 ORDER BY sell_date DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM matched_trades ORDER BY sell_date DESC"
            ).fetchall()

        return [_row_to_trade_dict(r) for r in rows]
    finally:
        conn.close()


def get_stats() -> Optional[Dict]:
    """获取统计信息"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT stats_json FROM trade_stats WHERE id = 1").fetchone()
        if row:
            return json.loads(row['stats_json'])
        return None
    finally:
        conn.close()


def get_trade_result_for_report() -> Dict:
    """
    获取 analyzer 需要的完整交易数据结构
    返回与 match_trades() 相同格式的 dict
    """
    conn = _get_conn()
    try:
        all_rows = conn.execute(
            "SELECT * FROM matched_trades ORDER BY sell_date DESC"
        ).fetchall()
        all_trades = [_row_to_trade_dict(r) for r in all_rows]

        profitable = [t for t in all_trades if t['profit'] > 0]
        losing = [t for t in all_trades if t['profit'] <= 0]

        stats_row = conn.execute(
            "SELECT stats_json FROM trade_stats WHERE id = 1"
        ).fetchone()
        stats = json.loads(stats_row['stats_json']) if stats_row else {}

        return {
            'trades': all_trades,
            'profitable': profitable,
            'losing': losing,
            'stats': stats,
        }
    finally:
        conn.close()


def _row_to_trade_dict(row: sqlite3.Row) -> Dict:
    """将数据库行转为交易 dict"""
    return {
        'stock_code': row['stock_code'],
        'stock_name': row['stock_name'],
        'buy_date': row['buy_date'],
        'buy_price': row['buy_price'],
        'sell_date': row['sell_date'],
        'sell_price': row['sell_price'],
        'quantity': row['quantity'],
        'buy_amount': row['buy_amount'],
        'sell_amount': row['sell_amount'],
        'total_fee': row['total_fee'],
        'profit': row['profit'],
        'profit_pct': row['profit_pct'],
        'holding_days': row['holding_days'],
    }


# ====== 选股交易池 ======

def save_pool_stocks(stocks: List[Dict]):
    """批量写入选股交易池（同一天同一只股票不重复插入）"""
    conn = _get_conn()
    try:
        conn.executemany(
            """INSERT OR REPLACE INTO stock_pool
               (stock_code, stock_name, add_date, score, drop_pct,
                volume_ratio, close_price, change_pct, reason, status)
               VALUES (?, ?, date('now','localtime'), ?, ?, ?, ?, ?, ?, 'active')""",
            [
                (
                    s['stock_code'], s['stock_name'], s['score'],
                    s['drop_pct'], s['volume_ratio'], s.get('close', 0),
                    s.get('change_pct', 0), s.get('reason', ''),
                )
                for s in stocks
            ]
        )
        conn.commit()
        logger.info("交易池写入 %d 只股票", len(stocks))
    finally:
        conn.close()


def get_pool_stocks() -> List[Dict]:
    """获取交易池中所有 active 股票，按评分降序"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM stock_pool
               WHERE status = 'active'
               ORDER BY score DESC"""
        ).fetchall()
        return [_row_to_pool_dict(r) for r in rows]
    finally:
        conn.close()


def remove_pool_stock(stock_code: str):
    """从交易池移除一只股票"""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE stock_pool SET status = 'removed' WHERE stock_code = ? AND status = 'active'",
            (stock_code,)
        )
        conn.commit()
    finally:
        conn.close()


def clear_pool():
    """清空交易池"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM stock_pool")
        conn.commit()
        logger.info("交易池已清空")
    finally:
        conn.close()


def _row_to_pool_dict(row: sqlite3.Row) -> Dict:
    """将数据库行转为交易池 dict"""
    return {
        'id': row['id'],
        'stock_code': row['stock_code'],
        'stock_name': row['stock_name'],
        'add_date': row['add_date'],
        'score': row['score'],
        'drop_pct': row['drop_pct'],
        'volume_ratio': row['volume_ratio'],
        'close_price': row['close_price'],
        'change_pct': row['change_pct'],
        'reason': row['reason'],
    }
