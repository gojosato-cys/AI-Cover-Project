"""RemLocal 的第一个可运行 API：文字聊天演示。"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .persona import REM_PERSONA, demo_reply


app = FastAPI(
    title="RemLocal API",
    version="0.1.0",
    description="本地角色人格智能体的文字聊天 MVP。",
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
def health() -> dict[str, str]:
    return {"status": "ok", "stage": "demo-rule-engine"}


@app.get("/api/persona")
def persona() -> dict[str, object]:
    return {
        "name": REM_PERSONA.name,
        "identity_note": REM_PERSONA.identity_note,
        "tone": REM_PERSONA.tone,
        "principles": REM_PERSONA.principles,
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="消息不能为空")

    return ChatResponse(
        reply=demo_reply(message, payload.user_name.strip()),
        source="demo_rule_engine",
        persona_name=REM_PERSONA.name,
    )
