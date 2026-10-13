"""Deterministic crisis routing for messages that must not rely on model sampling."""

from __future__ import annotations

import re


SAFETY_POLICY_VERSION = "self-harm-crisis-v1"


_CHINESE_SELF_HARM_INTENT = (
    "我不想活",
    "我想死",
    "我要死",
    "我想自杀",
    "我要自杀",
    "我准备自杀",
    "我打算自杀",
    "我有自杀的念头",
    "我要伤害自己",
    "我想伤害自己",
    "我准备伤害自己",
    "我打算伤害自己",
    "准备伤害自己",
    "打算伤害自己",
    "我想结束生命",
    "我想结束自己的生命",
    "我准备结束生命",
    "我准备结束自己的生命",
    "我打算结束生命",
    "我打算结束自己的生命",
    "我活不下去",
    "我撑不下去",
)

_ENGLISH_SELF_HARM_INTENT = (
    "i want to die",
    "i want to kill myself",
    "i'm going to kill myself",
    "i am going to kill myself",
    "i plan to kill myself",
    "i want to hurt myself",
    "i'm going to hurt myself",
    "i am going to hurt myself",
)


def is_self_harm_crisis(message: str) -> bool:
    """Return true only for direct first-person intent, not general discussion."""
    compact_chinese = re.sub(r"[\s，。！？、,.!?；;：:]+", "", message)
    if any(phrase in compact_chinese for phrase in _CHINESE_SELF_HARM_INTENT):
        return True

    normalized_english = " ".join(message.casefold().split())
    return any(phrase in normalized_english for phrase in _ENGLISH_SELF_HARM_INTENT)


def self_harm_crisis_reply() -> str:
    """Return a stable response focused on immediate safety and real-world help."""
    return (
        "听到你说准备伤害自己，雷姆很担心你。请先告诉我：你现在安全吗？"
        "如果危险物品就在身边，请先放下并远离危险物品，走到有其他人的安全地点，不要独处。"
        "现在就联系一位可信任的人，例如家人、朋友或老师，请他来陪着你。"
        "如果你可能马上行动，请立即联系当地急救或报警服务，或者直接前往最近的急诊；"
        "如果你在中国大陆，可以拨打120或110。"
        "请先只回复“现在安全”或“不安全”，雷姆会陪你处理下一步。"
    )
