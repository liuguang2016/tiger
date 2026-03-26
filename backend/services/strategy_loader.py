"""
策略选股加载器
扫描 strategies/ 目录下的 .py 文件，动态加载并执行策略
"""

import importlib.util
import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 策略目录：项目根目录下的 strategies/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRATEGIES_DIR = os.path.join(PROJECT_ROOT, 'strategies')

# 规范化策略输出的默认字段
DEFAULT_STOCK = {
    'score': 0,
    'drop_pct': 0,
    'volume_ratio': 0,
    'close': 0,
    'change_pct': 0,
    'reason': '',
    'tags': [],
    'pattern': '',
    'stab_confidence': 0,
    'market_env': '',
    'platform_days': 0,
    'probe_score': 0,
}


def _normalize_stock(item: dict) -> dict:
    """将策略返回的 dict 补全为 save_pool_stocks 所需格式"""
    out = dict(DEFAULT_STOCK)
    out['stock_code'] = str(item.get('stock_code', '')).strip()
    out['stock_name'] = str(item.get('stock_name', '')).strip()
    for k in ['score', 'drop_pct', 'volume_ratio', 'close', 'change_pct',
              'reason', 'tags', 'pattern', 'stab_confidence', 'market_env',
              'platform_days', 'probe_score']:
        if k in item and item[k] is not None:
            out[k] = item[k]
    if isinstance(out.get('tags'), str):
        try:
            out['tags'] = json.loads(out['tags'])
        except (json.JSONDecodeError, TypeError):
            out['tags'] = []
    return out


def list_strategies() -> List[Dict]:
    """
    扫描 strategies/ 目录，返回策略列表
    每个策略：{ id, name }
    """
    if not os.path.isdir(STRATEGIES_DIR):
        return []

    strategies = []
    for fname in sorted(os.listdir(STRATEGIES_DIR)):
        if fname.startswith('_') or not fname.endswith('.py'):
            continue
        module_name = fname[:-3]
        try:
            spec = importlib.util.spec_from_file_location(
                f"strategies.{module_name}",
                os.path.join(STRATEGIES_DIR, fname)
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                name = getattr(mod, 'NAME', module_name)
                run_fn = getattr(mod, 'run', None)
                if callable(run_fn):
                    strategies.append({'id': module_name, 'name': name})
                else:
                    logger.warning("策略 %s 缺少 run 函数，已跳过", fname)
        except Exception as e:
            logger.warning("加载策略 %s 失败: %s", fname, e)

    return strategies


def run_strategy(strategy_id: str) -> List[dict]:
    """
    执行指定策略，返回规范化后的 stock list
    strategy_id: 模块名（不含 .py）
    """
    path = os.path.join(STRATEGIES_DIR, f"{strategy_id}.py")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"策略不存在: {strategy_id}")

    spec = importlib.util.spec_from_file_location(
        f"strategies.{strategy_id}",
        path
    )
    if not spec or not spec.loader:
        raise ValueError(f"无法加载策略: {strategy_id}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    run_fn = getattr(mod, 'run', None)
    if not callable(run_fn):
        raise ValueError(f"策略 {strategy_id} 缺少 run 函数")

    raw = run_fn()
    if not isinstance(raw, list):
        raise TypeError(f"策略 {strategy_id} 的 run() 应返回 list，实际为 {type(raw)}")

    result = []
    for item in raw:
        if not isinstance(item, dict):
            logger.warning("策略返回项非 dict，已跳过: %s", item)
            continue
        if not item.get('stock_code') or not item.get('stock_name'):
            logger.warning("策略返回项缺少 stock_code 或 stock_name，已跳过: %s", item)
            continue
        result.append(_normalize_stock(item))

    return result
