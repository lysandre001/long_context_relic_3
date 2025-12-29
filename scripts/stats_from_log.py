#!/usr/bin/env python3
"""
从 JSONL 日志文件中统计 token 使用量和花销。

Usage:
    python scripts/stats_from_log.py --log_path tests/output/raw_logs/task3_all.jsonl

Output (JSON):
    {
        "total_requests": 81,
        "ok_count": 80,
        "error_count": 1,
        "prompt_tokens": 123456,
        "completion_tokens": 12345,
        "total_tokens": 135801,
        "prompt_cost": 1.23,
        "completion_cost": 0.45,
        "total_cost": 1.68,
        "by_model": {
            "anthropic/claude-sonnet-4.5": {...},
            "deepseek/deepseek-v3.2": {...}
        }
    }
"""

import argparse
import json
import sys
from collections import defaultdict


def parse_jsonl(log_path: str) -> list[dict]:
    """读取 JSONL 文件，返回记录列表"""
    records = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def compute_stats(records: list[dict]) -> dict:
    """从记录中计算统计信息"""
    stats = {
        "total_requests": 0,
        "ok_count": 0,
        "error_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "prompt_cost": 0.0,
        "completion_cost": 0.0,
        "total_cost": 0.0,
        "by_model": defaultdict(lambda: {
            "requests": 0,
            "ok_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "prompt_cost": 0.0,
            "completion_cost": 0.0,
            "total_cost": 0.0,
        }),
    }

    for rec in records:
        stats["total_requests"] += 1
        model = rec.get("model", "unknown")
        status = rec.get("status", "unknown")

        if status == "ok":
            stats["ok_count"] += 1
            stats["by_model"][model]["ok_count"] += 1
        else:
            stats["error_count"] += 1

        stats["by_model"][model]["requests"] += 1

        usage = rec.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0
        total_tokens = usage.get("total_tokens", 0) or 0
        total_cost = usage.get("cost", 0) or 0

        cost_details = usage.get("cost_details", {}) or {}
        prompt_cost = cost_details.get("upstream_inference_prompt_cost", 0) or 0
        completion_cost = cost_details.get("upstream_inference_completions_cost", 0) or 0

        # 全局累加
        stats["prompt_tokens"] += prompt_tokens
        stats["completion_tokens"] += completion_tokens
        stats["total_tokens"] += total_tokens
        stats["prompt_cost"] += prompt_cost
        stats["completion_cost"] += completion_cost
        stats["total_cost"] += total_cost

        # 按模型累加
        stats["by_model"][model]["prompt_tokens"] += prompt_tokens
        stats["by_model"][model]["completion_tokens"] += completion_tokens
        stats["by_model"][model]["total_tokens"] += total_tokens
        stats["by_model"][model]["prompt_cost"] += prompt_cost
        stats["by_model"][model]["completion_cost"] += completion_cost
        stats["by_model"][model]["total_cost"] += total_cost

    # 四舍五入花销
    stats["prompt_cost"] = round(stats["prompt_cost"], 6)
    stats["completion_cost"] = round(stats["completion_cost"], 6)
    stats["total_cost"] = round(stats["total_cost"], 6)

    for model in stats["by_model"]:
        stats["by_model"][model]["prompt_cost"] = round(stats["by_model"][model]["prompt_cost"], 6)
        stats["by_model"][model]["completion_cost"] = round(stats["by_model"][model]["completion_cost"], 6)
        stats["by_model"][model]["total_cost"] = round(stats["by_model"][model]["total_cost"], 6)

    # 转换 defaultdict 为普通 dict
    stats["by_model"] = dict(stats["by_model"])

    return stats


def main():
    parser = argparse.ArgumentParser(description="统计 JSONL 日志中的 token 和花销")
    parser.add_argument("--log_path", "-l", type=str, required=True, help="JSONL 日志文件路径")
    parser.add_argument("--output", "-o", type=str, default=None, help="输出 JSON 文件路径（默认输出到 stdout）")
    args = parser.parse_args()

    records = parse_jsonl(args.log_path)
    stats = compute_stats(records)

    output_json = json.dumps(stats, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Stats written to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()

