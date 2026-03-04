"""
数字货币量化交易机器人
基于价格行为学（弹簧反弹）的全自动现货交易系统
支持 live / paper 双模式
"""

import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from services.binance_client import BinanceClient
from services import database as db
from services import signal_engine as sig

logger = logging.getLogger(__name__)

# ============================
# 默认策略参数
# ============================
DEFAULT_CONFIG = {
    "mode": "paper",              # live / paper
    "scan_interval": 300,         # 扫描间隔（秒）
    "drop_pct": 15,               # 跌幅阈值 %
    "stop_loss_pct": 5,           # 固定止损比例 %（ATR 关闭时使用）
    "take_profit_1_pct": 8,       # 第一档止盈 %
    "take_profit_2_pct": 15,      # 第二档止盈 %
    "tp1_sell_ratio": 0.5,        # 第一档卖出比例
    "max_position_pct": 10,       # 单币种最大仓位 % of总资金
    "max_positions": 5,           # 最大同时持仓数
    "kline_interval": "4h",       # K线周期
    "kline_limit": 100,           # K线根数
    "paper_balance": 10000,       # 模拟盘初始资金 USDT
    "use_atr_stop": True,         # 使用 ATR 动态止损
    "use_trailing": True,         # 使用移动止损
    "use_multi_tf": True,         # 多时间框架过滤
}


