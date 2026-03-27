"""
PostgreSQL 数据库模块 (从 SQLite 迁移)
存储交割单原始记录、配对交易、统计信息
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2 import pool

logger = logging.getLogger(__name__)

# 数据库连接池
_connection_pool: Optional[pool.ThreadedConnectionPool] = None

# SQLite 路径 (迁移用)
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
DB_PATH = os.path.join(DB_DIR, 'trades.db')


def _get_DATABASE_URL() -> str:
    """获取 DATABASE_URL 环境变量"""
    return os.environ.get(
        'DATABASE_URL',
        f"postgresql://{os.environ.get('POSTGRES_USER', 'tigger')}:{os.environ.get('POSTGRES_PASSWORD', 'postgres')}@"
        f"{os.environ.get('POSTGRES_HOST', 'postgres')}:{os.environ.get('POSTGRES_PORT', '5432')}/"
        f"{os.environ.get('POSTGRES_DB', 'tigger')}"
    )


def _get_pool() -> pool.ThreadedConnectionPool:
    """获取或创建连接池"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=_get_DATABASE_URL()
        )
    return _connection_pool


def _get_conn():
    """获取数据库连接"""
    return _get_pool().getconn()


def _release_conn(conn):
    """释放连接回池"""
    _get_pool().putconn(conn)


def _row_to_dict(cursor, row: tuple) -> Dict:
    """将数据库行转为字典"""
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def _row_to_trade_dict(row: tuple, cursor) -> Dict:
    """将数据库行转为交易 dict"""
    d = _row_to_dict(cursor, row)
    return {
        'stock_code': d['stock_code'],
        'stock_name': d['stock_name'],
        'buy_date': d['buy_date'],
        'buy_price': d['buy_price'],
        'sell_date': d['sell_date'],
        'sell_price': d['sell_price'],
        'quantity': d['quantity'],
        'buy_amount': d['buy_amount'],
        'sell_amount': d['sell_amount'],
        'total_fee': d['total_fee'],
        'profit': d['profit'],
        'profit_pct': d['profit_pct'],
        'holding_days': d['holding_days'],
    }


def _row_to_pool_dict(row: tuple, cursor) -> Dict:
    """将数据库行转为交易池 dict"""
    d = _row_to_dict(cursor, row)
    tags_raw = d.get('tags', '[]')
    try:
        tags = json.loads(tags_raw) if tags_raw else []
    except (json.JSONDecodeError, TypeError):
        tags = []

    keys = d.keys()
    return {
        'id': d['id'],
        'stock_code': d['stock_code'],
        'stock_name': d['stock_name'],
        'add_date': d['add_date'],
        'score': d['score'],
        'drop_pct': d['drop_pct'],
        'volume_ratio': d['volume_ratio'],
        'close_price': d['close_price'],
        'change_pct': d['change_pct'],
        'reason': d['reason'],
        'tags': tags,
        'pattern': d.get('pattern', ''),
        'stab_confidence': d.get('stab_confidence', 0),
        'market_env': d.get('market_env', ''),
        'platform_days': d.get('platform_days', 0),
        'probe_score': d.get('probe_score', 0),
    }


def _row_to_crypto_trade(row: tuple, cursor) -> Dict:
    d = _row_to_dict(cursor, row)
    return {
        "id": d["id"],
        "symbol": d["symbol"],
        "side": d["side"],
        "price": d["price"],
        "quantity": d["quantity"],
        "amount": d["amount"],
        "fee": d["fee"],
        "pnl": d["pnl"],
        "signal_score": d["signal_score"],
        "signal_reason": d["signal_reason"],
        "trade_time": d["trade_time"],
        "status": d["status"],
    }


def _row_to_bt_run(row: tuple, cursor) -> Dict:
    d = _row_to_dict(cursor, row)
    summary = {}
    equity = []
    params = {}

    try:
        if d.get("summary_json"):
            summary = json.loads(d["summary_json"])
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        if d.get("equity_json"):
            equity = json.loads(d["equity_json"])
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        if d.get("params_json"):
            params = json.loads(d["params_json"])
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "id": d["id"],
        "run_id": d["run_id"],
        "params": params,
        "status": d["status"],
        "start_time": d["start_time"],
        "end_time": d["end_time"] or "",
        "summary": summary,
        "equity": equity,
    }


