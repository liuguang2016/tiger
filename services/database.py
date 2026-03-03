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
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code      TEXT NOT NULL,
                stock_name      TEXT DEFAULT '',
                add_date        TEXT NOT NULL DEFAULT (date('now','localtime')),
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
                UNIQUE(stock_code, add_date)
            );

            -- 加密货币交易记录
            CREATE TABLE IF NOT EXISTS crypto_trades (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
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

            -- 机器人配置（单行表）
            CREATE TABLE IF NOT EXISTS crypto_config (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                api_key         TEXT DEFAULT '',
                api_secret      TEXT DEFAULT '',
                is_running      INTEGER DEFAULT 0,
                config_json     TEXT DEFAULT '{}',
                updated_at      TEXT DEFAULT (datetime('now','localtime'))
            );

            -- 创建索引加速查询
            CREATE INDEX IF NOT EXISTS idx_matched_profit ON matched_trades(profit);
            CREATE INDEX IF NOT EXISTS idx_matched_sell_date ON matched_trades(sell_date);
            CREATE INDEX IF NOT EXISTS idx_matched_stock_code ON matched_trades(stock_code);
            CREATE INDEX IF NOT EXISTS idx_pool_status ON stock_pool(status);
            CREATE INDEX IF NOT EXISTS idx_pool_date ON stock_pool(add_date);
            -- 回测运行记录
            CREATE TABLE IF NOT EXISTS crypto_backtest_runs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
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
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
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

            CREATE INDEX IF NOT EXISTS idx_crypto_trades_symbol ON crypto_trades(symbol);
            CREATE INDEX IF NOT EXISTS idx_crypto_trades_time ON crypto_trades(trade_time);
            CREATE INDEX IF NOT EXISTS idx_bt_runs_id ON crypto_backtest_runs(run_id);
            CREATE INDEX IF NOT EXISTS idx_bt_trades_run ON crypto_backtest_trades(run_id);
        """)
        conn.commit()

        # 迁移：为旧版 stock_pool 表添加新列
        _migrate_pool_columns(conn)

        logger.info("数据库初始化完成: %s", DB_PATH)
    finally:
        conn.close()


def _migrate_pool_columns(conn: sqlite3.Connection):
    """为旧版 stock_pool 表添加 v2 新增列"""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(stock_pool)").fetchall()}
    new_cols = [
        ("tags", "TEXT DEFAULT '[]'"),
        ("pattern", "TEXT DEFAULT ''"),
        ("stab_confidence", "INTEGER DEFAULT 0"),
        ("market_env", "TEXT DEFAULT ''"),
    ]
    for col_name, col_def in new_cols:
        if col_name not in existing:
            try:
                conn.execute(f"ALTER TABLE stock_pool ADD COLUMN {col_name} {col_def}")
                logger.info("stock_pool 表新增列: %s", col_name)
            except Exception:
                pass
    conn.commit()


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
                volume_ratio, close_price, change_pct, reason,
                tags, pattern, stab_confidence, market_env, status)
               VALUES (?, ?, date('now','localtime'), ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, 'active')""",
            [
                (
                    s['stock_code'], s['stock_name'], s['score'],
                    s['drop_pct'], s['volume_ratio'], s.get('close', 0),
                    s.get('change_pct', 0), s.get('reason', ''),
                    json.dumps(s.get('tags', []), ensure_ascii=False),
                    s.get('pattern', ''),
                    s.get('stab_confidence', 0),
                    s.get('market_env', ''),
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


# ====== 加密货币配置 ======

def save_crypto_config(api_key: str, api_secret: str, config: dict):
    """保存加密货币机器人配置"""
    conn = _get_conn()
    try:
        config_json = json.dumps(config, ensure_ascii=False)
        conn.execute(
            """INSERT INTO crypto_config (id, api_key, api_secret, config_json, updated_at)
               VALUES (1, ?, ?, ?, datetime('now','localtime'))
               ON CONFLICT(id) DO UPDATE SET
                   api_key = excluded.api_key,
                   api_secret = excluded.api_secret,
                   config_json = excluded.config_json,
                   updated_at = datetime('now','localtime')""",
            (api_key, api_secret, config_json),
        )
        conn.commit()
        logger.info("加密货币配置已保存")
    finally:
        conn.close()


def get_crypto_config() -> Optional[Dict]:
    """获取加密货币机器人配置"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM crypto_config WHERE id = 1").fetchone()
        if not row:
            return None
        config_json = row["config_json"] or "{}"
        try:
            config = json.loads(config_json)
        except (json.JSONDecodeError, TypeError):
            config = {}
        return {
            "api_key": row["api_key"] or "",
            "api_secret": row["api_secret"] or "",
            "is_running": bool(row["is_running"]),
            "config": config,
            "updated_at": row["updated_at"] or "",
        }
    finally:
        conn.close()


def set_crypto_running(running: bool):
    """更新机器人运行状态"""
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO crypto_config (id, is_running, updated_at)
               VALUES (1, ?, datetime('now','localtime'))
               ON CONFLICT(id) DO UPDATE SET
                   is_running = excluded.is_running,
                   updated_at = datetime('now','localtime')""",
            (1 if running else 0,),
        )
        conn.commit()
    finally:
        conn.close()


# ====== 加密货币交易记录 ======

def save_crypto_trade(trade: Dict):
    """写入一条加密货币交易记录"""
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO crypto_trades
               (symbol, side, price, quantity, amount, fee, pnl,
                signal_score, signal_reason, trade_time, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
        conn.close()


def get_crypto_trades(limit: int = 100, symbol: str = None) -> List[Dict]:
    """获取加密货币交易记录"""
    conn = _get_conn()
    try:
        if symbol:
            rows = conn.execute(
                "SELECT * FROM crypto_trades WHERE symbol = ? ORDER BY trade_time DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM crypto_trades ORDER BY trade_time DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_crypto_trade(r) for r in rows]
    finally:
        conn.close()


def get_crypto_trade_stats() -> Dict:
    """获取加密货币交易汇总统计"""
    conn = _get_conn()
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN side='SELL' AND pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN side='SELL' AND pnl <= 0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN side='SELL' THEN pnl ELSE 0 END) as total_pnl,
                SUM(fee) as total_fee
            FROM crypto_trades
        """).fetchone()
        total_sells = (row["wins"] or 0) + (row["losses"] or 0)
        return {
            "total_trades": row["total"] or 0,
            "wins": row["wins"] or 0,
            "losses": row["losses"] or 0,
            "win_rate": round(row["wins"] / total_sells * 100, 1) if total_sells > 0 else 0,
            "total_pnl": round(row["total_pnl"] or 0, 2),
            "total_fee": round(row["total_fee"] or 0, 2),
        }
    finally:
        conn.close()


def _row_to_crypto_trade(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "side": row["side"],
        "price": row["price"],
        "quantity": row["quantity"],
        "amount": row["amount"],
        "fee": row["fee"],
        "pnl": row["pnl"],
        "signal_score": row["signal_score"],
        "signal_reason": row["signal_reason"],
        "trade_time": row["trade_time"],
        "status": row["status"],
    }


# ====== 回测记录 ======

def save_backtest_run(run_id: str, params: dict, start_time: str):
    """创建一条回测记录"""
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO crypto_backtest_runs (run_id, params_json, status, start_time)
               VALUES (?, ?, 'running', ?)""",
            (run_id, json.dumps(params, ensure_ascii=False), start_time),
        )
        conn.commit()
    finally:
        conn.close()


def update_backtest_run(run_id: str, status: str, summary: dict, equity: list,
                        end_time: str):
    """更新回测结果"""
    conn = _get_conn()
    try:
        conn.execute(
            """UPDATE crypto_backtest_runs
               SET status = ?, summary_json = ?, equity_json = ?, end_time = ?
               WHERE run_id = ?""",
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
        conn.close()


def save_backtest_trades(run_id: str, trades: List[Dict]):
    """批量写入回测交易"""
    conn = _get_conn()
    try:
        conn.executemany(
            """INSERT INTO crypto_backtest_trades
               (run_id, symbol, side, entry_time, entry_price,
                exit_time, exit_price, quantity, pnl, pnl_pct, exit_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
        conn.close()


def get_backtest_run(run_id: str) -> Optional[Dict]:
    """获取单条回测结果"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM crypto_backtest_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        return _row_to_bt_run(row)
    finally:
        conn.close()


def get_backtest_history(limit: int = 20) -> List[Dict]:
    """获取回测历史列表"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM crypto_backtest_runs ORDER BY start_time DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_bt_run(r) for r in rows]
    finally:
        conn.close()


def get_backtest_trades(run_id: str) -> List[Dict]:
    """获取某次回测的交易明细"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM crypto_backtest_trades WHERE run_id = ? ORDER BY entry_time",
            (run_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "symbol": r["symbol"],
                "side": r["side"],
                "entry_time": r["entry_time"],
                "entry_price": r["entry_price"],
                "exit_time": r["exit_time"],
                "exit_price": r["exit_price"],
                "quantity": r["quantity"],
                "pnl": r["pnl"],
                "pnl_pct": r["pnl_pct"],
                "exit_reason": r["exit_reason"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def _row_to_bt_run(row: sqlite3.Row) -> Dict:
    summary = {}
    equity = []
    try:
        if row["summary_json"]:
            summary = json.loads(row["summary_json"])
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        if row["equity_json"]:
            equity = json.loads(row["equity_json"])
    except (json.JSONDecodeError, TypeError):
        pass
    params = {}
    try:
        if row["params_json"]:
            params = json.loads(row["params_json"])
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "params": params,
        "status": row["status"],
        "start_time": row["start_time"],
        "end_time": row["end_time"] or "",
        "summary": summary,
        "equity": equity,
    }


def _row_to_pool_dict(row: sqlite3.Row) -> Dict:
    """将数据库行转为交易池 dict"""
    tags_raw = row['tags'] if 'tags' in row.keys() else '[]'
    try:
        tags = json.loads(tags_raw) if tags_raw else []
    except (json.JSONDecodeError, TypeError):
        tags = []

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
        'tags': tags,
        'pattern': row['pattern'] if 'pattern' in row.keys() else '',
        'stab_confidence': row['stab_confidence'] if 'stab_confidence' in row.keys() else 0,
        'market_env': row['market_env'] if 'market_env' in row.keys() else '',
    }
