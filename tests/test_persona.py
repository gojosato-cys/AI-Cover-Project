from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from backend.app import main
from backend.app.llm_service import LLMSettings, LocalLLMService
from backend.app.persona import (
    PERSONA_INTRO_POLICY_VERSION,
    REM_PERSONA,
    demo_reply,
    is_persona_introduction_request,
    persona_introduction_reply,
)


class PersonaPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        settings = LLMSettings(
            provider="llama_cpp",
            base_url="http://127.0.0.1:8080",
            model="RemLocal",
            timeout_seconds=10,
            temperature=0,
            max_tokens=512,
            fallback_to_rules=False,
        )
        self.service = LocalLLMService(settings)

    def test_prompt_contains_role_identity_and_relationships(self) -> None:
        prompt = self.service._system_prompt()

        self.assertIn("罗兹瓦尔宅邸", prompt)
        self.assertIn("姐姐拉姆", prompt)
        self.assertIn("细心温柔", prompt)

    def test_prompt_keeps_disclosure_out_of_normal_conversation(self) -> None:
        prompt = self.service._system_prompt()

        self.assertIn("正常对话不要主动插入免责声明", prompt)
        self.assertIn("不要声称获得官方授权", prompt)

    def test_prompt_requires_useful_default_before_clarification(self) -> None:
        prompt = self.service._system_prompt()

        self.assertIn("先给一个可立即使用的默认方案", prompt)
        self.assertIn("不能只提问而不给方案", prompt)

    def test_prompt_does_not_inject_example_content(self) -> None:
        prompt = self.service._system_prompt()

        self.assertNotIn("用户：", prompt)
        self.assertNotIn("第一天梳理范围", prompt)

    def test_rule_greeting_is_in_character(self) -> None:
        reply = demo_reply("你好，雷姆")

        self.assertIn(REM_PERSONA.name, reply)
        self.assertIn("女仆", reply)
        self.assertEqual(reply.count("。"), 2)


class PersonaIntroductionTests(unittest.TestCase):
    def test_detects_direct_identity_requests(self) -> None:
        self.assertTrue(
            is_persona_introduction_request(
                "你好，雷姆。请用两句话介绍自己，并保持温和语气。"
            )
        )
        self.assertTrue(is_persona_introduction_request("介绍一下你自己"))
        self.assertTrue(is_persona_introduction_request("你是谁？"))

    def test_does_not_intercept_user_intro_writing_requests(self) -> None:
        self.assertFalse(is_persona_introduction_request("帮我写一段自我介绍"))
        self.assertFalse(is_persona_introduction_request("我该如何介绍自己？"))

    def test_reply_is_exactly_two_sentences_and_in_character(self) -> None:
        reply = persona_introduction_reply()

        self.assertEqual(reply.count("。"), 2)
        self.assertIn("雷姆", reply)
        self.assertIn("女仆", reply)
        self.assertIn("帮助", reply)
        self.assertNotIn("官方授权", reply)


class PersonaIntroductionApiRoutingTests(unittest.TestCase):
    def test_policy_has_stable_version(self) -> None:
        self.assertEqual(
            PERSONA_INTRO_POLICY_VERSION,
            "persona-introduction-v1",
        )

    def test_matching_request_bypasses_model(self) -> None:
        with patch.object(
            main.llm_service,
            "generate_async",
            new=AsyncMock(side_effect=AssertionError("model must not be called")),
        ) as generate:
            response = asyncio.run(
                main.chat(
                    main.ChatRequest(
                        message="你好，雷姆。请用两句话介绍自己。"
                    )
                )
            )

        generate.assert_not_awaited()
        self.assertEqual(response.source, "persona_rule_engine")
        self.assertEqual(response.reply, persona_introduction_reply())

    def test_health_exposes_policy_version(self) -> None:
        self.assertEqual(
            main.health()["persona_intro_policy_version"],
            PERSONA_INTRO_POLICY_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