class CryptoBot:
    """量化交易机器人"""

    def __init__(self):
        self.running = False
        self.client: Optional[BinanceClient] = None
        self.config: Dict = dict(DEFAULT_CONFIG)
        self.positions: Dict[str, dict] = {}
        self.signals: List[dict] = []
        self.last_scan_time: str = ""
        self.error_msg: str = ""

        # paper 模式虚拟账户
        self._paper_balance: float = DEFAULT_CONFIG["paper_balance"]
        self._paper_positions: Dict[str, dict] = {}

        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 控制
    # ------------------------------------------------------------------

    def configure(self, api_key: str, api_secret: str, config: dict):
        """配置机器人"""
        with self._lock:
            self.client = BinanceClient(api_key, api_secret)
            self.config.update(config)
            if "paper_balance" in config:
                self._paper_balance = float(config["paper_balance"])

    def start(self) -> bool:
        """启动机器人"""
        if self.running:
            return True
        if not self.client:
            self.error_msg = "请先配置 API Key"
            return False

        self.running = True
        self.error_msg = ""
        db.set_crypto_running(True)
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("交易机器人已启动 (mode=%s)", self.config.get("mode", "paper"))
        return True

    def stop(self):
        """停止机器人"""
        self.running = False
        db.set_crypto_running(False)
        logger.info("交易机器人已停止")

    def get_status(self) -> dict:
        """获取机器人状态"""
        with self._lock:
            mode = self.config.get("mode", "paper")
            if mode == "paper":
                positions = dict(self._paper_positions)
                balance = self._paper_balance
            else:
                positions = dict(self.positions)
                balance = self._get_live_balance()

            # 计算持仓浮动盈亏
            position_list = []
            total_unrealized = 0.0
            for sym, pos in positions.items():
                current_price = self._get_price_safe(sym)
                entry_price = pos.get("entry_price", 0)
                qty = pos.get("quantity", 0)
                unrealized = (current_price - entry_price) * qty if entry_price > 0 else 0
                pnl_pct = ((current_price / entry_price) - 1) * 100 if entry_price > 0 else 0
                total_unrealized += unrealized
                position_list.append({
                    "symbol": sym,
                    "entry_price": entry_price,
                    "quantity": qty,
                    "current_price": current_price,
                    "unrealized_pnl": round(unrealized, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "entry_time": pos.get("entry_time", ""),
                    "tp1_hit": pos.get("tp1_hit", False),
                })
                
            return {
                "running": self.running,
                "mode": mode,
                "balance": round(balance, 2),
                "positions": position_list,
                "position_count": len(positions),
                "max_positions": self.config.get("max_positions", 5),
                "signals": list(self.signals),
                "last_scan_time": self.last_scan_time,
                "error": self.error_msg,
                "total_unrealized_pnl": round(total_unrealized, 2),
            }

    def manual_scan(self) -> List[dict]:
        """手动触发一次信号扫描（不自动下单）"""
        if not self.client:
            return []
        try:
            signals = self._scan_signals()
            with self._lock:
                self.signals = signals
                self.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return signals
        except Exception as e:
            logger.error("手动扫描失败: %s", e)
            return []

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def _run_loop(self):
        """后台循环：扫描 -> 下单 -> 止损止盈"""
        while self.running:
            try:
                self._check_positions()
                signals = self._scan_signals()
                with self._lock:
                    self.signals = signals
                    self.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                for signal in signals:
                    if not self.running:
                        break
                    self._try_execute_buy(signal)

            except Exception as e:
                logger.error("机器人循环异常: %s", e, exc_info=True)
                self.error_msg = str(e)

            interval = self.config.get("scan_interval", 300)
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # 信号扫描
    # ------------------------------------------------------------------

    def _scan_signals(self) -> List[dict]:
        """扫描 TOP20 币种，返回符合条件的信号"""
        symbols = self.client.get_top_symbols(20)
        results = []

        for symbol in symbols:
            if not self.running and not self.signals:
                break
            try:
                signal = self._analyze_signal(symbol)
                if signal:
                    results.append(signal)
            except Exception as e:
                logger.debug("分析 %s 失败: %s", symbol, e)
            time.sleep(0.2)

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _analyze_signal(self, symbol: str) -> Optional[dict]:
        """
        分析单个币种的价格行为信号 v2
        使用统一 signal_engine + 右侧确认 + 多时间框架 + BTC 联动增强
        """
        interval = self.config.get("kline_interval", "4h")
        limit = self.config.get("kline_limit", 100)
        raw_klines = self.client.get_klines(symbol, interval, limit)

        if not raw_klines or len(raw_klines) < 30:
            return None

        df = pd.DataFrame(raw_klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore",
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        opens = df["open"].values
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        volumes = df["volume"].values

        drop_threshold = self.config.get("drop_pct", 15) / 100.0
        high_period = max(highs[-60:]) if len(highs) >= 60 else max(highs)
        current_close = closes[-1]
        drop_pct = (high_period - current_close) / high_period
        if drop_pct < drop_threshold:
            return None

        stabilized, stab_confidence = sig.check_stabilized(closes, lows, highs, volumes)
        if not stabilized:
            return None

        vol_spike, vol_ratio = sig.check_volume_spike(volumes)
        if not vol_spike:
            return None

        ma_score, ma_tags = sig.check_ma_support_crypto(closes)
        pattern_score, pattern_name = sig.check_kline_pattern(opens, closes, highs, lows)
        reversal_score, reversal_tags = sig.check_reversal_confirmation(opens, closes, highs, lows, volumes)

        atr = sig.calculate_atr(highs, lows, closes, 14)

        # BTC 联动 v2
        btc_score = self._check_btc_trend_v2()

        # 多时间框架
        htf_score = 0
        if self.config.get("use_multi_tf", True) and symbol != "BTCUSDT":
            htf_score = self._check_htf(symbol)

        result = sig.score_crypto_signal(
            opens, closes, highs, lows, volumes,
            drop_pct=drop_pct,
            stab_confidence=stab_confidence,
            vol_ratio=vol_ratio,
            ma_score=ma_score,
            ma_tags=ma_tags,
            pattern_score=pattern_score,
            pattern_name=pattern_name,
            reversal_score=reversal_score,
            reversal_tags=reversal_tags,
            btc_score=btc_score,
            htf_score=htf_score,
            min_score=40,
        )

        if result is None:
            return None

        return {
            "symbol": symbol,
            "score": result["score"],
            "drop_pct": round(drop_pct * 100, 1),
            "volume_ratio": vol_ratio,
            "current_price": current_close,
            "stab_confidence": stab_confidence,
            "pattern": pattern_name,
            "ma_tags": ma_tags,
            "tags": result["tags"],
            "reason": result["reason"],
            "atr": atr,
        }

    # ------------------------------------------------------------------
    # BTC 联动 v2（短期 + 中期）
    # ------------------------------------------------------------------

    def _check_btc_trend_v2(self) -> float:
        """BTC 趋势增强版：短期 4h 动量 + 日线 MA20"""
        try:
            btc_4h = self.client.get_klines("BTCUSDT", "4h", 12)
            btc_4h_closes = [float(k[4]) for k in btc_4h] if btc_4h else []

            btc_1d = self.client.get_klines("BTCUSDT", "1d", 25)
            btc_daily_closes = [float(k[4]) for k in btc_1d] if btc_1d else []

            score, _ = sig.check_btc_trend_enhanced(btc_4h_closes, btc_daily_closes)
            return score
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # 多时间框架过滤
    # ------------------------------------------------------------------

    def _check_htf(self, symbol: str) -> float:
        """日线级别趋势过滤"""
        try:
            daily = self.client.get_klines(symbol, "1d", 25)
            if not daily or len(daily) < 20:
                return 0
            daily_closes = [float(k[4]) for k in daily]
            score, _ = sig.check_higher_timeframe(daily_closes)
            return score
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # 下单 & 持仓管理
    # ------------------------------------------------------------------

    def _try_execute_buy(self, signal: dict):
        """尝试买入"""
        symbol = signal["symbol"]
        mode = self.config.get("mode", "paper")

        positions = self._paper_positions if mode == "paper" else self.positions
        max_pos = self.config.get("max_positions", 5)
        if len(positions) >= max_pos:
            return
        if symbol in positions:
            return

        balance = self._paper_balance if mode == "paper" else self._get_live_balance()
        max_pct = self.config.get("max_position_pct", 10) / 100.0
        order_amount = balance * max_pct
        if order_amount < 10:
            return

        price = signal["current_price"]
        quantity = order_amount / price
        atr = signal.get("atr", 0)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        pos_data = {
            "entry_price": price,
            "quantity": quantity,
            "entry_time": now_str,
            "amount": order_amount,
            "tp1_hit": False,
            "highest_price": price,
            "atr": atr,
        }

        if mode == "paper":
            self._paper_balance -= order_amount
            fee = order_amount * 0.001
            self._paper_balance -= fee
            self._paper_positions[symbol] = pos_data
            db.save_crypto_trade({
                "symbol": symbol, "side": "BUY", "price": price,
                "quantity": quantity, "amount": order_amount,
                "fee": fee, "pnl": 0,
                "signal_score": signal["score"],
                "signal_reason": signal["reason"],
                "trade_time": now_str, "status": "paper",
            })
            logger.info("[PAPER] 买入 %s @ %.4f, qty=%.6f, amount=%.2f",
                        symbol, price, quantity, order_amount)
        else:
            try:
                result = self.client.place_market_order_quote(symbol, "BUY", order_amount)
                filled_qty = float(result.get("executedQty", 0))
                filled_price = float(result.get("cummulativeQuoteQty", 0)) / filled_qty if filled_qty > 0 else price
                pos_data["entry_price"] = filled_price
                pos_data["quantity"] = filled_qty
                pos_data["highest_price"] = filled_price
                self.positions[symbol] = pos_data
                db.save_crypto_trade({
                    "symbol": symbol, "side": "BUY", "price": filled_price,
                    "quantity": filled_qty, "amount": order_amount,
                    "fee": order_amount * 0.001,
                    "signal_score": signal["score"],
                    "signal_reason": signal["reason"],
                    "trade_time": now_str, "status": "filled",
                })
                logger.info("[LIVE] 买入 %s @ %.4f, qty=%.6f", symbol, filled_price, filled_qty)
            except Exception as e:
                logger.error("买入 %s 失败: %s", symbol, e)

    def _check_positions(self):
        """检查所有持仓，执行 ATR 止损 / 移动止损 / 阶梯止盈"""
        mode = self.config.get("mode", "paper")
        positions = self._paper_positions if mode == "paper" else self.positions
        use_atr = self.config.get("use_atr_stop", True)
        use_trailing = self.config.get("use_trailing", True)

        to_close = []
        for symbol, pos in list(positions.items()):
            current_price = self._get_price_safe(symbol)
            if current_price <= 0:
                continue

            entry_price = pos["entry_price"]
            atr = pos.get("atr", 0)
            pnl_pct = (current_price / entry_price - 1) * 100

            # 更新最高价追踪
            if current_price > pos.get("highest_price", entry_price):
                pos["highest_price"] = current_price

            tp1_pct = self.config.get("take_profit_1_pct", 8)
            tp2_pct = self.config.get("take_profit_2_pct", 15)
            tp1_ratio = self.config.get("tp1_sell_ratio", 0.5)

            # 计算止损价
            if use_atr and atr > 0:
                stop_price = entry_price - 2 * atr
            else:
                sl_pct = self.config.get("stop_loss_pct", 5) / 100.0
                stop_price = entry_price * (1 - sl_pct)

            # 移动止损：盈利后上移
            if use_trailing and atr > 0:
                pnl_in_atr = (current_price - entry_price) / atr
                if pnl_in_atr >= 2:
                    trailing = pos.get("highest_price", entry_price) - 1.5 * atr
                    stop_price = max(stop_price, trailing)
                elif pnl_in_atr >= 1:
                    stop_price = max(stop_price, entry_price)

            # 触发止损
            if current_price <= stop_price:
                reason = "ATR止损" if use_atr and atr > 0 else "止损"
                if use_trailing and current_price > entry_price:
                    reason = "移动止损"
                to_close.append((symbol, pos["quantity"], reason))
                continue

            # 第一档止盈
            if pnl_pct >= tp1_pct and not pos.get("tp1_hit"):
                sell_qty = pos["quantity"] * tp1_ratio
                self._execute_sell(symbol, sell_qty, "止盈1")
                pos["tp1_hit"] = True
                pos["quantity"] -= sell_qty
                continue

            # 第二档止盈
            if pnl_pct >= tp2_pct:
                to_close.append((symbol, pos["quantity"], "止盈2"))

        for symbol, qty, reason in to_close:
            self._execute_sell(symbol, qty, reason)
            if symbol in positions:
                del positions[symbol]

    def _execute_sell(self, symbol: str, quantity: float, reason: str):
        """执行卖出"""
        mode = self.config.get("mode", "paper")
        price = self._get_price_safe(symbol)
        amount = price * quantity
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        positions = self._paper_positions if mode == "paper" else self.positions
        entry_price = positions.get(symbol, {}).get("entry_price", 0)
        pnl = (price - entry_price) * quantity

        if mode == "paper":
            fee = amount * 0.001
            self._paper_balance += amount - fee
            db.save_crypto_trade({
                "symbol": symbol, "side": "SELL", "price": price,
                "quantity": quantity, "amount": amount,
                "fee": fee, "pnl": round(pnl, 2),
                "signal_reason": reason,
                "trade_time": now_str, "status": "paper",
            })
            logger.info("[PAPER] 卖出 %s @ %.4f, qty=%.6f, pnl=%.2f (%s)",
                        symbol, price, quantity, pnl, reason)
        else:
            try:
                self.client.place_market_order(symbol, "SELL", quantity)
                db.save_crypto_trade({
                    "symbol": symbol, "side": "SELL", "price": price,
                    "quantity": quantity, "amount": amount,
                    "fee": amount * 0.001, "pnl": round(pnl, 2),
                    "signal_reason": reason,
                    "trade_time": now_str, "status": "filled",
                })
                logger.info("[LIVE] 卖出 %s @ %.4f, qty=%.6f, pnl=%.2f (%s)",
                            symbol, price, quantity, pnl, reason)
            except Exception as e:
                logger.error("卖出 %s 失败: %s", symbol, e)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _get_price_safe(self, symbol: str) -> float:
        try:
            return self.client.get_ticker_price(symbol)
        except Exception:
            return 0

    def _get_live_balance(self) -> float:
        try:
            return self.client.get_usdt_balance()
        except Exception:
            return 0


# ============================
# 全局单例
# ============================
_bot_instance: Optional[CryptoBot] = None
_bot_lock = threading.Lock()


def get_bot() -> CryptoBot:
    """获取全局机器人单例"""
    global _bot_instance
    with _bot_lock:
        if _bot_instance is None:
            _bot_instance = CryptoBot()
            _restore_config()
    return _bot_instance


def _restore_config():
    """从数据库恢复配置"""
    cfg = db.get_crypto_config()
    if cfg and cfg["api_key"]:
        _bot_instance.configure(
            cfg["api_key"],
            cfg["api_secret"],
            cfg.get("config", {}),
        )
