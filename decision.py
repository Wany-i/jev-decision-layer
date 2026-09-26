#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
decision.py —— 把决策模型包成【业务决策工具】的核心层

设计要点（为什么这样分层）:
  1. 对外提供注册表 decide() 与动态 choose_candidate() —— 调用方不需要知道底层模型
  2. 注册表决策的 state 字段【白名单】写在注册表里；动态选择由调用方先裁剪 state
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
    python decision.py choose --input request.json [--debug]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

__version__ = "0.3.0"

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

    choice / score 用 confidence；noul 没有 confidence，用"离 0.5 的距离"折算
    —— 阈值 0.70 表示要求 |p-0.5| >= 0.20，即 p>=0.70 或 p<=0.30 才放行。

    阈值必须【按动作】定 —— 做错的代价不同（"加否定词"错了便宜，"暂停投放"错了贵）。
    也【不要】把阈值在 choice / score / noul 之间搬运，它们的数不是一回事。
    """
    if answer.get("type") == "noul":
        p = float(answer.get("noul", 0.5))
        need = max(0.0, threshold - 0.5)      # 需要的"离中点距离"
        return "auto" if abs(p - 0.5) >= need else "review"
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


def choose_candidate(goal: str, state: dict, candidates: list[dict], *,
                     threshold: float = 0.75, debug: bool = False,
                     model: str | None = None) -> dict:
    """Choose one observed candidate without executing it.

    The caller owns observation, risk classification, execution, and read-back.
    Candidate risk must be explicit so an irreversible action never receives an
    automatic execution gate merely because the model is confident.
    """
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 1000:
        raise DecisionError("goal 必须是 1–1000 字符的非空字符串")
    if not isinstance(state, dict):
        raise DecisionError("state 必须是对象")
    try:
        state_size = len(json.dumps(state, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise DecisionError("state 必须能序列化为有限 JSON") from exc
    if state_size > 32000:
        raise DecisionError("state 超过 32000 字节；请只传本轮判断需要的信息")
    if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold) or not 0 <= threshold <= 1):
        raise DecisionError("threshold 必须是 0–1 之间的有限数值")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 100:
        raise DecisionError("candidates 必须包含 1–100 个候选动作")

    allowed_risks = {"read_only", "reversible", "irreversible"}
    by_id: dict[str, dict] = {}
    criteria: dict[str, str] = {}
    for item in candidates:
        if not isinstance(item, dict):
            raise DecisionError("每个候选动作必须是对象")
        candidate_id = item.get("id")
        label = item.get("label")
        risk = item.get("risk")
        if (not isinstance(candidate_id, str) or not candidate_id.strip()
                or candidate_id != candidate_id.strip()
                or len(candidate_id) > 64 or any(ord(c) < 32 for c in candidate_id)
                or candidate_id.casefold() == "other" or candidate_id in by_id):
            raise DecisionError("候选 id 必须唯一、非空，且不能占用 other")
        if (not isinstance(label, str) or not label.strip() or len(label) > 160
                or any(ord(c) < 32 for c in label)):
            raise DecisionError("候选 label 必须是 1–160 字符的单行文本")
        if not isinstance(risk, str) or risk not in allowed_risks:
            raise DecisionError("候选 risk 必须是 read_only、reversible 或 irreversible")
        by_id[candidate_id] = {"label": label, "risk": risk}
        criteria[candidate_id] = f"{label} (risk: {risk})"
    criteria["other"] = "No candidate safely advances the goal."

    questions = {
        "action": {
            "type": "choice",
            "instructions": (
                "Choose exactly one observed candidate for the goal. "
                "Choose other if none safely advances it. Never invent an id. "
                f"Goal: {goal.strip()}"
            ),
            "criteria": criteria,
        }
    }
    started = time.perf_counter()
    response = _call_backend(state, questions,
                             model=model or os.environ.get("JEV_MODEL") or DEFAULT_MODEL)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    answers = response.get("answers") if isinstance(response, dict) else None
    answer = answers.get("action") if isinstance(answers, dict) else None
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise DecisionError("Jev 未返回有效的 action choice；没有动作被执行")
    choice = answer.get("choice")
    confidence = answer.get("confidence")
    probabilities = answer.get("probabilities")
    if (not isinstance(choice, str) or choice not in criteria
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence) or not 0 <= confidence <= 1
            or not isinstance(probabilities, dict)
            or set(probabilities) != set(criteria)
            or any(isinstance(p, bool) or not isinstance(p, (int, float))
                   or not math.isfinite(p) or not 0 <= p <= 1
                   for p in probabilities.values())
            or abs(sum(probabilities.values()) - 1) >= 0.02
            or probabilities[choice] < max(probabilities.values()) - 1e-6):
        raise DecisionError("Jev 的候选答案或概率分布无效；没有动作被执行")

    selected = by_id.get(choice)
    if selected is None:
        reason = "no_safe_candidate"
    elif selected["risk"] == "irreversible":
        reason = "irreversible"
    elif confidence < threshold:
        reason = "low_confidence"
    else:
        reason = "passed"
    result = {
        "outcome": choice,
        "label": selected["label"] if selected else None,
        "risk": selected["risk"] if selected else None,
        "confidence": confidence,
        "gate": "auto" if reason == "passed" else "review",
        "gate_reason": reason,
        "model": response.get("model"),
        "request_id": response.get("id"),
        "elapsed_ms": elapsed_ms,
        "usage": response.get("usage"),
        "version": __version__,
    }
    if debug:
        result["answers"] = response["answers"]
    return result


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
    p = sub.add_parser("choose", help="从本轮动态候选中选一个动作，不负责执行")
    p.add_argument("--input", required=True, help="JSON 输入文件，或 - 表示标准输入")
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
        if args.cmd == "choose":
            if args.input == "-":
                data = json.load(sys.stdin)
            else:
                with open(args.input, encoding="utf-8") as f:
                    data = json.load(f)
            if not isinstance(data, dict):
                raise DecisionError("choose 输入必须是 JSON 对象")
            result = choose_candidate(
                data.get("goal"), data.get("state"), data.get("candidates"),
                threshold=data.get("threshold", 0.75), debug=args.debug,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
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
