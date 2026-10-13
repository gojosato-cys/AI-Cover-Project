from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_training_data import (
    DatasetValidationError,
    validate_training_data,
)


class TrainingDataValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.sources = self.root / "sources.jsonl"
        self.eval_cases = self.root / "eval.jsonl"
        self._write_jsonl(
            self.sources,
            [
                {
                    "schema_version": "rem-source-v1",
                    "source_id": "rem-original-v1",
                    "name": "原创样本",
                    "source_type": "human_authored",
                    "location": "raw/rem-original-v1",
                    "usage_scope": "local",
                    "status": "approved",
                    "notes": "",
                }
            ],
        )
        self._write_jsonl(self.eval_cases, [{"message": "固定评测问题"}])

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _record(
        record_id: str,
        group_id: str,
        split: str,
        user_message: str,
        source_id: str = "rem-original-v1",
    ) -> dict[str, object]:
        return {
            "schema_version": "rem-sft-v1",
            "id": record_id,
            "source_id": source_id,
            "group_id": group_id,
            "split": split,
            "category": "persona",
            "language": "zh-CN",
            "messages": [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": f"雷姆回应：{record_id}"},
            ],
            "quality": {
                "status": "approved",
                "reviewer": "owner",
                "notes": "",
            },
        }

    def _write_splits(
        self,
        train: list[dict[str, object]],
        validation: list[dict[str, object]],
        test: list[dict[str, object]],
    ) -> list[Path]:
        paths = [self.root / "train.jsonl", self.root / "validation.jsonl", self.root / "test.jsonl"]
        for path, rows in zip(paths, (train, validation, test), strict=True):
            self._write_jsonl(path, rows)
        return paths

    def _valid_paths(self) -> list[Path]:
        return self._write_splits(
            [self._record("rem-train-001", "scene-train-001", "train", "训练问题")],
            [
                self._record(
                    "rem-validation-001",
                    "scene-validation-001",
                    "validation",
                    "验证问题",
                )
            ],
            [self._record("rem-test-001", "scene-test-001", "test", "测试问题")],
        )

    def test_accepts_valid_isolated_dataset(self) -> None:
        summary = validate_training_data(
            self._valid_paths(),
            self.sources,
            self.eval_cases,
        )

        self.assertEqual(summary["record_count"], 3)
        self.assertEqual(summary["unique_groups"], 3)
        self.assertEqual(summary["split_counts"]["train"], 1)

    def test_rejects_group_leakage_between_splits(self) -> None:
        paths = self._write_splits(
            [self._record("rem-train-001", "shared-scene", "train", "训练问题")],
            [
                self._record(
                    "rem-validation-001",
                    "shared-scene",
                    "validation",
                    "不同改写",
                )
            ],
            [self._record("rem-test-001", "test-scene", "test", "测试问题")],
        )

        with self.assertRaisesRegex(DatasetValidationError, "禁止跨集合泄漏"):
            validate_training_data(paths, self.sources, self.eval_cases)

    def test_rejects_normalized_duplicate_conversations(self) -> None:
        duplicate = self._record("rem-validation-001", "validation-scene", "validation", "训练 问题")
        duplicate["messages"][1]["content"] = "雷姆回应：rem-train-001"
        paths = self._write_splits(
            [self._record("rem-train-001", "train-scene", "train", "训练问题")],
            [duplicate],
            [self._record("rem-test-001", "test-scene", "test", "测试问题")],
        )

        with self.assertRaisesRegex(DatasetValidationError, "规范化重复对话"):
            validate_training_data(paths, self.sources, self.eval_cases)

    def test_rejects_fixed_evaluation_prompt(self) -> None:
        paths = self._write_splits(
            [self._record("rem-train-001", "train-scene", "train", "固定评测问题")],
            [
                self._record(
                    "rem-validation-001",
                    "validation-scene",
                    "validation",
                    "验证问题",
                )
            ],
            [self._record("rem-test-001", "test-scene", "test", "测试问题")],
        )

        with self.assertRaisesRegex(DatasetValidationError, "与固定评测题直接重复"):
            validate_training_data(paths, self.sources, self.eval_cases)

    def test_rejects_invalid_role_order(self) -> None:
        paths = self._valid_paths()
        train_rows = [self._record("rem-train-001", "train-scene", "train", "训练问题")]
        train_rows[0]["messages"] = [
            {"role": "assistant", "content": "顺序错误"},
            {"role": "user", "content": "训练问题"},
        ]
        self._write_jsonl(paths[0], train_rows)

        with self.assertRaisesRegex(DatasetValidationError, "严格交替"):
            validate_training_data(paths, self.sources, self.eval_cases)

    def test_rejects_unknown_source(self) -> None:
        paths = self._valid_paths()
        train_rows = [
            self._record(
                "rem-train-001",
                "train-scene",
                "train",
                "训练问题",
                source_id="missing-source",
            )
        ]
        self._write_jsonl(paths[0], train_rows)

        with self.assertRaisesRegex(DatasetValidationError, "引用了未登记来源"):
            validate_training_data(paths, self.sources, self.eval_cases)


if __name__ == "__main__":
    unittest.main()
