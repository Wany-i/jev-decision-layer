"""Offline contract tests for one-off candidate decisions."""

import unittest

import decision as D
import mcp_server as M


class CandidateChoiceTest(unittest.TestCase):
    def setUp(self):
        self.original_backend = D._call_backend
        self.answer = {
            "type": "choice",
            "choice": "open_profile",
            "probabilities": {"open_profile": 0.9, "help": 0.07, "other": 0.03},
            "confidence": 0.9,
        }
        self.request = None
        D._call_backend = self.fake_backend

    def tearDown(self):
        D._call_backend = self.original_backend

    def fake_backend(self, state, questions, *, model, timeout=120, retries=2):
        self.request = (state, questions, model)
        return {
            "id": "request-1",
            "model": model,
            "answers": {"action": self.answer},
            "usage": {"input_tokens": 10},
        }

    @staticmethod
    def candidates(risk="read_only"):
        return [
            {"id": "open_profile", "label": "Open the profile menu", "risk": risk},
            {"id": "help", "label": "Open help", "risk": "read_only"},
        ]

    def choose(self, **kwargs):
        return D.choose_candidate(
            "View remaining usage", {"window": "Codex"}, self.candidates(), **kwargs
        )

    def test_selects_candidate_and_returns_gate(self):
        result = self.choose()
        self.assertEqual(result["outcome"], "open_profile")
        self.assertEqual(result["gate"], "auto")
        self.assertEqual(result["risk"], "read_only")
        self.assertNotIn("answers", result)
        state, questions, _ = self.request
        self.assertEqual(state, {"window": "Codex"})
        self.assertEqual(
            set(questions["action"]["criteria"]), {"open_profile", "help", "other"}
        )

    def test_low_confidence_requires_review(self):
        self.answer["confidence"] = 0.6
        self.assertEqual(self.choose()["gate"], "review")

    def test_irreversible_candidate_requires_review(self):
        result = D.choose_candidate(
            "View remaining usage", {}, self.candidates("irreversible")
        )
        self.assertEqual(result["gate"], "review")

    def test_other_requires_review(self):
        self.answer.update(
            choice="other",
            probabilities={"open_profile": 0.03, "help": 0.07, "other": 0.9},
        )
        result = self.choose()
        self.assertEqual(result["outcome"], "other")
        self.assertEqual(result["gate"], "review")

    def test_debug_includes_raw_answer(self):
        self.assertEqual(self.choose(debug=True)["answers"]["action"], self.answer)

    def test_rejects_unknown_model_choice(self):
        self.answer["choice"] = "delete_everything"
        with self.assertRaises(D.DecisionError):
            self.choose()

    def test_rejects_invalid_probability_distribution(self):
        self.answer["probabilities"]["open_profile"] = 0.5
        with self.assertRaises(D.DecisionError):
            self.choose()

    def test_rejects_duplicate_ids_and_reserved_other(self):
        with self.assertRaises(D.DecisionError):
            D.choose_candidate("goal", {}, self.candidates() * 2)
        with self.assertRaises(D.DecisionError):
            D.choose_candidate("goal", {}, [{"id": "other", "label": "x", "risk": "read_only"}])

    def test_rejects_missing_risk_and_oversize_state(self):
        with self.assertRaises(D.DecisionError):
            D.choose_candidate("goal", {}, [{"id": "x", "label": "x"}])
        with self.assertRaises(D.DecisionError):
            D.choose_candidate("goal", {"text": "x" * 40000}, self.candidates())

    def test_rejects_malformed_provider_and_candidate_types(self):
        self.answer["choice"] = ["open_profile"]
        with self.assertRaises(D.DecisionError):
            self.choose()
        self.answer["choice"] = "open_profile"
        with self.assertRaises(D.DecisionError):
            D.choose_candidate("goal", {}, self.candidates(["read_only"]))

    def test_mcp_exposes_choice_and_propagates_gate(self):
        tool = next(item for item in M._tools() if item["name"] == "choose_candidate")
        self.assertEqual(tool["inputSchema"]["required"], ["goal", "state", "candidates"])
        result = M.call_tool("choose_candidate", {
            "goal": "View remaining usage",
            "state": {"window": "Codex"},
            "candidates": self.candidates(),
        })
        self.assertFalse(result.get("isError", False))
        self.assertIn("gate=auto", result["content"][0]["text"])
        rejected = M.call_tool("choose_candidate", {
            "goal": "View remaining usage", "state": {}, "candidates": []
        })
        self.assertTrue(rejected["isError"])


if __name__ == "__main__":
    unittest.main()
