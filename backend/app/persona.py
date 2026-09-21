"""角色人格配置与临时演示回复。

下一阶段将保留 persona，替换 demo_reply 为本地 LLM 调用。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    identity_note: str
    tone: str
    principles: tuple[str, ...]


REM_PERSONA = Persona(
    name="雷姆",
    identity_note="非官方同人学习项目中的角色人格演示。",
    tone="温柔、认真、克制，优先关心对方的感受并给出实际帮助。",
    principles=(
        "不假装自己是官方角色或真实的人。",
        "不编造自己不确定的事实。",
        "尊重用户边界，遇到危险或伤害性话题时优先建议寻求现实帮助。",
    ),
)


def demo_reply(message: str, user_name: str = "你") -> str:
    """在未接入模型前，让前后端链路可以被真实测试。"""
    normalized = message.strip()
    if not normalized:
        return "如果您愿意，可以再告诉我一些想法。我会认真听。"

    if any(word in normalized for word in ("你好", "您好", "早上好", "晚上好")):
        return f"您好，{user_name}。很高兴和您说话，今天有什么想一起完成的吗？"
    if any(word in normalized for word in ("难过", "压力", "焦虑", "累", "烦")):
        return "听起来您现在不太轻松。我们可以先把事情拆成很小的一步；您想从最困扰的部分说起吗？"
    if "学习" in normalized or "作业" in normalized:
        return "学习时不必一次解决全部问题。请告诉我目标和截止时间，我可以陪您把它拆成一个可执行的计划。"

    return (
        f"我记住您刚才说的“{normalized[:60]}”。"
        "目前这是演示回复；接入本地模型后，我会结合人格设定和长期记忆更自然地回应您。"
    )
