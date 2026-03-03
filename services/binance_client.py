"""
Binance REST API 轻量封装
使用 requests + HMAC-SHA256 签名，不依赖第三方 SDK
"""

import time
import hmac
import hashlib
import logging
from urllib.parse import urlencode
from typing import Optional, Dict, List

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com"

_HEADERS = {
    "User-Agent": "Tigger/1.0",
    "Content-Type": "application/x-www-form-urlencoded",
}


class BinanceClient:
    """Binance REST API 客户端"""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        if api_key:
            self.session.headers["X-MBX-APIKEY"] = api_key

    # ------------------------------------------------------------------
    # 签名
    # ------------------------------------------------------------------

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _public_get(self, path: str, params: dict = None, timeout: int = 15) -> dict:
        url = BASE_URL + path
        resp = self.session.get(url, params=params or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _signed_get(self, path: str, params: dict = None, timeout: int = 15) -> dict:
        url = BASE_URL + path
        signed = self._sign(params or {})
        resp = self.session.get(url, params=signed, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _signed_post(self, path: str, params: dict = None, timeout: int = 15) -> dict:
        url = BASE_URL + path
        signed = self._sign(params or {})
        resp = self.session.post(url, data=signed, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _signed_delete(self, path: str, params: dict = None, timeout: int = 15) -> dict:
        url = BASE_URL + path
        signed = self._sign(params or {})
        resp = self.session.delete(url, params=signed, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_top_symbols(self, n: int = 20) -> List[str]:
        """
        获取市值 TOP N 的 USDT 交易对
        通过 24h ticker 按 quoteVolume 降序排列
        """
        tickers = self._public_get("/api/v3/ticker/24hr")
        usdt_tickers = [
            t for t in tickers
            if t["symbol"].endswith("USDT")
            and not t["symbol"].endswith("DOWNUSDT")
            and not t["symbol"].endswith("UPUSDT")
            and "BUSD" not in t["symbol"]
        ]
        usdt_tickers.sort(key=lambda t: float(t.get("quoteVolume", 0)), reverse=True)
        return [t["symbol"] for t in usdt_tickers[:n]]

    def get_klines(
        self,
        symbol: str,
        interval: str = "4h",
        limit: int = 200,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[list]:
        """
        获取K线数据
        interval: 1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M
        返回: [[open_time, open, high, low, close, volume, close_time, ...], ...]
        """
        params: Dict = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return self._public_get("/api/v3/klines", params)

    def get_ticker_price(self, symbol: str) -> float:
        """获取某交易对实时价格"""
        data = self._public_get("/api/v3/ticker/price", {"symbol": symbol})
        return float(data["price"])

    def get_all_prices(self) -> Dict[str, float]:
        """获取所有交易对价格"""
        data = self._public_get("/api/v3/ticker/price")
        return {item["symbol"]: float(item["price"]) for item in data}

    def get_exchange_info(self, symbol: str) -> dict:
        """获取交易对信息（精度、最小下单量等）"""
        data = self._public_get("/api/v3/exchangeInfo", {"symbol": symbol})
        for s in data.get("symbols", []):
            if s["symbol"] == symbol:
                return s
        return {}

    # ------------------------------------------------------------------
    # 需要签名的接口
    # ------------------------------------------------------------------

    def get_account_balance(self) -> Dict[str, dict]:
        """
        查询账户余额
        返回: {asset: {"free": float, "locked": float}, ...}
        """
        data = self._signed_get("/api/v3/account")
        result = {}
        for b in data.get("balances", []):
            free = float(b["free"])
            locked = float(b["locked"])
            if free > 0 or locked > 0:
                result[b["asset"]] = {"free": free, "locked": locked}
        return result

    def get_usdt_balance(self) -> float:
        """获取 USDT 可用余额"""
        balances = self.get_account_balance()
        usdt = balances.get("USDT", {})
        return usdt.get("free", 0.0)

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        """
        市价单
        side: BUY / SELL
        quantity: 下单数量
        """
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": self._format_quantity(symbol, quantity),
        }
        return self._signed_post("/api/v3/order", params)

    def place_market_order_quote(self, symbol: str, side: str, quote_amount: float) -> dict:
        """
        按 USDT 金额市价买入
        使用 quoteOrderQty 参数
        """
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quoteOrderQty": f"{quote_amount:.2f}",
        }
        return self._signed_post("/api/v3/order", params)

    def get_open_orders(self, symbol: str = None) -> list:
        """查询当前挂单"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._signed_get("/api/v3/openOrders", params)

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """撤销订单"""
        params = {"symbol": symbol, "orderId": order_id}
        return self._signed_delete("/api/v3/order", params)

    def get_order(self, symbol: str, order_id: int) -> dict:
        """查询订单状态"""
        params = {"symbol": symbol, "orderId": order_id}
        return self._signed_get("/api/v3/order", params)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _format_quantity(self, symbol: str, quantity: float) -> str:
        """根据交易对精度格式化数量"""
        try:
            info = self.get_exchange_info(symbol)
            for f in info.get("filters", []):
                if f["filterType"] == "LOT_SIZE":
                    step = float(f["stepSize"])
                    precision = len(f["stepSize"].rstrip("0").split(".")[-1]) if "." in f["stepSize"] else 0
                    adjusted = int(quantity / step) * step
                    return f"{adjusted:.{precision}f}"
        except Exception:
            pass
        return f"{quantity:.6f}"

    def test_connectivity(self) -> bool:
        """测试 API 连通性"""
        try:
            self._public_get("/api/v3/ping")
            return True
        except Exception:
            return False

    def test_auth(self) -> bool:
        """测试 API Key 是否有效"""
        try:
            self._signed_get("/api/v3/account")
            return True
        except Exception:
            return False
