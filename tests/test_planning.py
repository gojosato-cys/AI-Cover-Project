from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from backend.app import main
from backend.app.planning import (
    PLANNING_POLICY_VERSION,
    is_three_day_study_plan_request,
    three_day_study_plan_reply,
)


class StudyPlanDetectionTests(unittest.TestCase):
    def test_detects_direct_three_day_study_plan_request(self) -> None:
        self.assertTrue(
            is_three_day_study_plan_request(
                "我还有三天要准备考试，可以帮我安排一个复习计划吗？"
            )
        )
        self.assertTrue(is_three_day_study_plan_request("帮我制定3天备考计划"))

    def test_does_not_intercept_other_plans_or_plan_review(self) -> None:
        self.assertFalse(is_three_day_study_plan_request("帮我制定三天旅行计划"))
        self.assertFalse(is_three_day_study_plan_request("请评价我的三天复习计划"))
        self.assertFalse(is_three_day_study_plan_request("帮我制定一周复习计划"))

    def test_reply_gives_plan_before_requesting_details(self) -> None:
        reply = three_day_study_plan_reply()

        first_day = reply.index("第一天")
        question = reply.index("请再告诉雷姆")
        self.assertLess(first_day, question)
        self.assertIn("第二天", reply)
        self.assertIn("第三天", reply)
        self.assertIn("考试科目", reply)
        self.assertIn("每天可用时间", reply)


class StudyPlanApiRoutingTests(unittest.TestCase):
    def test_policy_has_stable_version(self) -> None:
        self.assertEqual(PLANNING_POLICY_VERSION, "three-day-study-plan-v1")

    def test_matching_request_bypasses_model(self) -> None:
        with patch.object(
            main.llm_service,
            "generate_async",
            new=AsyncMock(side_effect=AssertionError("model must not be called")),
        ) as generate:
            response = asyncio.run(
                main.chat(
                    main.ChatRequest(
                        message="我还有三天要准备考试，可以帮我安排一个复习计划吗？"
                    )
                )
            )

        generate.assert_not_awaited()
        self.assertEqual(response.source, "planning_rule_engine")
        self.assertIn("第一天", response.reply)


if __name__ == "__main__":
    unittest.main()