def init_db():
    """初始化数据库表结构"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                -- 原始交易记录表
                CREATE TABLE IF NOT EXISTS raw_records (
                    id          SERIAL PRIMARY KEY,
                    trade_date  TEXT NOT NULL,
                    stock_code  TEXT NOT NULL,
                    stock_name  TEXT DEFAULT '',
                    direction   TEXT NOT NULL,
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
                    id           SERIAL PRIMARY KEY,
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

                -- 统计信息表
                CREATE TABLE IF NOT EXISTS trade_stats (
                    id              INTEGER PRIMARY KEY CHECK (id = 1),
                    stats_json      TEXT NOT NULL,
                    upload_time     TIMESTAMP DEFAULT NOW()
                );

                -- 选股交易池表
                CREATE TABLE IF NOT EXISTS stock_pool (
                    id              SERIAL PRIMARY KEY,
                    stock_code      TEXT NOT NULL,
                    stock_name      TEXT DEFAULT '',
                    add_date        DATE DEFAULT CURRENT_DATE,
                    score           REAL DEFAULT 0,
                    drop_pct        REAL DEFAULT 0,
                    volume_ratio    REAL DEFAULT 0,
                    close_price     REAL DEFAULT 0,
                    change_pct      REAL DEFAULT 0,
                    reason          TEXT DEFAULT '',
                    tags            TEXT DEFAULT '[]',
                    pattern         TEXT DEFAULT '',
                    stab_confidence INTEGER DEFAULT 0,
                    market_env      TEXT DEFAULT '',
                    status          TEXT DEFAULT 'active',
                    platform_days   INTEGER DEFAULT 0,
                    probe_score     REAL DEFAULT 0,
                    UNIQUE(stock_code, add_date)
                );

                -- 加密货币交易记录
                CREATE TABLE IF NOT EXISTS crypto_trades (
                    id           SERIAL PRIMARY KEY,
                    symbol       TEXT NOT NULL,
                    side         TEXT NOT NULL,
                    price        REAL NOT NULL,
                    quantity     REAL NOT NULL,
                    amount       REAL NOT NULL,
                    fee          REAL DEFAULT 0,
                    pnl          REAL DEFAULT 0,
                    signal_score REAL DEFAULT 0,
                    signal_reason TEXT DEFAULT '',
                    trade_time   TEXT NOT NULL,
                    status       TEXT DEFAULT 'filled'
                );

                -- 机器人配置
                CREATE TABLE IF NOT EXISTS crypto_config (
                    id              INTEGER PRIMARY KEY CHECK (id = 1),
                    api_key         TEXT DEFAULT '',
                    api_secret      TEXT DEFAULT '',
                    is_running      INTEGER DEFAULT 0,
                    config_json     TEXT DEFAULT '{}',
                    updated_at      TIMESTAMP DEFAULT NOW()
                );

                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_matched_profit ON matched_trades(profit);
                CREATE INDEX IF NOT EXISTS idx_matched_sell_date ON matched_trades(sell_date);
                CREATE INDEX IF NOT EXISTS idx_matched_stock_code ON matched_trades(stock_code);
                CREATE INDEX IF NOT EXISTS idx_pool_status ON stock_pool(status);
                CREATE INDEX IF NOT EXISTS idx_pool_date ON stock_pool(add_date);
                CREATE INDEX IF NOT EXISTS idx_crypto_trades_symbol ON crypto_trades(symbol);
                CREATE INDEX IF NOT EXISTS idx_crypto_trades_time ON crypto_trades(trade_time);

                -- 回测运行记录
                CREATE TABLE IF NOT EXISTS crypto_backtest_runs (
                    id           SERIAL PRIMARY KEY,
                    run_id       TEXT NOT NULL UNIQUE,
                    params_json  TEXT NOT NULL,
                    status       TEXT DEFAULT 'running',
                    start_time   TEXT NOT NULL,
                    end_time     TEXT,
                    summary_json TEXT,
                    equity_json  TEXT
                );

                -- 回测逐笔交易
                CREATE TABLE IF NOT EXISTS crypto_backtest_trades (
                    id           SERIAL PRIMARY KEY,
                    run_id       TEXT NOT NULL,
                    symbol       TEXT NOT NULL,
                    side         TEXT NOT NULL,
                    entry_time   TEXT,
                    entry_price  REAL,
                    exit_time    TEXT,
                    exit_price   REAL,
                    quantity     REAL,
                    pnl          REAL,
                    pnl_pct      REAL,
                    exit_reason  TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_bt_runs_id ON crypto_backtest_runs(run_id);
                CREATE INDEX IF NOT EXISTS idx_bt_trades_run ON crypto_backtest_trades(run_id);
            """)
        conn.commit()
        logger.info("数据库初始化完成")
    finally:
        _release_conn(conn)


