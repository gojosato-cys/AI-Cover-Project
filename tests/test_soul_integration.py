from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.app import main
from backend.app.llm_service import LLMResult, LLMSettings, LocalLLMService


class SoulOpenAICompatibilityTests(unittest.TestCase):
    def test_full_soul_history_is_forwarded_to_local_model(self) -> None:
        messages = [
            main.OpenAIChatMessage(role="system", content="Soul memory context"),
            main.OpenAIChatMessage(role="user", content="你还记得我上次说的事吗？"),
        ]
        with patch.object(
            main.llm_service,
            "generate_messages_async",
            new=AsyncMock(
                return_value=LLMResult(reply="记得。", source="local_llama_cpp")
            ),
        ) as generate:
            response = asyncio.run(
                main.openai_chat_completions(
                    main.OpenAIChatCompletionRequest(
                        model="RemLocal",
                        messages=messages,
                    )
                )
            )

        generate.assert_awaited_once_with(
            [message.model_dump() for message in messages],
            temperature=None,
            max_tokens=None,
        )
        self.assertEqual(
            response["choices"][0]["message"]["content"],
            "记得。",
        )
        self.assertEqual(response["rem_local"]["source"], "local_llama_cpp")

    def test_safety_route_bypasses_model_for_soul_client(self) -> None:
        with patch.object(
            main.llm_service,
            "generate_messages_async",
            new=AsyncMock(side_effect=AssertionError("model must not be called")),
        ) as generate:
            response = asyncio.run(
                main.openai_chat_completions(
                    main.OpenAIChatCompletionRequest(
                        messages=[
                            main.OpenAIChatMessage(
                                role="user",
                                content="我不想活了，今晚准备伤害自己。",
                            )
                        ]
                    )
                )
            )

        generate.assert_not_awaited()
        self.assertEqual(response["rem_local"]["source"], "safety_rule_engine")
        self.assertIn("你现在安全吗", response["choices"][0]["message"]["content"])

    def test_stream_uses_openai_compatible_sse_chunks(self) -> None:
        response = main.ChatResponse(
            reply="你好。",
            source="persona_rule_engine",
            persona_name="雷姆",
        )
        chunks = list(
            main._openai_stream(
                response,
                request_id="chatcmpl-test",
                created=1,
                model="RemLocal",
            )
        )

        self.assertEqual(chunks[-1], "data: [DONE]\n\n")
        content_chunk = json.loads(chunks[1].removeprefix("data: "))
        self.assertEqual(content_chunk["choices"][0]["delta"]["content"], "你好。")

    def test_model_stream_forwards_each_llama_delta_separately(self) -> None:
        async def collect_body() -> list[str]:
            body: list[str] = []
            async for chunk in response.body_iterator:
                body.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
            return body

        with patch.object(
            main.llm_service,
            "open_messages_stream",
            return_value=iter(("雷", "姆", "。")),
        ) as open_stream:
            response = asyncio.run(
                main.openai_chat_completions(
                    main.OpenAIChatCompletionRequest(
                        messages=[
                            main.OpenAIChatMessage(role="user", content="继续聊吧")
                        ],
                        stream=True,
                    )
                )
            )

        chunks = asyncio.run(collect_body())
        deltas = [
            json.loads(chunk.removeprefix("data: "))["choices"][0]["delta"]
            for chunk in chunks[:-1]
        ]
        open_stream.assert_called_once()
        self.assertEqual(
            [delta["content"] for delta in deltas if "content" in delta],
            ["雷", "姆", "。"],
        )
        self.assertEqual(chunks[-1], "data: [DONE]\n\n")

    def test_models_endpoint_exposes_configured_model(self) -> None:
        body = main.openai_models()

        self.assertEqual(body["object"], "list")
        self.assertEqual(body["data"][0]["id"], main.llm_service.model)


class SoulHistoryAdapterTests(unittest.TestCase):
    def test_remlocal_policy_precedes_soul_context_and_history_is_preserved(self) -> None:
        service = LocalLLMService(
            LLMSettings(
                provider="llama_cpp",
                base_url="http://127.0.0.1:8080",
                model="RemLocal",
                timeout_seconds=10,
                temperature=0,
                max_tokens=512,
                fallback_to_rules=False,
            )
        )
        captured: dict[str, object] = {}

        def fake_post(url: str, payload: dict[str, object]) -> dict[str, object]:
            captured.update(payload)
            return {"choices": [{"message": {"content": "好的。"}}]}

        with patch.object(service, "_post_json", side_effect=fake_post):
            service.generate_messages(
                [
                    {"role": "system", "content": "Soul character and memory"},
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "您好"},
                    {"role": "user", "content": "继续聊吧"},
                ]
            )

        sent_messages = captured["messages"]
        self.assertIn("遇到危险", sent_messages[0]["content"])
        self.assertIn("Soul character and memory", sent_messages[0]["content"])
        self.assertEqual(sent_messages[-1], {"role": "user", "content": "继续聊吧"})
        self.assertEqual(sent_messages[-2], {"role": "assistant", "content": "您好"})

    def test_llama_sse_is_parsed_into_text_deltas(self) -> None:
        service = LocalLLMService(
            LLMSettings(
                provider="llama_cpp",
                base_url="http://127.0.0.1:8080",
                model="RemLocal",
                timeout_seconds=10,
                temperature=0,
                max_tokens=512,
                fallback_to_rules=False,
            )
        )
        response = Mock()
        response.raise_for_status.return_value = None
        response.iter_lines.return_value = iter(
            (
                b'data: {"choices":[{"delta":{"role":"assistant"}}]}',
                'data: {"choices":[{"delta":{"content":"雷"}}]}'.encode(),
                'data: {"choices":[{"delta":{"content":"姆"}}]}'.encode(),
                b"data: [DONE]",
            )
        )

        with patch("backend.app.llm_service.requests.post", return_value=response) as post:
            tokens = list(
                service.open_messages_stream(
                    [{"role": "user", "content": "你好"}],
                    temperature=0,
                    max_tokens=32,
                )
            )

        self.assertEqual(tokens, ["雷", "姆"])
        self.assertTrue(post.call_args.kwargs["stream"])
        self.assertTrue(post.call_args.kwargs["json"]["stream"])
        response.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
