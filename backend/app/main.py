"""RemLocal 的本地模型聊天 API。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from .llm_service import LLMServiceError, LocalLLMService
from .planning import (
    PLANNING_POLICY_VERSION,
    is_three_day_study_plan_request,
    three_day_study_plan_reply,
)
from .persona import (
    PERSONA_INTRO_POLICY_VERSION,
    REM_PERSONA,
    demo_reply,
    is_persona_introduction_request,
    persona_introduction_reply,
)
from .safety import (
    SAFETY_POLICY_VERSION,
    is_self_harm_crisis,
    self_harm_crisis_reply,
)


LOGGER = logging.getLogger(__name__)
llm_service = LocalLLMService()


app = FastAPI(
    title="RemLocal API",
    version="0.2.0",
    description="本地角色人格智能体的本地模型聊天 API。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000, description="用户输入")
    user_name: str = Field(default="你", min_length=1, max_length=32)


class ChatResponse(BaseModel):
    reply: str
    source: str
    persona_name: str


class OpenAIChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=100_000)


class OpenAIChatCompletionRequest(BaseModel):
    model: str = Field(default="RemLocal", min_length=1, max_length=200)
    messages: list[OpenAIChatMessage] = Field(min_length=1, max_length=200)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=4096)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "stage": "local-llm",
        "persona_intro_policy_version": PERSONA_INTRO_POLICY_VERSION,
        "planning_policy_version": PLANNING_POLICY_VERSION,
        "safety_policy_version": SAFETY_POLICY_VERSION,
        **llm_service.public_config(),
    }


@app.get("/api/persona")
def persona() -> dict[str, object]:
    return {
        "version": REM_PERSONA.version,
        "name": REM_PERSONA.name,
        "identity_note": REM_PERSONA.identity_note,
        "role_background": REM_PERSONA.role_background,
        "tone": REM_PERSONA.tone,
        "speaking_style": REM_PERSONA.speaking_style,
        "behavior_rules": REM_PERSONA.behavior_rules,
        "principles": REM_PERSONA.principles,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="消息不能为空")

    user_name = payload.user_name.strip() or "你"
    return await _respond(message, user_name)


async def _respond(
    message: str,
    user_name: str,
    context_messages: list[dict[str, str]] | None = None,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatResponse:
    rule_response = _rule_response(message, user_name)
    if rule_response is not None:
        return rule_response

    try:
        if context_messages is None:
            result = await llm_service.generate_async(message, user_name)
        else:
            result = await llm_service.generate_messages_async(
                context_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
    except LLMServiceError as exc:
        LOGGER.warning("Local LLM request failed: %s", exc)
        if not llm_service.settings.fallback_to_rules:
            raise HTTPException(
                status_code=503,
                detail="本地模型暂时不可用，请检查模型服务是否已启动。",
            ) from exc
        return ChatResponse(
            reply=demo_reply(message, user_name),
            source="demo_rule_engine_fallback",
            persona_name=REM_PERSONA.name,
        )

    return ChatResponse(
        reply=result.reply,
        source=result.source,
        persona_name=REM_PERSONA.name,
    )


def _rule_response(message: str, user_name: str) -> ChatResponse | None:
    if is_self_harm_crisis(message):
        return ChatResponse(
            reply=self_harm_crisis_reply(),
            source="safety_rule_engine",
            persona_name=REM_PERSONA.name,
        )

    if is_persona_introduction_request(message):
        return ChatResponse(
            reply=persona_introduction_reply(),
            source="persona_rule_engine",
            persona_name=REM_PERSONA.name,
        )

    if is_three_day_study_plan_request(message):
        return ChatResponse(
            reply=three_day_study_plan_reply(),
            source="planning_rule_engine",
            persona_name=REM_PERSONA.name,
        )

    if llm_service.rule_mode:
        return ChatResponse(
            reply=demo_reply(message, user_name),
            source="demo_rule_engine",
            persona_name=REM_PERSONA.name,
        )

    return None


def _openai_completion_body(
    response: ChatResponse,
    *,
    request_id: str,
    created: int,
    model: str,
) -> dict[str, object]:
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response.reply},
                "finish_reason": "stop",
            }
        ],
        "rem_local": {
            "source": response.source,
            "persona_name": response.persona_name,
        },
    }


def _openai_stream(
    response: ChatResponse,
    *,
    request_id: str,
    created: int,
    model: str,
) -> Iterator[str]:
    return _openai_token_stream(
        iter((response.reply,)),
        request_id=request_id,
        created=created,
        model=model,
    )


def _openai_token_stream(
    content_chunks: Iterator[str],
    *,
    request_id: str,
    created: int,
    model: str,
) -> Iterator[str]:
    role_chunk = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
        ],
    }
    yield f"data: {json.dumps(role_chunk, ensure_ascii=False)}\n\n"
    for content in content_chunks:
        if not content:
            continue
        content_chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": content},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(content_chunk, ensure_ascii=False)}\n\n"
    finish_chunk = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/v1/models")
def openai_models() -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {
                "id": llm_service.model,
                "object": "model",
                "created": 0,
                "owned_by": "remlocal",
            }
        ],
    }


@app.post("/v1/chat/completions", response_model=None)
async def openai_chat_completions(
    payload: OpenAIChatCompletionRequest,
) -> dict[str, object] | StreamingResponse:
    messages = [message.model_dump() for message in payload.messages]
    last_user_message = next(
        (
            message["content"].strip()
            for message in reversed(messages)
            if message["role"] == "user" and message["content"].strip()
        ),
        "",
    )
    if not last_user_message:
        raise HTTPException(status_code=422, detail="messages 中必须包含用户消息")

    request_id = f"chatcmpl-remlocal-{uuid.uuid4().hex}"
    created = int(time.time())
    model = payload.model or llm_service.model
    if payload.stream:
        rule_response = _rule_response(last_user_message, "你")
        if rule_response is not None:
            content_stream = _openai_stream(
                rule_response,
                request_id=request_id,
                created=created,
                model=model,
            )
            source = rule_response.source
        else:
            try:
                model_tokens = await asyncio.to_thread(
                    llm_service.open_messages_stream,
                    messages,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                )
            except LLMServiceError as exc:
                LOGGER.warning("Local LLM stream failed: %s", exc)
                if not llm_service.settings.fallback_to_rules:
                    raise HTTPException(
                        status_code=503,
                        detail="本地模型暂时不可用，请检查模型服务是否已启动。",
                    ) from exc
                fallback = ChatResponse(
                    reply=demo_reply(last_user_message, "你"),
                    source="demo_rule_engine_fallback",
                    persona_name=REM_PERSONA.name,
                )
                content_stream = _openai_stream(
                    fallback,
                    request_id=request_id,
                    created=created,
                    model=model,
                )
                source = fallback.source
            else:
                content_stream = _openai_token_stream(
                    model_tokens,
                    request_id=request_id,
                    created=created,
                    model=model,
                )
                source = llm_service.source

        return StreamingResponse(
            content_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-RemLocal-Source": source,
            },
        )

    response = await _respond(
        last_user_message,
        "你",
        messages,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    return _openai_completion_body(
        response,
        request_id=request_id,
        created=created,
        model=model,
    )
