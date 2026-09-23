"""HTTP adapter for a local llama.cpp OpenAI-compatible server."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # Allows a rule-only start before dependencies are installed.
    load_dotenv = None

from .persona import REM_PERSONA

LOGGER = logging.getLogger(__name__)

if load_dotenv is not None:
    load_dotenv()


class LLMServiceError(RuntimeError):
    """A safe, user-facing local model failure."""


class LLMNotConfiguredError(LLMServiceError):
    """Raised when no supported local model provider is configured."""


@dataclass(frozen=True)
class LLMResult:
    reply: str
    source: str


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    base_url: str
    model: str
    timeout_seconds: float
    temperature: float
    max_tokens: int
    fallback_to_rules: bool

    @classmethod
    def from_env(cls) -> "LLMSettings":
        provider = os.getenv("LLM_PROVIDER", "llama_cpp").strip().lower()
        if provider in {"llama.cpp", "llama-cpp", "llamacpp"}:
            provider = "llama_cpp"

        configured_base_url = os.getenv("LLM_BASE_URL", "").strip()
        if configured_base_url:
            base_url = configured_base_url
        else:
            base_url = _first_env("LLAMA_CPP_BASE_URL", default="http://127.0.0.1:8080")

        default_model = "RemLocal"
        model = _first_env("LLM_MODEL", "LLAMA_CPP_MODEL", default=default_model)
        timeout_raw = _first_env("LLM_TIMEOUT", "LLM_TIMEOUT_SECONDS", default="90")

        return cls(
            provider=provider,
            base_url=_normalize_base_url(base_url),
            model=model,
            timeout_seconds=_env_float_value(timeout_raw, 90.0, 1.0, 600.0),
            temperature=_env_float("LLM_TEMPERATURE", 0.7, 0.0, 2.0),
            max_tokens=_env_int("LLM_MAX_TOKENS", 512, 32, 4096),
            fallback_to_rules=_env_bool("LLM_FALLBACK_TO_RULES", True),
        )


def _first_env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized and not normalized.startswith(("http://", "https://")):
        normalized = f"http://{normalized}"
    return normalized


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    return _env_float_value(os.getenv(name), default, minimum, maximum, name)


def _env_float_value(
    raw_value: str | None,
    default: float,
    minimum: float,
    maximum: float,
    name: str = "LLM_TIMEOUT",
) -> float:
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        LOGGER.warning("Invalid %s value; using default", name)
        return default
    return min(max(value, minimum), maximum)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        LOGGER.warning("Invalid %s value; using default", name)
        return default
    return min(max(value, minimum), maximum)


class LocalLLMService:
    """Small synchronous HTTP adapter with an async wrapper for FastAPI."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or LLMSettings.from_env()

    @property
    def provider(self) -> str:
        return self.settings.provider

    @property
    def model(self) -> str:
        return self.settings.model

    @property
    def enabled(self) -> bool:
        return self.provider == "llama_cpp"

    @property
    def rule_mode(self) -> bool:
        return self.provider in {"rules", "demo", "demo_rule_engine"}

    @property
    def source(self) -> str:
        return "local_llama_cpp" if self.provider == "llama_cpp" else "local_llm"

    def public_config(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "enabled": self.enabled,
            "fallback_to_rules": self.settings.fallback_to_rules,
        }

    async def generate_async(self, message: str, user_name: str) -> LLMResult:
        return await asyncio.to_thread(self.generate, message, user_name)

    def generate(self, message: str, user_name: str) -> LLMResult:
        if not self.enabled:
            raise LLMNotConfiguredError("没有配置受支持的本地模型服务")

        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": f"{user_name}说：\n{message}"},
        ]
        if self.provider == "llama_cpp":
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
            }
            body = self._post_json(
                f"{self.settings.base_url}/v1/chat/completions",
                payload,
            )
            reply = self._extract_llama_cpp_reply(body)
        else:  # pragma: no cover - guarded by enabled, retained for clarity
            raise LLMNotConfiguredError(f"不支持的本地模型服务：{self.provider}")

        if not reply:
            raise LLMServiceError("本地模型返回了空回复")
        return LLMResult(reply=reply, source=self.source)

    def _system_prompt(self) -> str:
        principles = "；".join(REM_PERSONA.principles)
        return (
            f"你是{REM_PERSONA.name}，这是一个非官方同人学习项目中的角色人格演示。"
            f"你的语气应当{REM_PERSONA.tone}。"
            f"请遵守以下原则：{principles}"
            "请用自然、简洁的中文回答；不要声称自己是官方角色或真实的人。"
        )

    def _post_json(self, url: str, payload: dict[str, object]) -> Mapping[str, Any]:
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
            decoded = response.json()
        except requests.Timeout as exc:
            raise LLMServiceError("连接本地模型服务超时") from exc
        except requests.ConnectionError as exc:
            raise LLMServiceError("本地模型服务不可用") from exc
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "未知"
            raise LLMServiceError(f"本地模型服务返回 HTTP {status_code}") from exc
        except requests.RequestException as exc:
            raise LLMServiceError("请求本地模型服务失败") from exc
        except ValueError as exc:
            raise LLMServiceError("本地模型返回了无法解析的数据") from exc
        if not isinstance(decoded, Mapping):
            raise LLMServiceError("本地模型返回的数据格式不正确")
        return decoded

    @staticmethod
    def _extract_llama_cpp_reply(body: Mapping[str, Any]) -> str:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        choice = choices[0]
        if not isinstance(choice, Mapping):
            return ""
        message = choice.get("message")
        if not isinstance(message, Mapping):
            return ""
        content = message.get("content")
        return content.strip() if isinstance(content, str) else ""
