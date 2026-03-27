#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script

Usage:
    python scripts/migrate_sqlite_to_pg.py

Environment variables:
    POSTGRES_HOST: PostgreSQL host (default: localhost)
    POSTGRES_PORT: PostgreSQL port (default: 5432)
    POSTGRES_DB: Database name (default: tigger)
    POSTGRES_USER: Database user (default: tigger)
    POSTGRES_PASSWORD: Database password (default: postgres)
    SQLITE_PATH: Path to SQLite file (default: data/trades.db)
"""

import json
import os
import sqlite3
import sys
from datetime import datetime

import psycopg2
from psycopg2 import pool


def get_sqlite_conn(path: str) -> sqlite3.Connection:
    """Connect to SQLite database"""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_pg_pool():
    """Get PostgreSQL connection pool"""
    return pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        host=os.environ.get('POSTGRES_HOST', 'localhost'),
        port=int(os.environ.get('POSTGRES_PORT', '5432')),
        database=os.environ.get('POSTGRES_DB', 'tigger'),
        user=os.environ.get('POSTGRES_USER', 'tigger'),
        password=os.environ.get('POSTGRES_PASSWORD', 'postgres'),
    )


def create_pg_tables(cur):
    """Create PostgreSQL tables"""
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

        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_matched_profit ON matched_trades(profit);
        CREATE INDEX IF NOT EXISTS idx_matched_sell_date ON matched_trades(sell_date);
        CREATE INDEX IF NOT EXISTS idx_matched_stock_code ON matched_trades(stock_code);
        CREATE INDEX IF NOT EXISTS idx_pool_status ON stock_pool(status);
        CREATE INDEX IF NOT EXISTS idx_pool_date ON stock_pool(add_date);
        CREATE INDEX IF NOT EXISTS idx_crypto_trades_symbol ON crypto_trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_crypto_trades_time ON crypto_trades(trade_time);
        CREATE INDEX IF NOT EXISTS idx_bt_runs_id ON crypto_backtest_runs(run_id);
        CREATE INDEX IF NOT EXISTS idx_bt_trades_run ON crypto_backtest_trades(run_id);
    """)


def migrate_table(pg_cur, sqlite_cur, table_name: str, columns: list, pg_columns: list = None):
    """Migrate a single table from SQLite to PostgreSQL"""
    if pg_columns is None:
        pg_columns = columns

    # Get SQLite data
    sqlite_cur.execute(f"SELECT {', '.join(columns)} FROM {table_name}")
    rows = sqlite_cur.fetchall()

    if not rows:
        print(f"  {table_name}: 0 rows (skip)")
        return 0

    # Insert into PostgreSQL
    placeholders = ', '.join(['%s'] * len(pg_columns))
    insert_sql = f"INSERT INTO {table_name} ({', '.join(pg_columns)}) VALUES ({placeholders})"

    for row in rows:
        try:
            pg_cur.execute(insert_sql, tuple(row))
        except Exception as e:
            print(f"  Error inserting into {table_name}: {e}")
            continue

    return len(rows)


