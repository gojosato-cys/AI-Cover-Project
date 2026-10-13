"""Validate RemLocal SFT JSONL files before a training run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "training" / "splits"
DEFAULT_SOURCES = PROJECT_ROOT / "data" / "training" / "manifests" / "sources.jsonl"
DEFAULT_EVAL_CASES = PROJECT_ROOT / "tests" / "eval_cases" / "rem_v2.jsonl"

SCHEMA_VERSION = "rem-sft-v1"
SOURCE_SCHEMA_VERSION = "rem-source-v1"
VALID_SPLITS = ("train", "validation", "test")
VALID_CATEGORIES = {
    "persona",
    "casual",
    "emotion",
    "help",
    "planning",
    "boundary",
    "truthfulness",
    "safety",
    "security",
    "format",
}
VALID_SOURCE_TYPES = {
    "human_authored",
    "user_provided",
    "model_assisted",
    "public_dataset",
}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")

RECORD_FIELDS = {
    "schema_version",
    "id",
    "source_id",
    "group_id",
    "split",
    "category",
    "language",
    "messages",
    "quality",
}
SOURCE_FIELDS = {
    "schema_version",
    "source_id",
    "name",
    "source_type",
    "location",
    "usage_scope",
    "status",
    "notes",
}


class DatasetValidationError(ValueError):
    """Raised when one or more dataset readiness checks fail."""


def _read_jsonl(path: Path, errors: list[str]) -> list[tuple[int, dict[str, Any]]]:
    if not path.is_file():
        errors.append(f"缺少文件：{path}")
        return []

    rows: list[tuple[int, dict[str, Any]]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{line_number} 不是有效 JSON：{exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.name}:{line_number} 必须是 JSON 对象")
            continue
        rows.append((line_number, value))
    return rows


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", "", normalized)


def _conversation_fingerprint(messages: list[dict[str, str]]) -> str:
    normalized_messages = [
        {"role": item["role"], "content": _normalize_text(item["content"])}
        for item in messages
    ]
    payload = json.dumps(
        normalized_messages,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_sources(path: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for line_number, source in _read_jsonl(path, errors):
        location = f"{path.name}:{line_number}"
        missing = SOURCE_FIELDS - source.keys()
        extra = source.keys() - SOURCE_FIELDS
        if missing:
            errors.append(f"{location} 缺少字段：{sorted(missing)}")
        if extra:
            errors.append(f"{location} 包含未知字段：{sorted(extra)}")

        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not ID_PATTERN.fullmatch(source_id):
            errors.append(f"{location} 的 source_id 格式无效")
            continue
        if source_id in sources:
            errors.append(f"{location} 的 source_id 与前面重复：{source_id}")
            continue
        if source.get("schema_version") != SOURCE_SCHEMA_VERSION:
            errors.append(f"{location} 的 schema_version 必须是 {SOURCE_SCHEMA_VERSION}")
        if source.get("source_type") not in VALID_SOURCE_TYPES:
            errors.append(f"{location} 的 source_type 无效")
        if source.get("status") not in {"draft", "approved", "blocked"}:
            errors.append(f"{location} 的 status 无效")
        for field in ("name", "location", "usage_scope", "notes"):
            if not isinstance(source.get(field), str):
                errors.append(f"{location} 的 {field} 必须是字符串")
        sources[source_id] = source
    if not sources:
        errors.append("来源清单中没有可识别的记录")
    return sources


def _load_eval_messages(path: Path, errors: list[str]) -> set[str]:
    messages: set[str] = set()
    for line_number, case in _read_jsonl(path, errors):
        message = case.get("message")
        if not isinstance(message, str) or not message.strip():
            errors.append(f"{path.name}:{line_number} 缺少有效 message")
            continue
        messages.add(_normalize_text(message))
    return messages


def _validate_messages(
    value: object,
    location: str,
    errors: list[str],
) -> list[dict[str, str]] | None:
    if not isinstance(value, list) or len(value) < 2:
        errors.append(f"{location} 的 messages 至少需要一组 user/assistant 消息")
        return None

    messages: list[dict[str, str]] = []
    for index, item in enumerate(value, 1):
        item_location = f"{location} messages[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_location} 必须是对象")
            return None
        if set(item) != {"role", "content"}:
            errors.append(f"{item_location} 只能包含 role 和 content")
            return None
        role = item.get("role")
        content = item.get("content")
        if role not in {"system", "user", "assistant"}:
            errors.append(f"{item_location} 的 role 无效")
            return None
        if not isinstance(content, str) or not content.strip() or len(content) > 8000:
            errors.append(f"{item_location} 的 content 必须是 1..8000 字符的非空文本")
            return None
        messages.append({"role": role, "content": content.strip()})

    roles = [item["role"] for item in messages]
    conversation_roles = roles[1:] if roles[0] == "system" else roles
    if "system" in conversation_roles:
        errors.append(f"{location} 的 system 消息只能出现在第一条")
        return None
    expected = ["user" if index % 2 == 0 else "assistant" for index in range(len(conversation_roles))]
    if conversation_roles != expected or conversation_roles[-1] != "assistant":
        errors.append(f"{location} 必须从 user 开始、严格交替并以 assistant 结束")
        return None
    return messages


def validate_training_data(
    data_paths: list[Path],
    sources_path: Path = DEFAULT_SOURCES,
    eval_cases_path: Path = DEFAULT_EVAL_CASES,
) -> dict[str, object]:
    """Validate format, provenance, deduplication and split isolation."""
    errors: list[str] = []
    sources = _load_sources(sources_path, errors)
    eval_messages = _load_eval_messages(eval_cases_path, errors)

    supplied_splits = {path.stem for path in data_paths if path.stem in VALID_SPLITS}
    missing_splits = set(VALID_SPLITS) - supplied_splits
    if missing_splits:
        errors.append(f"缺少数据集合文件：{sorted(missing_splits)}")

    seen_ids: dict[str, str] = {}
    group_splits: dict[str, tuple[str, str]] = {}
    fingerprints: dict[str, str] = {}
    split_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    sources_used: set[str] = set()
    record_count = 0

    for path in data_paths:
        for line_number, record in _read_jsonl(path, errors):
            record_count += 1
            location = f"{path.name}:{line_number}"
            missing = RECORD_FIELDS - record.keys()
            extra = record.keys() - RECORD_FIELDS
            if missing:
                errors.append(f"{location} 缺少字段：{sorted(missing)}")
            if extra:
                errors.append(f"{location} 包含未知字段：{sorted(extra)}")

            if record.get("schema_version") != SCHEMA_VERSION:
                errors.append(f"{location} 的 schema_version 必须是 {SCHEMA_VERSION}")

            record_id = record.get("id")
            if not isinstance(record_id, str) or not ID_PATTERN.fullmatch(record_id):
                errors.append(f"{location} 的 id 格式无效")
            elif record_id in seen_ids:
                errors.append(f"{location} 的 id 与 {seen_ids[record_id]} 重复")
            else:
                seen_ids[record_id] = location

            source_id = record.get("source_id")
            if not isinstance(source_id, str) or not ID_PATTERN.fullmatch(source_id):
                errors.append(f"{location} 的 source_id 格式无效")
            elif source_id not in sources:
                errors.append(f"{location} 引用了未登记来源：{source_id}")
            elif sources[source_id].get("status") != "approved":
                errors.append(f"{location} 引用的来源尚未 approved：{source_id}")
            else:
                sources_used.add(source_id)

            split = record.get("split")
            if split not in VALID_SPLITS:
                errors.append(f"{location} 的 split 无效")
            else:
                split_counts[split] += 1
                if path.stem in VALID_SPLITS and split != path.stem:
                    errors.append(f"{location} 的 split 与文件名 {path.name} 不一致")

            group_id = record.get("group_id")
            if not isinstance(group_id, str) or not ID_PATTERN.fullmatch(group_id):
                errors.append(f"{location} 的 group_id 格式无效")
            elif split in VALID_SPLITS:
                previous = group_splits.get(group_id)
                if previous and previous[0] != split:
                    errors.append(
                        f"{location} 的 group_id {group_id} 已出现在 "
                        f"{previous[0]}（{previous[1]}），禁止跨集合泄漏"
                    )
                else:
                    group_splits[group_id] = (split, location)

            category = record.get("category")
            if category not in VALID_CATEGORIES:
                errors.append(f"{location} 的 category 无效")
            else:
                category_counts[category] += 1
            if record.get("language") != "zh-CN":
                errors.append(f"{location} 的 language 必须是 zh-CN")

            quality = record.get("quality")
            if not isinstance(quality, dict) or set(quality) != {
                "status",
                "reviewer",
                "notes",
            }:
                errors.append(f"{location} 的 quality 字段结构无效")
            else:
                if quality.get("status") != "approved":
                    errors.append(f"{location} 尚未通过人工复核")
                if not isinstance(quality.get("reviewer"), str) or not quality["reviewer"].strip():
                    errors.append(f"{location} 缺少 quality.reviewer")
                if not isinstance(quality.get("notes"), str):
                    errors.append(f"{location} 的 quality.notes 必须是字符串")

            messages = _validate_messages(record.get("messages"), location, errors)
            if messages is None:
                continue
            fingerprint = _conversation_fingerprint(messages)
            if fingerprint in fingerprints:
                errors.append(f"{location} 与 {fingerprints[fingerprint]} 是规范化重复对话")
            else:
                fingerprints[fingerprint] = location
            for message in messages:
                if (
                    message["role"] == "user"
                    and _normalize_text(message["content"]) in eval_messages
                ):
                    errors.append(f"{location} 与固定评测题直接重复，禁止进入微调数据")

    if record_count == 0:
        errors.append("训练数据不能为空")
    for split in VALID_SPLITS:
        if split_counts[split] == 0:
            errors.append(f"{split}.jsonl 没有有效记录")

    if errors:
        raise DatasetValidationError("训练数据校验失败：\n- " + "\n- ".join(errors))

    return {
        "schema_version": SCHEMA_VERSION,
        "record_count": record_count,
        "split_counts": dict(sorted(split_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "sources_used": sorted(sources_used),
        "unique_groups": len(group_splits),
        "unique_conversations": len(fingerprints),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--eval-cases", type=Path, default=DEFAULT_EVAL_CASES)
    args = parser.parse_args()

    data_paths = [args.data_dir / f"{split}.jsonl" for split in VALID_SPLITS]
    try:
        summary = validate_training_data(data_paths, args.sources, args.eval_cases)
    except DatasetValidationError as exc:
        print(exc, file=sys.stderr)
        return 1

    print("训练数据校验通过：")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