def clear_all():
    """清空所有数据"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM raw_records")
            cur.execute("DELETE FROM matched_trades")
            cur.execute("DELETE FROM trade_stats")
        conn.commit()
        logger.info("已清空所有旧数据")
    finally:
        _release_conn(conn)


def save_raw_records(records: List[Dict]):
    """批量写入原始交易记录"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO raw_records
                   (trade_date, stock_code, stock_name, direction,
                    price, quantity, amount, commission, stamp_tax,
                    transfer_fee, total_fee)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
        _release_conn(conn)


def save_matched_trades(trades: List[Dict]):
    """批量写入配对交易"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO matched_trades
                   (stock_code, stock_name, buy_date, buy_price,
                    sell_date, sell_price, quantity, buy_amount,
                    sell_amount, total_fee, profit, profit_pct, holding_days)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
        _release_conn(conn)


def save_stats(stats: Dict):
    """保存统计信息（UPSERT）"""
    conn = _get_conn()
    try:
        stats_json = json.dumps(stats, ensure_ascii=False)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO trade_stats (id, stats_json, upload_time)
                   VALUES (1, %s, NOW())
                   ON CONFLICT(id) DO UPDATE SET
                       stats_json = excluded.stats_json,
                       upload_time = NOW()""",
                (stats_json,)
            )
        conn.commit()
        logger.info("统计信息已保存")
    finally:
        _release_conn(conn)


# ====== 查询函数 ======

def has_data() -> bool:
    """检查数据库中是否有交易数据"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM matched_trades")
            row = cur.fetchone()
            return row[0] > 0
    finally:
        _release_conn(conn)


def get_trades(trade_type: str = 'profitable') -> List[Dict]:
    """获取配对交易列表"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            if trade_type == 'profitable':
                cur.execute(
                    "SELECT * FROM matched_trades WHERE profit > 0 ORDER BY sell_date DESC"
                )
            elif trade_type == 'losing':
                cur.execute(
                    "SELECT * FROM matched_trades WHERE profit <= 0 ORDER BY sell_date DESC"
                )
            else:
                cur.execute(
                    "SELECT * FROM matched_trades ORDER BY sell_date DESC"
                )
            rows = cur.fetchall()
            return [_row_to_trade_dict(r, cur) for r in rows]
    finally:
        _release_conn(conn)


def get_stats() -> Optional[Dict]:
    """获取统计信息"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT stats_json FROM trade_stats WHERE id = 1")
            row = cur.fetchone()
            if row:
                return json.loads(row[0])
            return None
    finally:
        _release_conn(conn)


def get_trade_result_for_report() -> Dict:
    """获取完整交易数据结构"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM matched_trades ORDER BY sell_date DESC"
            )
            rows = cur.fetchall()
            all_trades = [_row_to_trade_dict(r, cur) for r in rows]

            profitable = [t for t in all_trades if t['profit'] > 0]
            losing = [t for t in all_trades if t['profit'] <= 0]

            cur.execute(
                "SELECT stats_json FROM trade_stats WHERE id = 1"
            )
            stats_row = cur.fetchone()
            stats = json.loads(stats_row[0]) if stats_row else {}

            return {
                'trades': all_trades,
                'profitable': profitable,
                'losing': losing,
                'stats': stats,
            }
    finally:
        _release_conn(conn)


# ====== 选股交易池 ======