def main():
    print("=" * 60)
    print("SQLite to PostgreSQL Migration")
    print("=" * 60)

    # Get paths
    sqlite_path = os.environ.get('SQLITE_PATH', 'data/trades.db')
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), sqlite_path)

    if not os.path.exists(sqlite_path):
        print(f"ERROR: SQLite file not found: {sqlite_path}")
        sys.exit(1)

    print(f"\nSource SQLite: {sqlite_path}")

    # Connect to SQLite
    print("\nConnecting to SQLite...")
    sqlite_conn = get_sqlite_conn(sqlite_path)
    sqlite_cur = sqlite_conn.cursor()
    print("  OK")

    # Connect to PostgreSQL
    print("\nConnecting to PostgreSQL...")
    try:
        pg_pool = get_pg_pool()
        pg_conn = pg_pool.getconn()
        pg_cur = pg_conn.cursor()
        print("  OK")
    except Exception as e:
        print(f"  ERROR: {e}")
        print("\nMake sure PostgreSQL is running and accessible.")
        print("You can start it with: docker-compose up -d postgres")
        sys.exit(1)

    try:
        # Create tables
        print("\nCreating PostgreSQL tables...")
        create_pg_tables(pg_cur)
        pg_conn.commit()
        print("  OK")

        # Migration summary
        total_migrated = 0

        # 1. raw_records
        print("\nMigrating raw_records...")
        count = migrate_table(pg_cur, sqlite_cur, "raw_records",
                             ['trade_date', 'stock_code', 'stock_name', 'direction',
                              'price', 'quantity', 'amount', 'commission', 'stamp_tax',
                              'transfer_fee', 'total_fee'])
        print(f"  Migrated {count} rows")
        total_migrated += count

        # 2. matched_trades
        print("\nMigrating matched_trades...")
        count = migrate_table(pg_cur, sqlite_cur, "matched_trades",
                             ['stock_code', 'stock_name', 'buy_date', 'buy_price',
                              'sell_date', 'sell_price', 'quantity', 'buy_amount',
                              'sell_amount', 'total_fee', 'profit', 'profit_pct',
                              'holding_days'])
        print(f"  Migrated {count} rows")
        total_migrated += count

        # 3. trade_stats
        print("\nMigrating trade_stats...")
        sqlite_cur.execute("SELECT id, stats_json, upload_time FROM trade_stats")
        rows = sqlite_cur.fetchall()
        for row in rows:
            pg_cur.execute(
                "INSERT INTO trade_stats (id, stats_json, upload_time) VALUES (%s, %s, %s) "
                "ON CONFLICT(id) DO UPDATE SET stats_json = excluded.stats_json",
                (row['id'], row['stats_json'], row['upload_time'])
            )
        print(f"  Migrated {len(rows)} rows")
        total_migrated += len(rows)

        # 4. stock_pool
        print("\nMigrating stock_pool...")
        count = migrate_table(pg_cur, sqlite_cur, "stock_pool",
                             ['stock_code', 'stock_name', 'add_date', 'score',
                              'drop_pct', 'volume_ratio', 'close_price', 'change_pct',
                              'reason', 'tags', 'pattern', 'stab_confidence', 'market_env',
                              'status', 'platform_days', 'probe_score'])
        print(f"  Migrated {count} rows")
        total_migrated += count

        # 5. crypto_trades
        print("\nMigrating crypto_trades...")
        count = migrate_table(pg_cur, sqlite_cur, "crypto_trades",
                             ['symbol', 'side', 'price', 'quantity', 'amount',
                              'fee', 'pnl', 'signal_score', 'signal_reason',
                              'trade_time', 'status'])
        print(f"  Migrated {count} rows")
        total_migrated += count

        # 6. crypto_config
        print("\nMigrating crypto_config...")
        sqlite_cur.execute("SELECT * FROM crypto_config")
        rows = sqlite_cur.fetchall()
        for row in rows:
            d = dict(row)
            pg_cur.execute(
                """INSERT INTO crypto_config (id, api_key, api_secret, is_running, config_json, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT(id) DO UPDATE SET
                       api_key = excluded.api_key,
                       api_secret = excluded.api_secret,
                       is_running = excluded.is_running,
                       config_json = excluded.config_json""",
                (d['id'], d['api_key'], d['api_secret'], d['is_running'],
                 d['config_json'], d['updated_at'])
            )
        print(f"  Migrated {len(rows)} rows")
        total_migrated += len(rows)

        # 7. crypto_backtest_runs
        print("\nMigrating crypto_backtest_runs...")
        count = migrate_table(pg_cur, sqlite_cur, "crypto_backtest_runs",
                             ['run_id', 'params_json', 'status', 'start_time',
                              'end_time', 'summary_json', 'equity_json'])
        print(f"  Migrated {count} rows")
        total_migrated += count

        # 8. crypto_backtest_trades
        print("\nMigrating crypto_backtest_trades...")
        count = migrate_table(pg_cur, sqlite_cur, "crypto_backtest_trades",
                             ['run_id', 'symbol', 'side', 'entry_time', 'entry_price',
                              'exit_time', 'exit_price', 'quantity', 'pnl', 'pnl_pct',
                              'exit_reason'])
        print(f"  Migrated {count} rows")
        total_migrated += count

        # Commit
        pg_conn.commit()

        # Verification
        print("\n" + "=" * 60)
        print("Verification")
        print("=" * 60)

        pg_cur.execute("""
            SELECT 'raw_records' as tbl, COUNT(*) as cnt FROM raw_records
            UNION ALL SELECT 'matched_trades', COUNT(*) FROM matched_trades
            UNION ALL SELECT 'trade_stats', COUNT(*) FROM trade_stats
            UNION ALL SELECT 'stock_pool', COUNT(*) FROM stock_pool
            UNION ALL SELECT 'crypto_trades', COUNT(*) FROM crypto_trades
            UNION ALL SELECT 'crypto_config', COUNT(*) FROM crypto_config
            UNION ALL SELECT 'crypto_backtest_runs', COUNT(*) FROM crypto_backtest_runs
            UNION ALL SELECT 'crypto_backtest_trades', COUNT(*) FROM crypto_backtest_trades
        """)

        print("\nPostgreSQL record counts:")
        print("-" * 40)
        total_pg = 0
        for row in pg_cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
            total_pg += row[1]

        print("-" * 40)
        print(f"  Total: {total_pg} records")

        print("\n" + "=" * 60)
        print(f"Migration complete! {total_migrated} records migrated.")
        print("=" * 60)

    finally:
        sqlite_conn.close()
        pg_pool.putconn(pg_conn)
        pg_pool.closeall()


if __name__ == "__main__":
    main()
