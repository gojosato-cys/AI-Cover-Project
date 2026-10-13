from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from backend.app import main
from backend.app.safety import (
    SAFETY_POLICY_VERSION,
    is_self_harm_crisis,
    self_harm_crisis_reply,
)


class SelfHarmDetectionTests(unittest.TestCase):
    def test_detects_direct_chinese_intent(self) -> None:
        self.assertTrue(is_self_harm_crisis("我不想活了，今晚准备伤害自己。"))
        self.assertTrue(is_self_harm_crisis("我打算结束自己的生命"))

    def test_detects_direct_english_intent(self) -> None:
        self.assertTrue(is_self_harm_crisis("I want to kill myself"))

    def test_does_not_intercept_general_discussion(self) -> None:
        self.assertFalse(is_self_harm_crisis("我想知道如何帮助有自杀念头的朋友"))
        self.assertFalse(is_self_harm_crisis("这篇论文研究青少年自杀率"))

    def test_reply_contains_immediate_safety_steps(self) -> None:
        reply = self_harm_crisis_reply()

        self.assertIn("你现在安全吗", reply)
        self.assertIn("远离危险物品", reply)
        self.assertIn("不要独处", reply)
        self.assertIn("可信任的人", reply)
        self.assertIn("120或110", reply)


class SelfHarmApiRoutingTests(unittest.TestCase):
    def test_policy_has_stable_version(self) -> None:
        self.assertEqual(SAFETY_POLICY_VERSION, "self-harm-crisis-v1")

    def test_crisis_message_bypasses_model(self) -> None:
        with patch.object(
            main.llm_service,
            "generate_async",
            new=AsyncMock(side_effect=AssertionError("model must not be called")),
        ) as generate:
            response = asyncio.run(
                main.chat(main.ChatRequest(message="我不想活了，今晚准备伤害自己。"))
            )

        generate.assert_not_awaited()
        self.assertEqual(response.source, "safety_rule_engine")
        self.assertIn("你现在安全吗", response.reply)


if __name__ == "__main__":
    unittest.main()
