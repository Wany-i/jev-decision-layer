#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_offline.py —— 离线单元测试（不需要 API key，不需要联网）

CI 就靠它。它把后端替换成假实现，只验"这一层自己的逻辑"：
注册表校验、state 裁剪、门控、硬约束 —— 这几件事都不该依赖网络。

    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import decision as D  # noqa: E402

REG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "registry")


CANNED: dict = {}


def fake_backend(state, questions, *, model=None, timeout=0, retries=0):
    """
    假后端。注意：decide() 会先把 state 按白名单裁剪，所以假后端拿不到测试塞进去的
    额外键 —— 需要指定答案时用模块级 CANNED。
    """
    if CANNED:
        answers = dict(CANNED)
    else:
        answers = {
            q: ({"type": "choice", "choice": "other",
                 "probabilities": {"other": 1.0}, "confidence": 0.10}
                if spec["type"] == "choice" else
                {"type": "noul", "noul": 0.10} if spec["type"] == "noul" else
                {"type": "score", "score": 0.0, "probabilities": {"0": 1.0}, "confidence": 0.10})
            for q, spec in questions.items()
        }
    return {"model": "fake-model-1", "id": "req-1",
            "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 0.0}}


class GateTest(unittest.TestCase):
    """门控：choice/score 看 confidence，noul 看离 0.5 的距离"""

    def test_choice_above_threshold(self):
        self.assertEqual(D.gate({"type": "choice", "confidence": 0.80}, 0.70), "auto")

    def test_choice_below_threshold(self):
        self.assertEqual(D.gate({"type": "choice", "confidence": 0.69}, 0.70), "review")

    def test_choice_at_threshold_is_auto(self):
        self.assertEqual(D.gate({"type": "choice", "confidence": 0.70}, 0.70), "auto")

    def test_score_uses_confidence_too(self):
        self.assertEqual(D.gate({"type": "score", "score": 1.4, "confidence": 0.75}, 0.70), "auto")

    def test_noul_far_from_half_is_auto(self):
        self.assertEqual(D.gate({"type": "noul", "noul": 0.95}, 0.70), "auto")

    def test_noul_near_half_is_review(self):
        for p in (0.40, 0.50, 0.60):
            self.assertEqual(D.gate({"type": "noul", "noul": p}, 0.70), "review",
                             msg=f"noul={p} 应该判 review")

    def test_noul_ignores_confidence_key(self):
        """noul 没有 confidence 字段，不能因为误传了 confidence 就改判据"""
        self.assertEqual(D.gate({"type": "noul", "noul": 0.51, "confidence": 0.99}, 0.70), "review")


class GuardsTest(unittest.TestCase):
    """硬约束：只能把 auto 收紧成 review，绝不能反向放宽"""

    def test_guard_escalates(self):
        spec = {"guards": [{"signal": "risk", "op": ">", "value": 0.3, "then": "review"}]}
        gate, hits = D.apply_guards(spec, "auto", {"risk": 0.9})
        self.assertEqual(gate, "review")
        self.assertEqual(len(hits), 1)

    def test_guard_does_not_fire(self):
        spec = {"guards": [{"signal": "risk", "op": ">", "value": 0.3, "then": "review"}]}
        gate, hits = D.apply_guards(spec, "auto", {"risk": 0.1})
        self.assertEqual(gate, "auto")
        self.assertEqual(hits, [])

    def test_guard_cannot_loosen(self):
        """即使规则想把它推成 auto，也不允许覆盖已有的 review"""
        gate, _ = D.apply_guards({"guards": []}, "review", {})
        self.assertEqual(gate, "review")

    def test_guard_then_must_be_review(self):
        spec = {"guards": [{"signal": "risk", "op": ">", "value": 0.3, "then": "auto"}]}
        gate, hits = D.apply_guards(spec, "auto", {"risk": 0.99})
        self.assertEqual(gate, "auto")
        self.assertEqual(hits, [])

    def test_guard_missing_signal_is_ignored(self):
        spec = {"guards": [{"signal": "nope", "op": ">", "value": 0.3, "then": "review"}]}
        gate, hits = D.apply_guards(spec, "auto", {"risk": 0.9})
        self.assertEqual((gate, hits), ("auto", []))

    def test_all_operators(self):
        """把 5 个运算符在边界 0.5 的上下两侧都钉住，区分严格与含等号"""
        cases = {
            ">":  {0.4: False, 0.5: False, 0.6: True},
            ">=": {0.4: False, 0.5: True,  0.6: True},
            "<":  {0.4: True,  0.5: False, 0.6: False},
            "<=": {0.4: True,  0.5: True,  0.6: False},
            "==": {0.4: False, 0.5: True,  0.6: False},
        }
        for op, table in cases.items():
            for val, expect in table.items():
                spec = {"guards": [{"signal": "s", "op": op, "value": 0.5, "then": "review"}]}
                gate, _ = D.apply_guards(spec, "auto", {"s": val})
                self.assertEqual(gate == "review", expect, msg=f"op={op} val={val}")

    def test_unknown_operator_is_ignored(self):
        """未知运算符不能静默当成命中，也不能当成永远命中"""
        spec = {"guards": [{"signal": "s", "op": "~=", "value": 0.5, "then": "review"}]}
        gate, hits = D.apply_guards(spec, "auto", {"s": 0.9})
        self.assertEqual((gate, hits), ("auto", []))

    def test_non_numeric_signal_is_ignored(self):
        spec = {"guards": [{"signal": "s", "op": ">", "value": 0.5, "then": "review"}]}
        gate, hits = D.apply_guards(spec, "auto", {"s": "高"})
        self.assertEqual((gate, hits), ("auto", []))


class RegistryTest(unittest.TestCase):

    def test_shipped_registries_are_valid(self):
        names = D.list_decisions(REG)
        self.assertGreaterEqual(len(names), 3)
        for n in names:
            spec = D.load_decision(n, REG)
            self.assertIn(spec["primary"], spec["questions"], msg=n)
            self.assertTrue(spec["state_fields"], msg=n)
            for q, qspec in spec["questions"].items():
                self.assertIn(qspec["type"], ("choice", "score", "noul"), msg=f"{n}.{q}")
                if qspec["type"] in ("choice", "score"):
                    self.assertIn("criteria", qspec, msg=f"{n}.{q} 缺少 criteria")
                    self.assertIn("instructions", qspec, msg=f"{n}.{q} 缺少 instructions")

    def test_choice_criteria_is_object(self):
        for n in D.list_decisions(REG):
            for q, qspec in D.load_decision(n, REG)["questions"].items():
                if qspec["type"] == "choice":
                    self.assertIsInstance(qspec["criteria"], dict, msg=f"{n}.{q}")

    def test_score_criteria_is_list(self):
        for n in D.list_decisions(REG):
            for q, qspec in D.load_decision(n, REG)["questions"].items():
                if qspec["type"] == "score":
                    self.assertIsInstance(qspec["criteria"], list, msg=f"{n}.{q}")
                    self.assertGreaterEqual(len(qspec["criteria"]), 2, msg=f"{n}.{q}")

    def test_choice_should_offer_other(self):
        """choice 应带 other 兜底，否则模型只能在给定选项里挑个最不坏的"""
        for n in D.list_decisions(REG):
            for q, qspec in D.load_decision(n, REG)["questions"].items():
                if qspec["type"] == "choice":
                    self.assertIn("other", qspec["criteria"], msg=f"{n}.{q} 建议补 other 选项")

    def test_unknown_decision_raises(self):
        with self.assertRaises(D.DecisionError):
            D.load_decision("no_such_decision", REG)


class DecideTest(unittest.TestCase):
    """decide() 的整体行为，后端被换成假的"""

    def setUp(self):
        self._orig = D._call_backend
        D._call_backend = fake_backend

    def tearDown(self):
        D._call_backend = self._orig
        CANNED.clear()

    def ctx(self, **over):
        base = {"关键词": "k", "匹配方式": "widened", "曝光": 1, "点击": 1, "花费": 1.0,
                "销售额": 0.0, "订单": 0, "运行天数": 1, "当前出价": 0.5,
                "实测ACOS": "无成交", "目标ACOS": 0.3}
        base.update(over)
        return base

    def browser_ctx(self):
        return {"任务目标": "g", "当前URL": "u", "页面标题": "t",
                "可见文本": "v", "下一步候选动作": "a", "已完成步数": 1}

    def test_trimmed_reports_extra_fields(self):
        r = D.decide("ad_keyword_action", self.ctx(无关字段="不该进去", 另一个=123), reg_dir=REG)
        self.assertCountEqual(r["trimmed"], ["另一个", "无关字段"])

    def test_missing_field_raises_with_name(self):
        c = self.ctx()
        c.pop("实测ACOS")
        with self.assertRaises(D.DecisionError) as cm:
            D.decide("ad_keyword_action", c, reg_dir=REG)
        self.assertIn("实测ACOS", str(cm.exception))

    def test_debug_off_hides_raw_answers(self):
        r = D.decide("ad_keyword_action", self.ctx(), debug=False, reg_dir=REG)
        self.assertNotIn("answers", r)

    def test_debug_on_includes_raw_answers(self):
        r = D.decide("ad_keyword_action", self.ctx(), debug=True, reg_dir=REG)
        self.assertIn("answers", r)

    def test_result_shape(self):
        r = D.decide("ad_keyword_action", self.ctx(), reg_dir=REG)
        for k in ("decision", "outcome", "confidence", "gate", "signals",
                  "model", "request_id", "elapsed_ms", "usage", "trimmed", "version"):
            self.assertIn(k, r, msg=k)
        self.assertIn(r["gate"], ("auto", "review"))

    def test_guard_escalates_real_registry(self):
        """browser_step：不可逆概率高时，即使 confidence 很高也必须转人工"""
        CANNED.update({
            "下一步": {"type": "choice", "choice": "proceed",
                       "probabilities": {"proceed": 0.99}, "confidence": 0.99},
            "是否不可逆": {"type": "noul", "noul": 0.95},
            "目标是否达成": {"type": "noul", "noul": 0.0},
        })
        r = D.decide("browser_step", self.browser_ctx(), reg_dir=REG)
        self.assertEqual(r["gate"], "review", msg="高危硬约束没生效")
        self.assertEqual(len(r.get("guard_hits", [])), 1)

    def test_threshold_per_outcome(self):
        """pause 的阈值（0.90）比 confirm（0.60）严：同样的 confidence 结果不同"""
        CANNED.update({
            "下一步": {"type": "choice", "choice": "pause",
                       "probabilities": {"pause": 0.62}, "confidence": 0.62},
            "是否不可逆": {"type": "noul", "noul": 0.10},
            "目标是否达成": {"type": "noul", "noul": 0.0},
        })
        r = D.decide("browser_step", self.browser_ctx(), reg_dir=REG)
        self.assertEqual(r["outcome"], "pause")
        self.assertEqual(r["gate"], "review", msg="pause 阈值 0.90，0.62 不该放行")

        CANNED["下一步"] = {"type": "choice", "choice": "confirm",
                            "probabilities": {"confirm": 0.62}, "confidence": 0.62}
        r2 = D.decide("browser_step", self.browser_ctx(), reg_dir=REG)
        self.assertEqual(r2["gate"], "auto", msg="confirm 阈值 0.60，0.62 应该放行")


class NoulHasNoConfidenceTest(unittest.TestCase):
    """守住那条容易被误传的差别"""

    def test_noul_answer_shape_in_readme_example(self):
        a = {"type": "noul", "noul": 0.72}
        self.assertNotIn("confidence", a)
        self.assertEqual(D.gate(a, 0.5), "auto")


if __name__ == "__main__":
    unittest.main(verbosity=2)
