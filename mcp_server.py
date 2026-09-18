#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mcp_server.py —— 把决策层暴露成 MCP 工具（薄壳）

工具名刻意【不带 jev】：调用方看到的是"业务决策"，不是"某个模型"。
换后端时调用方零改动。

依赖: 无（纯标准库，手写 stdio JSON-RPC）
协议: MCP stdio，一行一个 JSON-RPC 消息

注册到 MCP 客户端（以 Cursor / Cline 为例）:
    {
      "mcpServers": {
        "decision-layer": {
          "command": "python",
          "args": ["C:/path/to/jev-decision-layer/mcp_server.py"],
          "env": { "OPENROUTER_API_KEY": "sk-or-v1-..." }
        }
      }
    }

自测（不需要 MCP 客户端）:
    python mcp_server.py --selftest
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decision import (DecisionError, __version__, decide,  # noqa: E402
                      list_decisions, load_decision)

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "decision-layer", "version": __version__}


def _tools() -> list[dict]:
    names = []
    try:
        names = list_decisions()
    except DecisionError:
        pass
    catalog = []
    for n in names:
        try:
            spec = load_decision(n)
            catalog.append(f"  - {n}: {spec.get('description', '')} "
                           f"(必填字段: {', '.join(spec['state_fields'])})")
        except DecisionError:
            continue
    catalog_txt = "\n".join(catalog) or "  （注册表为空）"

    return [
        {
            "name": "list_decisions",
            "description": "列出当前可用的业务决策及其必填字段。不确定该调哪个时先调它。",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "decide",
            "description": (
                "对一个业务决策做一次判断，返回结论 + 置信度 + 门控。\n"
                "**门控是结果的一部分**：gate=auto 才可按结论自动执行，gate=review 表示必须转人工。\n"
                "注意：需要算术的值（比例、差值、计数）请在调用前自己算好再放进 context。\n\n"
                f"当前可用决策：\n{catalog_txt}"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "description": "决策名，见 list_decisions"},
                    "context": {
                        "type": "object",
                        "description": "业务上下文（扁平对象）。只需给该决策声明的字段；"
                                       "多给的字段会被裁掉并在返回的 trimmed 里列出。",
                    },
                    "debug": {
                        "type": "boolean",
                        "description": "是否附上原始答案与概率分布（排障用，默认 false）",
                    },
                },
                "required": ["decision", "context"],
            },
        },
    ]


def call_tool(name: str, args: dict) -> dict:
    if name == "list_decisions":
        rows = []
        for n in list_decisions():
            spec = load_decision(n)
            rows.append({"decision": n, "description": spec.get("description"),
                         "required_fields": spec["state_fields"],
                         "primary": spec["primary"]})
        return {"content": [{"type": "text",
                             "text": "```json\n" + json.dumps(rows, ensure_ascii=False, indent=2) + "\n```"}]}

    if name == "decide":
        try:
            r = decide(args["decision"], args.get("context") or {},
                       debug=bool(args.get("debug")))
        except DecisionError as e:
            # 把结构化错误回给 agent，让它能自己修（例如缺字段）
            return {"content": [{"type": "text", "text": f"ERROR: {e}"}], "isError": True}
        head = (f"{r['decision']} → {r['outcome']}  "
                f"(confidence={r['confidence']}, gate={r['gate']}, {r['elapsed_ms']}ms)")
        if r.get("guard_hits"):
            head += "\n硬约束命中：" + "; ".join(
                f"{h['signal']}={h['value']} {h['rule']}" for h in r["guard_hits"])
        if r["trimmed"]:
            head += f"\n已裁掉的无关字段：{', '.join(r['trimmed'])}"
        return {"content": [
            {"type": "text", "text": head},
            {"type": "text", "text": "```json\n" + json.dumps(r, ensure_ascii=False, indent=2) + "\n```"},
        ]}

    raise ValueError(f"未知工具: {name}")


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result(rid, result):
    _send({"jsonrpc": "2.0", "id": rid, "result": result})


def _error(rid, code, message):
    _send({"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}})


def handle(msg: dict) -> None:
    method, rid = msg.get("method"), msg.get("id")
    if method == "initialize":
        _result(rid, {"protocolVersion": PROTOCOL_VERSION,
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": SERVER_INFO})
    elif method in ("notifications/initialized", "initialized"):
        return
    elif method == "tools/list":
        _result(rid, {"tools": _tools()})
    elif method == "tools/call":
        p = msg.get("params") or {}
        try:
            _result(rid, call_tool(p.get("name", ""), p.get("arguments") or {}))
        except Exception as e:                                   # noqa: BLE001
            _result(rid, {"content": [{"type": "text", "text": f"ERROR: {e}"}], "isError": True})
    elif method == "ping":
        _result(rid, {})
    elif rid is not None:
        _error(rid, -32601, f"Method not found: {method}")


def selftest() -> int:
    print("[1] 可用决策:", ", ".join(list_decisions()))
    print("[2] tools/list ->", [t["name"] for t in _tools()])
    print("[3] tools/call decide ...")
    out = call_tool("decide", {
        "decision": "support_triage",
        "context": {"subject": "Charged twice", "body": "I was charged twice for order A-104. Please refund the duplicate charge today.",
                    "customer_tier": "pro", "prior_contacts": 1},
    })
    print("   ", "❌" if out.get("isError") else "✅", out["content"][0]["text"].replace("\n", "\n    "))
    return 1 if out.get("isError") else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            handle(msg)
        except Exception as e:                                   # noqa: BLE001
            if msg.get("id") is not None:
                _error(msg["id"], -32603, str(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
