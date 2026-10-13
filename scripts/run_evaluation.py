"""Run the fixed RemLocal evaluation set against a running API."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "tests" / "eval_cases" / "rem_v2.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "eval-results"
SUPPORTED_CHECK_TYPES = {
    "contains_any",
    "contains_all",
    "excludes_all",
    "regex",
    "sentence_count",
    "list_item_count",
}


def _validate_check(check: dict[str, Any], line_number: int) -> None:
    check_type = check.get("type")
    if check_type not in SUPPORTED_CHECK_TYPES:
        raise ValueError(f"评测集第 {line_number} 行包含不支持的检查规则")
    if not isinstance(check.get("description"), str) or not check["description"]:
        raise ValueError(f"评测集第 {line_number} 行的检查规则缺少 description")
    if check_type in {"contains_any", "contains_all", "excludes_all"}:
        values = check.get("values")
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) and value for value in values
        ):
            raise ValueError(f"评测集第 {line_number} 行的 {check_type} 缺少有效 values")
    elif check_type == "regex":
        pattern = check.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"评测集第 {line_number} 行的 regex 缺少 pattern")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"评测集第 {line_number} 行的正则表达式无效: {exc}") from exc
    else:
        minimum = check.get("min", 0)
        maximum = check.get("max")
        if (
            not isinstance(minimum, int)
            or isinstance(minimum, bool)
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or minimum < 0
            or maximum < minimum
        ):
            raise ValueError(f"评测集第 {line_number} 行的计数范围无效")


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            case = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"评测集第 {line_number} 行不是有效 JSON: {exc}") from exc
        if not isinstance(case, dict) or not case.get("id") or not case.get("message"):
            raise ValueError(f"评测集第 {line_number} 行缺少 id 或 message")
        case_id = case["id"]
        if not isinstance(case_id, str) or case_id in seen_ids:
            raise ValueError(f"评测集第 {line_number} 行的 id 无效或重复")
        checks = case.get("checks")
        if not isinstance(checks, list) or not checks:
            raise ValueError(f"评测集第 {line_number} 行缺少 checks")
        for check in checks:
            if not isinstance(check, dict):
                raise ValueError(f"评测集第 {line_number} 行包含不支持的检查规则")
            _validate_check(check, line_number)
        seen_ids.add(case_id)
        cases.append(case)
    if not cases:
        raise ValueError("评测集不能为空")
    return cases


def _count_sentences(reply: str) -> int:
    return len([part for part in re.split(r"[。！？!?]+", reply) if part.strip()])


def _count_list_items(reply: str) -> int:
    pattern = re.compile(
        r"^\s*(?:[-*+]\s+|\d+\s*[.、)]\s*|第[一二三四五六七八九十]+步\s*[:：])\S+",
        re.MULTILINE,
    )
    explicit_items = len(pattern.findall(reply))
    inline_marker_sets = (
        ("首先", "其次"),
        ("第一步", "第二步"),
        ("第一点", "第二点"),
    )
    inline_items = max(
        (sum(marker in reply for marker in markers) for markers in inline_marker_sets),
        default=0,
    )
    return max(explicit_items, inline_items)


def evaluate_reply(
    reply: str,
    checks: list[dict[str, Any]],
    user_message: str = "",
) -> dict[str, Any]:
    """Apply transparent lexical/structural checks; manual rubrics remain separate."""
    evaluated_text = reply
    if user_message:
        evaluated_text = evaluated_text.replace(user_message, "")
        if len(user_message) > 60:
            evaluated_text = evaluated_text.replace(user_message[:60], "")

    outcomes: list[dict[str, object]] = []
    for check in checks:
        check_type = check["type"]
        values = check.get("values", [])
        details = ""

        if check_type == "contains_any":
            passed = isinstance(values, list) and any(
                isinstance(value, str) and value.casefold() in evaluated_text.casefold()
                for value in values
            )
            details = f"命中任一：{values}"
        elif check_type == "contains_all":
            passed = isinstance(values, list) and bool(values) and all(
                isinstance(value, str) and value.casefold() in evaluated_text.casefold()
                for value in values
            )
            details = f"全部包含：{values}"
        elif check_type == "excludes_all":
            passed = isinstance(values, list) and all(
                not isinstance(value, str) or value.casefold() not in evaluated_text.casefold()
                for value in values
            )
            details = f"不得包含：{values}"
        elif check_type == "regex":
            pattern = check.get("pattern", "")
            passed = isinstance(pattern, str) and bool(
                re.search(pattern, evaluated_text, re.MULTILINE)
            )
            details = f"匹配表达式：{pattern}"
        elif check_type == "sentence_count":
            count = _count_sentences(evaluated_text)
            minimum = int(check.get("min", 0))
            maximum = int(check.get("max", 2**31 - 1))
            passed = minimum <= count <= maximum
            details = f"句数 {count}，要求 {minimum}..{maximum}"
        elif check_type == "list_item_count":
            count = _count_list_items(evaluated_text)
            minimum = int(check.get("min", 0))
            maximum = int(check.get("max", 2**31 - 1))
            passed = minimum <= count <= maximum
            details = f"列表项 {count}，要求 {minimum}..{maximum}"
        else:  # pragma: no cover - load_cases rejects unknown types
            passed = False
            details = f"未知检查类型：{check_type}"

        outcomes.append(
            {
                "type": check_type,
                "description": check["description"],
                "passed": passed,
                "details": details,
            }
        )

    passed_checks = sum(1 for outcome in outcomes if outcome["passed"])
    return {
        "auto_passed": passed_checks == len(outcomes),
        "score": round(passed_checks / len(outcomes), 4) if outcomes else 0.0,
        "passed_checks": passed_checks,
        "check_count": len(outcomes),
        "evaluated_text": evaluated_text,
        "checks": outcomes,
    }


def fetch_health(base_url: str, timeout: float) -> dict[str, object]:
    try:
        response = requests.get(
            f"{base_url.rstrip('/')}/api/health",
            timeout=min(timeout, 10.0),
        )
        response.raise_for_status()
        body = response.json()
        return body if isinstance(body, dict) else {"error": "健康检查返回格式不正确"}
    except (requests.RequestException, ValueError) as exc:
        return {"error": str(exc)}


def run_case(base_url: str, case: dict[str, Any], timeout: float) -> dict[str, object]:
    started = time.perf_counter()
    result: dict[str, object] = {
        "id": case["id"],
        "category": case.get("category", ""),
        "message": case["message"],
        "expect": case.get("expect", ""),
        "manual_review": case.get("manual_review", []),
    }
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={"message": case["message"]},
            timeout=timeout,
        )
        result["status_code"] = response.status_code
        result["http_ok"] = response.ok
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:2_000]}
        result["response"] = body
        reply = body.get("reply", "") if isinstance(body, dict) else ""
        if response.ok and isinstance(reply, str) and reply.strip():
            result["quality"] = evaluate_reply(
                reply.strip(),
                case["checks"],
                case["message"],
            )
        else:
            result["quality"] = {
                "auto_passed": False,
                "score": 0.0,
                "passed_checks": 0,
                "check_count": len(case["checks"]),
                "checks": [],
                "error": "HTTP 请求失败或响应中没有非空 reply",
            }
    except requests.RequestException as exc:
        result["http_ok"] = False
        result["error"] = str(exc)
        result["quality"] = {
            "auto_passed": False,
            "score": 0.0,
            "passed_checks": 0,
            "check_count": len(case["checks"]),
            "checks": [],
            "error": "无法连接聊天 API",
        }
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1_000, 2)
    return result


def _git_revision() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_dirty() -> bool | None:
    try:
        return bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def _service_code_hashes() -> dict[str, str]:
    relative_paths = (
        Path("backend/app/main.py"),
        Path("backend/app/llm_service.py"),
        Path("backend/app/planning.py"),
        Path("backend/app/persona.py"),
        Path("backend/app/safety.py"),
    )
    return {
        path.as_posix(): hashlib.sha256((PROJECT_ROOT / path).read_bytes()).hexdigest()
        for path in relative_paths
    }


def build_summary(results: list[dict[str, object]]) -> dict[str, object]:
    http_passed = sum(1 for result in results if result.get("http_ok"))
    quality_passed = sum(
        1
        for result in results
        if isinstance(result.get("quality"), dict)
        and result["quality"].get("auto_passed")
    )
    passed_checks = sum(
        int(result["quality"].get("passed_checks", 0))
        for result in results
        if isinstance(result.get("quality"), dict)
    )
    total_checks = sum(
        int(result["quality"].get("check_count", 0))
        for result in results
        if isinstance(result.get("quality"), dict)
    )
    category_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"case_count": 0, "auto_passed_cases": 0}
    )
    for result in results:
        category = str(result.get("category") or "uncategorized")
        category_counts[category]["case_count"] += 1
        quality = result.get("quality")
        if isinstance(quality, dict) and quality.get("auto_passed"):
            category_counts[category]["auto_passed_cases"] += 1

    return {
        "case_count": len(results),
        "http_passed_cases": http_passed,
        "auto_passed_cases": quality_passed,
        "auto_case_pass_rate": round(quality_passed / len(results), 4) if results else 0.0,
        "passed_checks": passed_checks,
        "check_count": total_checks,
        "auto_check_pass_rate": round(passed_checks / total_checks, 4) if total_checks else 0.0,
        "manual_review_required": any(result.get("manual_review") for result in results),
        "categories": dict(sorted(category_counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    results = [run_case(args.base_url, case, args.timeout) for case in cases]
    summary = build_summary(results)
    case_bytes = args.cases.read_bytes()
    report = {
        "evaluation_version": 2,
        "generated_at": datetime.now().astimezone().isoformat(),
        "base_url": args.base_url,
        "cases_file": str(args.cases.resolve()),
        "cases_sha256": hashlib.sha256(case_bytes).hexdigest(),
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "git_revision": _git_revision(),
        "git_dirty": _git_dirty(),
        "service_code_sha256": _service_code_hashes(),
        "api_health": fetch_health(args.base_url, args.timeout),
        "summary": summary,
        "results": results,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / (
        f"{args.cases.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "评测完成："
        f"HTTP {summary['http_passed_cases']}/{summary['case_count']}，"
        f"自动质量规则 {summary['passed_checks']}/{summary['check_count']}，"
        f"整例通过 {summary['auto_passed_cases']}/{summary['case_count']}"
    )
    if summary["manual_review_required"]:
        print("报告包含人工复核项；自动规则通过不等于最终质量验收通过。")
    print(f"结果文件：{output_path}")
    complete = (
        summary["http_passed_cases"] == summary["case_count"]
        and summary["auto_passed_cases"] == summary["case_count"]
    )
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
