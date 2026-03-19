"""
调试脚本：验证 300482、920187、920626 为何能/不能通过触底反弹条件
运行：python -m strategies.debug_verify
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.touch_bottom_rebound import (
    _fetch_all_snapshot, _fetch_kline, _append_today_if_needed, _check_conditions,
)

def main():
    codes = ["300482", "920187", "920626"]
    print("获取全A股快照...")
    snapshot = _fetch_all_snapshot()
    if snapshot is None:
        print("快照获取失败")
        return
    snap_map = {str(r["code"]).zfill(6): r for _, r in snapshot.iterrows()}

    for code in codes:
        print(f"\n===== {code} =====")
        row = snap_map.get(code)
        if row is None:
            print("  不在快照中(可能非交易时段或代码有误)")
            continue
        print(f"  名称: {row['name']}, 涨跌幅: {row['change_pct']:.2f}%")
        if row["change_pct"] <= 0:
            print("  -> 不满足条件3(涨跌幅>0%)")
            continue
        kline = _fetch_kline(code)
        if kline is None:
            print("  K线获取失败")
            continue
        kline = _append_today_if_needed(kline, code, row)
        ok, reason = _check_conditions(kline, float(row["change_pct"]), code=code)
        print(f"  结果: {'通过' if ok else '未通过'} {reason}")

if __name__ == "__main__":
    main()
