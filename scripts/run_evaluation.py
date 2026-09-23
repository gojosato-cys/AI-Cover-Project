"""Run the fixed RemLocal evaluation set against a running API."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "tests" / "eval_cases" / "rem_v1.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "eval-results"


def load_cases(path: Path) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            case = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"评测集第 {line_number} 行不是有效 JSON: {exc}") from exc
        if not isinstance(case, dict) or not case.get("id") or not case.get("message"):
            raise ValueError(f"评测集第 {line_number} 行缺少 id 或 message")
        cases.append(case)
    return cases


def run_case(base_url: str, case: dict[str, str], timeout: float) -> dict[str, object]:
    started = time.perf_counter()
    result: dict[str, object] = {
        "id": case["id"],
        "category": case.get("category", ""),
        "message": case["message"],
        "expect": case.get("expect", ""),
    }
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={"message": case["message"]},
            timeout=timeout,
        )
        result["status_code"] = response.status_code
        result["ok"] = response.ok
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:2_000]}
        result["response"] = body
    except requests.RequestException as exc:
        result["ok"] = False
        result["error"] = str(exc)
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1_000, 2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    results = [run_case(args.base_url, case, args.timeout) for case in cases]
    passed = sum(1 for result in results if result.get("ok"))
    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "base_url": args.base_url,
        "case_count": len(results),
        "passed_http_cases": passed,
        "results": results,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"rem-v1-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"评测完成：{passed}/{len(results)} 个请求返回 HTTP 2xx")
    print(f"结果文件：{output_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
