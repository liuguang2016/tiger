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

logger = logging.getLogger(__name__)

# ============================
# 默认策略参数
# ============================
DEFAULT_CONFIG = {
    "mode": "paper",              # live / paper
    "scan_interval": 300,         # 扫描间隔（秒）
    "drop_pct": 15,               # 跌幅阈值 %
    "stop_loss_pct": 5,           # 止损比例 %
    "take_profit_1_pct": 8,       # 第一档止盈 %
    "take_profit_2_pct": 15,      # 第二档止盈 %
    "tp1_sell_ratio": 0.5,        # 第一档卖出比例
    "max_position_pct": 10,       # 单币种最大仓位 % of总资金
    "max_positions": 5,           # 最大同时持仓数
    "kline_interval": "4h",       # K线周期
    "kline_limit": 100,           # K线根数
    "paper_balance": 10000,       # 模拟盘初始资金 USDT
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
        分析单个币种的价格行为信号
        复用 A 股选股引擎逻辑，适配加密货币
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

        # 跌幅检查
        drop_threshold = self.config.get("drop_pct", 15) / 100.0
        high_period = max(highs[-60:]) if len(highs) >= 60 else max(highs)
        current_close = closes[-1]
        drop_pct = (high_period - current_close) / high_period
        if drop_pct < drop_threshold:
            return None

        # 企稳信号
        stabilized, stab_confidence = self._check_stabilized(closes, lows, highs, volumes)
        if not stabilized:
            return None

        # 量能异变
        vol_spike, vol_ratio = self._check_volume_spike(volumes)
        if not vol_spike:
            return None

        # 均线支撑
        ma_score, ma_tags = self._check_ma_support(closes)

        # K线形态
        pattern_score, pattern_name = self._check_kline_pattern(opens, closes, highs, lows)

        # 综合评分（满分100）
        score = 0.0
        reasons = []
        tags = []

        drop_score = min(drop_pct / 0.4 * 25, 25)
        score += drop_score
        reasons.append(f"回落{drop_pct*100:.1f}%")

        stab_score = min(stab_confidence * 6.7, 20)
        score += stab_score
        reasons.append(f"企稳{stab_confidence}/3")

        vol_score = min(max((vol_ratio - 1) * 8, 0), 20)
        score += vol_score
        reasons.append(f"量比{vol_ratio}")

        ma_capped = min(ma_score, 15)
        score += ma_capped
        tags.extend(ma_tags)

        pattern_capped = min(pattern_score, 10)
        score += pattern_capped
        if pattern_name:
            tags.append(pattern_name)
            reasons.append(pattern_name)

        # BTC 联动加分（如果 BTC 是上涨的）
        btc_bonus = self._check_btc_trend()
        score += min(btc_bonus, 10)

        score = round(max(min(score, 100), 0), 1)

        if score < 40:
            return None

        return {
            "symbol": symbol,
            "score": score,
            "drop_pct": round(drop_pct * 100, 1),
            "volume_ratio": vol_ratio,
            "current_price": current_close,
            "stab_confidence": stab_confidence,
            "pattern": pattern_name,
            "ma_tags": ma_tags,
            "tags": tags,
            "reason": "; ".join(reasons),
        }

    # ------------------------------------------------------------------
    # 技术分析
    # ------------------------------------------------------------------

    def _check_stabilized(self, closes, lows, highs, volumes) -> Tuple[bool, int]:
        if len(closes) < 25:
            return False, 0

        recent_5d_low = min(lows[-5:])
        prev_20d_low = min(lows[-25:-5])
        if recent_5d_low < prev_20d_low * 0.99:
            return False, 0

        confidence = 0

        if len(closes) >= 10:
            recent_drop = (closes[-1] - closes[-5]) / closes[-5]
            prev_drop = (closes[-5] - closes[-10]) / closes[-10]
            if recent_drop > prev_drop:
                confidence += 1

        if len(highs) >= 15:
            recent_range = (max(highs[-5:]) - min(lows[-5:])) / closes[-1]
            prev_range = (max(highs[-15:-5]) - min(lows[-15:-5])) / closes[-5]
            if recent_range < prev_range:
                confidence += 1

        if len(volumes) >= 13:
            recent_vol = volumes[-3:].mean()
            prev_vol = volumes[-13:-3].mean()
            if prev_vol > 0 and recent_vol > prev_vol * 1.3:
                confidence += 1

        return confidence >= 1, confidence

    def _check_volume_spike(self, volumes) -> Tuple[bool, float]:
        if len(volumes) >= 23:
            avg_vol = volumes[-23:-3].mean()
            if avg_vol > 0:
                max_vol = max(volumes[-3:])
                ratio = round(max_vol / avg_vol, 2)
                return max_vol > avg_vol * 2, ratio
        return False, 0

    def _check_ma_support(self, closes) -> Tuple[float, List[str]]:
        if len(closes) < 25:
            return 0, []

        s = pd.Series(closes)
        ma7 = s.rolling(7).mean().values
        ma25 = s.rolling(25).mean().values

        score = 0.0
        tags = []
        current = closes[-1]

        if len(ma7) >= 3 and not np.isnan(ma7[-3]):
            if ma7[-1] > ma7[-2] and ma7[-2] <= ma7[-3]:
                score += 6
                tags.append("MA7拐头")

        if not np.isnan(ma7[-1]) and current > ma7[-1]:
            score += 3

        if len(ma7) >= 2 and not np.isnan(ma25[-2]):
            if ma7[-1] > ma25[-1] and ma7[-2] <= ma25[-2]:
                score += 6
                tags.append("金叉")

        return score, tags

    def _check_kline_pattern(self, opens, closes, highs, lows) -> Tuple[float, str]:
        if len(closes) < 3:
            return 0, ""

        best_score = 0
        best_pattern = ""

        o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
        body = abs(c - o)
        lower_shadow = min(o, c) - l
        upper_shadow = h - max(o, c)

        if body > 0 and lower_shadow > body * 2 and upper_shadow < body * 0.5:
            best_score = 8
            best_pattern = "锤子线"

        if len(closes) >= 2:
            yo, yc = opens[-2], closes[-2]
            if yc < yo and c > o and c > yo and o < yc:
                if 10 > best_score:
                    best_score = 10
                    best_pattern = "阳包阴"

        if len(closes) >= 3:
            o3, c3 = opens[-3], closes[-3]
            o2, c2 = opens[-2], closes[-2]
            big_body = abs(o3 - c3)
            if big_body > 0 and c3 < o3 and abs(c2 - o2) < big_body * 0.3 and c > o and c > (o3 + c3) / 2:
                if 10 > best_score:
                    best_score = 10
                    best_pattern = "早晨之星"

        return best_score, best_pattern

    def _check_btc_trend(self) -> float:
        """检查 BTC 趋势作为大环境参考"""
        try:
            btc_klines = self.client.get_klines("BTCUSDT", "4h", 10)
            if not btc_klines or len(btc_klines) < 5:
                return 0
            closes = [float(k[4]) for k in btc_klines]
            change_5 = (closes[-1] / closes[-5] - 1) if len(closes) >= 5 else 0
            if change_5 > 0.02:
                return 10
            elif change_5 > 0:
                return 5
            elif change_5 > -0.02:
                return 0
            else:
                return -5
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

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if mode == "paper":
            self._paper_balance -= order_amount
            fee = order_amount * 0.001
            self._paper_balance -= fee
            self._paper_positions[symbol] = {
                "entry_price": price,
                "quantity": quantity,
                "entry_time": now_str,
                "amount": order_amount,
                "tp1_hit": False,
            }
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
                self.positions[symbol] = {
                    "entry_price": filled_price,
                    "quantity": filled_qty,
                    "entry_time": now_str,
                    "amount": order_amount,
                    "tp1_hit": False,
                }
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
        """检查所有持仓，执行止损/止盈"""
        mode = self.config.get("mode", "paper")
        positions = self._paper_positions if mode == "paper" else self.positions

        to_close = []
        for symbol, pos in list(positions.items()):
            current_price = self._get_price_safe(symbol)
            if current_price <= 0:
                continue

            entry_price = pos["entry_price"]
            pnl_pct = (current_price / entry_price - 1) * 100

            sl_pct = self.config.get("stop_loss_pct", 5)
            tp1_pct = self.config.get("take_profit_1_pct", 8)
            tp2_pct = self.config.get("take_profit_2_pct", 15)
            tp1_ratio = self.config.get("tp1_sell_ratio", 0.5)

            # 止损
            if pnl_pct <= -sl_pct:
                to_close.append((symbol, pos["quantity"], "止损"))
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
