"""RemLocal 的本地模型聊天 API。"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .llm_service import LLMServiceError, LocalLLMService
from .persona import REM_PERSONA, demo_reply


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


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "stage": "local-llm", **llm_service.public_config()}


@app.get("/api/persona")
def persona() -> dict[str, object]:
    return {
        "name": REM_PERSONA.name,
        "identity_note": REM_PERSONA.identity_note,
        "tone": REM_PERSONA.tone,
        "principles": REM_PERSONA.principles,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="消息不能为空")

    user_name = payload.user_name.strip() or "你"
    if llm_service.rule_mode:
        return ChatResponse(
            reply=demo_reply(message, user_name),
            source="demo_rule_engine",
            persona_name=REM_PERSONA.name,
        )

    try:
        result = await llm_service.generate_async(message, user_name)
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
