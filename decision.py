#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
decision.py —— 把决策模型包成【业务决策工具】的核心层

设计要点（为什么这样分层）:
  1. 对外只有 decide(决策名, 业务上下文) —— 调用方不需要知道底层用的是哪个模型
  2. 每个决策的 state 字段【白名单】写在注册表里 —— 这是防止无关内容拖垮置信度的机制，不是口头纪律
  3. 置信度门控在【本层完成】 —— 对外只给 gate=auto/review，原始概率要显式 debug 才给
  4. 后端只是适配层 —— 换模型只改 _call_backend，调用方零改动

依赖: 仅标准库（Python 3.10+）
配置: 全部走环境变量，本文件不含任何密钥
    OPENROUTER_API_KEY   必填
    JEV_MODEL            默认 typesafe/jev-1.13
    JEV_BASE_URL         默认 https://openrouter.ai
    JEV_DECISIONS_DIR    默认 <本文件目录>/registry

CLI:
    python decision.py list
    python decision.py show ad_keyword_action
    python decision.py decide ad_keyword_action --context context.json [--debug]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

__version__ = "0.1.0"

DEFAULT_MODEL = "typesafe/jev-1.13"
DEFAULT_BASE = "https://openrouter.ai"
RETRYABLE = (429, 500, 502, 503, 524, 529)
HERE = os.path.dirname(os.path.abspath(__file__))


class DecisionError(RuntimeError):
    """注册表错误、字段缺失、后端非 200 —— 一律显式抛出，不静默降级"""


# ------------------------------------------------------------------ 注册表
def registry_dir() -> str:
    return os.environ.get("JEV_DECISIONS_DIR") or os.path.join(HERE, "registry")


def list_decisions(reg_dir: str | None = None) -> list[str]:
    d = reg_dir or registry_dir()
    if not os.path.isdir(d):
        raise DecisionError(f"注册表目录不存在: {d}")
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


def load_decision(name: str, reg_dir: str | None = None) -> dict:
    d = reg_dir or registry_dir()
    path = os.path.join(d, f"{name}.json")
    if not os.path.isfile(path):
        raise DecisionError(f"没有这个决策: {name}（可用: {', '.join(list_decisions(d))}）")
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    for key in ("primary", "questions", "state_fields"):
        if key not in spec:
            raise DecisionError(f"{path} 缺少必填键 `{key}`")
    if spec["primary"] not in spec["questions"]:
        raise DecisionError(f"{path} 的 primary=`{spec['primary']}` 不在 questions 里")
    return spec


# ------------------------------------------------------------------ 门控
def gate(answer: dict, threshold: float = 0.70) -> str:
    """
    把答案折成两档：auto（按答案执行） / review（推人复核）

    choice / score 用 confidence；noul 没有 confidence，用"离 0.5 的距离"折算。
    阈值必须【按动作】定 —— 做错的代价不同（"加否定词"错了便宜，"暂停投放"错了贵）。
    也【不要】把阈值在 choice / score / noul 之间搬运，它们的数不是一回事。
    """
    if answer.get("type") == "noul":
        p = float(answer.get("noul", 0.5))
        return "auto" if abs(p - 0.5) >= max(0.0, 0.5 - threshold) else "review"
    return "auto" if float(answer.get("confidence", 0.0)) >= threshold else "review"


def _threshold_for(spec: dict, outcome: str | None) -> float:
    """先按选中的动作取阈值，取不到再用 default_threshold"""
    table = spec.get("thresholds") or {}
    if outcome and outcome in table:
        return float(table[outcome])
    return float(spec.get("default_threshold", 0.70))


def _cmp(v: float, op: str, target: float) -> bool:
    return {">": v > target, ">=": v >= target,
            "<": v < target, "<=": v <= target, "==": v == target}.get(op, False)


def apply_guards(spec: dict, gate_result: str, signals: dict) -> tuple[str, list[dict]]:
    """
    注册表里声明的硬约束。**只允许把结果往"更保守"推（auto -> review），不允许反向放宽。**

    为什么要有这个：某些判断不能只看置信度。例如"下一步动作是否不可逆"——
    哪怕模型对"该点哪个按钮"很有把握，只要它认为这一步不可逆概率高，就必须转人工。
    把这类不变量写在注册表里，等于把纪律变成机制。
    """
    hits: list[dict] = []
    result = gate_result
    for rb in spec.get("guards") or []:
        sig = rb.get("signal")
        if sig not in signals or signals[sig] is None:
            continue
        try:
            val = float(signals[sig])
        except (TypeError, ValueError):
            continue
        if _cmp(val, rb.get("op", ">"), float(rb.get("value", 0.5))) and rb.get("then") == "review":
            result = "review"
            hits.append({"signal": sig, "value": val,
                         "rule": f"{sig} {rb.get('op', '>')} {rb.get('value')}",
                         "why": rb.get("why", "")})
    return result, hits


