"""Deterministic responses for narrow planning tasks the model handles unreliably."""

from __future__ import annotations

import re


PLANNING_POLICY_VERSION = "three-day-study-plan-v1"

_THREE_DAY_PATTERN = re.compile(r"(?:3|三)\s*(?:天|日)")
_STUDY_TERMS = ("考试", "复习", "备考", "学习")
_REQUEST_TERMS = (
    "帮我安排",
    "帮我制定",
    "安排一个",
    "安排一下",
    "制定一个",
    "制定计划",
    "做个计划",
    "规划一下",
    "怎么复习",
    "如何复习",
)


def is_three_day_study_plan_request(message: str) -> bool:
    """Match direct requests for a three-day study plan, not general plan discussion."""
    normalized = re.sub(r"\s+", "", message)
    return (
        bool(_THREE_DAY_PATTERN.search(normalized))
        and any(term in normalized for term in _STUDY_TERMS)
        and any(term in normalized for term in _REQUEST_TERMS)
    )


def three_day_study_plan_reply() -> str:
    """Give an immediately useful default before asking for customization details."""
    return (
        "当然可以，雷姆先给你一份能立即执行的三天复习计划：\n"
        "第一天：列出考试范围，用一次快速自测找出薄弱知识点；"
        "把约一半时间用于理解和补缺，最后整理错题。\n"
        "第二天：集中练习高频题和薄弱项，每完成一组就核对并记录错误原因；"
        "晚上闭卷回忆重点。\n"
        "第三天：按考试时长做一次模拟，复盘错题和易忘内容；"
        "停止学习前留出时间整理用品并保证睡眠。\n"
        "请再告诉雷姆考试科目、范围和每天可用时间，"
        "雷姆会把每一段复习时间调整得更适合你。"
    )