def save_pool_stocks(stocks: List[Dict]):
    """批量写入选股交易池"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            for s in stocks:
                cur.execute(
                    """INSERT INTO stock_pool
                       (stock_code, stock_name, add_date, score, drop_pct,
                        volume_ratio, close_price, change_pct, reason,
                        tags, pattern, stab_confidence, market_env,
                        platform_days, probe_score, status)
                       VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s,
                               %s, %s, %s, %s, %s, %s, 'active')
                       ON CONFLICT(stock_code, add_date) DO UPDATE SET
                           stock_name = excluded.stock_name,
                           score = excluded.score,
                           drop_pct = excluded.drop_pct,
                           volume_ratio = excluded.volume_ratio,
                           close_price = excluded.close_price,
                           change_pct = excluded.change_pct,
                           reason = excluded.reason,
                           tags = excluded.tags,
                           pattern = excluded.pattern,
                           stab_confidence = excluded.stab_confidence,
                           market_env = excluded.market_env,
                           platform_days = excluded.platform_days,
                           probe_score = excluded.probe_score,
                           status = 'active'""",
                    (
                        s['stock_code'], s['stock_name'], s['score'],
                        s['drop_pct'], s['volume_ratio'], s.get('close', 0),
                        s.get('change_pct', 0), s.get('reason', ''),
                        json.dumps(s.get('tags', []), ensure_ascii=False),
                        s.get('pattern', ''),
                        s.get('stab_confidence', 0),
                        s.get('market_env', ''),
                        s.get('platform_days', 0),
                        s.get('probe_score', 0),
                    )
                )
        conn.commit()
        logger.info("交易池写入 %d 只股票", len(stocks))
    finally:
        _release_conn(conn)


def get_pool_stocks() -> List[Dict]:
    """获取交易池中所有 active 股票"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM stock_pool
                   WHERE status = 'active'
                   ORDER BY score DESC"""
            )
            rows = cur.fetchall()
            return [_row_to_pool_dict(r, cur) for r in rows]
    finally:
        _release_conn(conn)


def remove_pool_stock(stock_code: str):
    """从交易池移除一只股票"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE stock_pool SET status = 'removed' WHERE stock_code = %s AND status = 'active'",
                (stock_code,)
            )
        conn.commit()
    finally:
        _release_conn(conn)


def clear_pool():
    """清空交易池"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM stock_pool")
        conn.commit()
        logger.info("交易池已清空")
    finally:
        _release_conn(conn)


# ====== 加密货币配置 ======

def save_crypto_config(api_key: str, api_secret: str, config: dict):
    """保存加密货币机器人配置"""
    conn = _get_conn()
    try:
        config_json = json.dumps(config, ensure_ascii=False)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO crypto_config (id, api_key, api_secret, config_json, updated_at)
                   VALUES (1, %s, %s, %s, NOW())
                   ON CONFLICT(id) DO UPDATE SET
                       api_key = excluded.api_key,
                       api_secret = excluded.api_secret,
                       config_json = excluded.config_json,
                       updated_at = NOW()""",
                (api_key, api_secret, config_json),
            )
        conn.commit()
        logger.info("加密货币配置已保存")
    finally:
        _release_conn(conn)


def get_crypto_config() -> Optional[Dict]:
    """获取加密货币机器人配置"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crypto_config WHERE id = 1")
            row = cur.fetchone()
            if not row:
                return None
            col_names = [desc[0] for desc in cur.description]
            d = dict(zip(col_names, row))

            config_json = d.get("config_json") or "{}"
            try:
                config = json.loads(config_json)
            except (json.JSONDecodeError, TypeError):
                config = {}
            return {
                "api_key": d.get("api_key") or "",
                "api_secret": d.get("api_secret") or "",
                "is_running": bool(d.get("is_running")),
                "config": config,
                "updated_at": d.get("updated_at") or "",
            }
    finally:
        _release_conn(conn)


def set_crypto_running(running: bool):
    """更新机器人运行状态"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO crypto_config (id, is_running, updated_at)
                   VALUES (1, %s, NOW())
                   ON CONFLICT(id) DO UPDATE SET
                       is_running = excluded.is_running,
                       updated_at = NOW()""",
                (1 if running else 0,),
            )
        conn.commit()
    finally:
        _release_conn(conn)


# ====== 加密货币交易记录 ======

def save_crypto_trade(trade: Dict):
    """写入一条加密货币交易记录"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO crypto_trades
                   (symbol, side, price, quantity, amount, fee, pnl,
                    signal_score, signal_reason, trade_time, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    trade["symbol"], trade["side"], trade["price"],
                    trade["quantity"], trade["amount"], trade.get("fee", 0),
                    trade.get("pnl", 0), trade.get("signal_score", 0),
                    trade.get("signal_reason", ""), trade["trade_time"],
                    trade.get("status", "filled"),
                ),
            )
        conn.commit()
    finally:
        _release_conn(conn)


