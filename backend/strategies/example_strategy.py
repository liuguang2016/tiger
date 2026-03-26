"""
示例策略 - 策略选股模板
可复制此文件创建自定义策略，需定义 NAME 和 run() 函数
"""

NAME = "示例策略"


def run() -> list:
    """
    返回 List[Dict]，每项需包含 stock_code、stock_name
    可含 score、drop_pct、volume_ratio、reason、tags、pattern 等
    """
    return [
        {"stock_code": "600519", "stock_name": "贵州茅台", "score": 85, "reason": "示例"},
        {"stock_code": "000858", "stock_name": "五粮液", "score": 78, "reason": "示例"},
    ]
