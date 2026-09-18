#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
quickstart.py —— 三个最小可用示例

跑之前先设好密钥（本仓库任何文件都不含密钥）:
    Windows (PowerShell):  $env:OPENROUTER_API_KEY = "sk-or-v1-..."
    Windows (Git Bash):    export OPENROUTER_API_KEY="sk-or-v1-..."
    macOS / Linux:         export OPENROUTER_API_KEY="sk-or-v1-..."

    python examples/quickstart.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision import DecisionError, decide  # noqa: E402


def banner(t: str) -> None:
    print("\n" + "=" * 78)
    print("### " + t)


def show(r: dict) -> None:
    print(f"  结论     : {r['outcome']}")
    print(f"  置信度   : {r['confidence']}")
    print(f"  门控     : {r['gate']}   ← auto 才可自动执行，review 必须转人工")
    if r.get("guard_hits"):
        for h in r["guard_hits"]:
            print(f"  硬约束   : {h['signal']}={h['value']} 命中 {h['rule']} — {h['why']}")
    if r["signals"]:
        print(f"  其它信号 : {r['signals']}")
    if r["trimmed"]:
        print(f"  已裁字段 : {r['trimmed']}  ← 白名单之外的字段不会进入判断")
    print(f"  耗时成本 : {r['elapsed_ms']}ms  {r['usage']}")


def main() -> int:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("请先设置环境变量 OPENROUTER_API_KEY")
        return 2

    # ---------------------------------------------------------------- 1
    banner("1) 广告关键词：注意 ACOS 是【我们自己算好】再传进去的")
    ctx = {
        "目标ACOS": 0.30,
        "关键词": "car phone holder magnetic",
        "匹配方式": "widened",
        "曝光": 1840,
        "点击": 11,
        "花费": 6.85,
        "销售额": 0.0,
        "订单": 0,
        "运行天数": 9,
        "当前出价": 0.62,
        "实测ACOS": "无成交",          # 算好了再传：这个模型不做算术
    }
    try:
        show(decide("ad_keyword_action", ctx))
    except DecisionError as e:
        print("  失败:", e)

    # ---------------------------------------------------------------- 2
    banner("2) 浏览器风险闸门：候选动作不可逆时，硬约束会把它升级成人工复核")
    steps = [
        {"下一步候选动作": "在搜索框输入出发地并回车",
         "可见文本": "搜索航班 出发地 目的地 日期", "已完成步数": 1},
        {"下一步候选动作": "点击「确认支付」提交订单",
         "可见文本": "订单确认 支付方式 信用卡末四位 8842 确认支付", "已完成步数": 7},
    ]
    for i, s in enumerate(steps, 1):
        print(f"\n  --- 场景 {i}：{s['下一步候选动作']}")
        try:
            show(decide("browser_step", {
                "任务目标": "查到明天北京到上海的最早航班并完成预订",
                "当前URL": "https://example.com/flights", "页面标题": "Flights",
                "已完成步数": s["已完成步数"],
                "可见文本": s["可见文本"],
                "下一步候选动作": s["下一步候选动作"],
            }))
        except DecisionError as e:
            print("  失败:", e)

    # ---------------------------------------------------------------- 3
    banner("3) 客服分流（英文示例 —— 官方说英文准确率最高）")
    try:
        show(decide("support_triage", {
            "subject": "Charged twice for order A-104",
            "body": "I was charged twice for the same order. Please refund the duplicate charge today.",
            "customer_tier": "pro",
            "prior_contacts": 2,
        }))
    except DecisionError as e:
        print("  失败:", e)

    print("\n" + "=" * 78)
    print("读法：gate=auto 才按结论自动执行；gate=review 一律转人工。")
    print("      置信度会随 state 形状变化（实测同一判断可偏 ±0.33），阈值要在你自己的 data 上调。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