# ------------------------------------------------------------------ 后端适配层
def _call_backend(state: dict, questions: dict, *, model: str, timeout: int = 120,
                  retries: int = 2) -> dict:
    """
    唯一与"模型"耦合的地方。换后端只改这个函数。

    已验证的接口事实（2026-09-19 实测）:
      - 端点 /api/alpha/decisions，注意【没有 /v1】
      - 请求体顶层就是 model / state / questions，【不要】套 input 外壳
      - 用 /chat/completions 调它会 400
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise DecisionError("环境变量 OPENROUTER_API_KEY 未设置")
    base = (os.environ.get("JEV_BASE_URL") or DEFAULT_BASE).rstrip("/")
    url = f"{base}/api/alpha/decisions"
    payload = json.dumps({"model": model, "state": state, "questions": questions},
                         ensure_ascii=False).encode("utf-8")

    last: str = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", "Bearer " + key)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            last = f"HTTP {e.code}: {body[:500]}"
            if e.code in RETRYABLE and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise DecisionError(last) from None
        except Exception as e:                                  # noqa: BLE001
            last = repr(e)
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise DecisionError(last) from None
    raise DecisionError(last)


# ------------------------------------------------------------------ 对外唯一入口
def decide(name: str, context: dict, *, debug: bool = False, model: str | None = None,
           reg_dir: str | None = None) -> dict:
    """
    做一次业务决策。

    name     : 注册表里的决策名
    context  : 业务上下文（扁平 dict）。**只保留注册表声明的字段**，其余被裁掉并在
               返回的 trimmed 里列出来 —— 裁掉不是"省 token"，是为了不让无关内容
               扭曲置信度（实测：同一判断加 26k tokens 无关内容，置信度可偏 ±0.33）。
    debug    : True 时附上原始 answers 与 probabilities；False 只给结论
    """
    spec = load_decision(name, reg_dir)

    fields = spec["state_fields"]
    state = {k: context[k] for k in fields if k in context}
    missing = [k for k in fields if k not in context]
    if missing:
        raise DecisionError(
            f"缺少必填字段: {', '.join(missing)}。"
            f"注意：需要计算的值（比例/差值/计数）请先在你的代码里算好再传。")
    trimmed = sorted(set(context) - set(fields))

    t0 = time.perf_counter()
    resp = _call_backend(state, spec["questions"],
                         model=model or os.environ.get("JEV_MODEL") or DEFAULT_MODEL)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    answers = resp.get("answers") or {}
    if not answers:
        raise DecisionError(f"后端没返回 answers: {json.dumps(resp, ensure_ascii=False)[:300]}")

    primary = spec["primary"]
    if primary not in answers:
        raise DecisionError(f"后端没返回 primary 问题 `{primary}`: {list(answers)}")
    pa = answers[primary]

    outcome = pa.get("choice") if pa.get("type") == "choice" else pa.get("score")
    conf = pa.get("noul") if pa.get("type") == "noul" else pa.get("confidence")

    out = {
        "decision": name,
        "outcome": outcome,
        "confidence": conf,
        "gate": gate(pa, _threshold_for(spec, outcome if isinstance(outcome, str) else None)),
        "signals": {k: (v.get("noul") if v.get("type") == "noul" else v.get("score"))
                    for k, v in answers.items() if k != primary},
        "model": resp.get("model"),
        "request_id": resp.get("id"),
        "elapsed_ms": elapsed_ms,
        "usage": resp.get("usage"),
        "trimmed": trimmed,
        "version": __version__,
    }
    out["gate"], guard_hits = apply_guards(spec, out["gate"], out["signals"])
    if guard_hits:
        out["guard_hits"] = guard_hits
    if debug:
        out["answers"] = answers
    return out


# ------------------------------------------------------------------ CLI
def _main() -> int:
    ap = argparse.ArgumentParser(prog="decision.py", description="业务决策工具（核心层）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出可用决策")
    p = sub.add_parser("show", help="打印某个决策的注册表定义")
    p.add_argument("name")
    p = sub.add_parser("decide", help="做一次决策")
    p.add_argument("name")
    p.add_argument("--context", required=True, help="上下文 JSON 文件路径")
    p.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    try:
        if args.cmd == "list":
            for n in list_decisions():
                print(f"  {n}")
            return 0
        if args.cmd == "show":
            print(json.dumps(load_decision(args.name), ensure_ascii=False, indent=2))
            return 0
        with open(args.context, encoding="utf-8") as f:
            ctx = json.load(f)
        print(json.dumps(decide(args.name, ctx, debug=args.debug), ensure_ascii=False, indent=2))
        return 0
    except DecisionError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main())