def get_crypto_trades(limit: int = 100, symbol: str = None) -> List[Dict]:
    """获取加密货币交易记录"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            if symbol:
                cur.execute(
                    "SELECT * FROM crypto_trades WHERE symbol = %s ORDER BY trade_time DESC LIMIT %s",
                    (symbol, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM crypto_trades ORDER BY trade_time DESC LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()
            return [_row_to_crypto_trade(r, cur) for r in rows]
    finally:
        _release_conn(conn)


def get_crypto_trade_stats() -> Dict:
    """获取加密货币交易汇总统计"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN side='SELL' AND pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN side='SELL' AND pnl <= 0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN side='SELL' THEN pnl ELSE 0 END) as total_pnl,
                    SUM(fee) as total_fee
                FROM crypto_trades
            """)
            row = cur.fetchone()
            total_sells = (row[1] or 0) + (row[2] or 0)
            return {
                "total_trades": row[0] or 0,
                "wins": row[1] or 0,
                "losses": row[2] or 0,
                "win_rate": round(row[1] / total_sells * 100, 1) if total_sells > 0 else 0,
                "total_pnl": round(row[3] or 0, 2),
                "total_fee": round(row[4] or 0, 2),
            }
    finally:
        _release_conn(conn)


# ====== 回测记录 ======

def save_backtest_run(run_id: str, params: dict, start_time: str):
    """创建一条回测记录"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO crypto_backtest_runs (run_id, params_json, status, start_time)
                   VALUES (%s, %s, 'running', %s)""",
                (run_id, json.dumps(params, ensure_ascii=False), start_time),
            )
        conn.commit()
    finally:
        _release_conn(conn)


def update_backtest_run(run_id: str, status: str, summary: dict, equity: list,
                        end_time: str):
    """更新回测结果"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE crypto_backtest_runs
                   SET status = %s, summary_json = %s, equity_json = %s, end_time = %s
                   WHERE run_id = %s""",
                (
                    status,
                    json.dumps(summary, ensure_ascii=False),
                    json.dumps(equity, ensure_ascii=False),
                    end_time,
                    run_id,
                ),
            )
        conn.commit()
    finally:
        _release_conn(conn)


def save_backtest_trades(run_id: str, trades: List[Dict]):
    """批量写入回测交易"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO crypto_backtest_trades
                   (run_id, symbol, side, entry_time, entry_price,
                    exit_time, exit_price, quantity, pnl, pnl_pct, exit_reason)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        run_id, t["symbol"], t.get("side", "ROUND"),
                        t.get("entry_time", ""), t.get("entry_price", 0),
                        t.get("exit_time", ""), t.get("exit_price", 0),
                        t.get("quantity", 0), t.get("pnl", 0),
                        t.get("pnl_pct", 0), t.get("exit_reason", ""),
                    )
                    for t in trades
                ],
            )
        conn.commit()
    finally:
        _release_conn(conn)


def get_backtest_run(run_id: str) -> Optional[Dict]:
    """获取单条回测结果"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM crypto_backtest_runs WHERE run_id = %s", (run_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_bt_run(row, cur)
    finally:
        _release_conn(conn)


def get_backtest_history(limit: int = 20) -> List[Dict]:
    """获取回测历史列表"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM crypto_backtest_runs ORDER BY start_time DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
            return [_row_to_bt_run(r, cur) for r in rows]
    finally:
        _release_conn(conn)


def get_backtest_trades(run_id: str) -> List[Dict]:
    """获取某次回测的交易明细"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM crypto_backtest_trades WHERE run_id = %s ORDER BY entry_time",
                (run_id,),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "symbol": r[2],
                    "side": r[3],
                    "entry_time": r[4],
                    "entry_price": r[5],
                    "exit_time": r[6],
                    "exit_price": r[7],
                    "quantity": r[8],
                    "pnl": r[9],
                    "pnl_pct": r[10],
                    "exit_reason": r[11],
                }
                for r in rows
            ]
    finally:
        _release_conn(conn)
