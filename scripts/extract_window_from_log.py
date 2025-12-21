#!/usr/bin/env python3
"""
将 run_inference 生成的 JSONL 原始日志与输入 CSV 通过 uuid 对齐，
抽取 <window></window> 内容并写回 CSV。
"""
import argparse
import json
import os
import re
import sys
import pandas as pd
from pathlib import Path


def _extract_tag(text: str, tag: str) -> str:
    if not isinstance(text, str):
        return ""
    matches = re.findall(fr"<{tag}>(.*?)</{tag}>", text, flags=re.DOTALL)
    if not matches:
        return ""
    return matches[0].strip()


def extract_window(text: str) -> str:
    """兼容旧调用，提取 <window>。</window>"""
    return _extract_tag(text, "window")


def extract_line(text: str) -> str:
    return _extract_tag(text, "line")


def extract_text(text: str) -> str:
    return _extract_tag(text, "text")


def load_log(log_path: Path):
    records = {}
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            uuid = str(obj.get("uuid")) if obj.get("uuid") is not None else None
            book_title = str(obj.get("book_title")) if obj.get("book_title") is not None else None
            model = str(obj.get("model")) if obj.get("model") is not None else "unknown"
            if not uuid or not book_title:
                continue
            # 使用 (uuid, book_title, model) 作为key以支持多模型
            key = (uuid, book_title, model)
            # 后写的覆盖之前的，方便重跑
            records[key] = obj
    return records


def main():
    parser = argparse.ArgumentParser(description="Merge raw JSONL logs into CSV with window extraction.")
    parser.add_argument("--input_path", "-i", required=True, help="原始输入 CSV（含 uuid 列）。")
    parser.add_argument("--log_path", "-l", required=True, help="run_inference 生成的 JSONL 路径。")
    parser.add_argument("--output_path", "-o", required=True, help="输出 CSV 路径（会覆盖/创建）。")
    parser.add_argument("--window_col_name", "-w", required=False, help="写入 <window> 提取结果的列名。")
    parser.add_argument("--line_col_name", "-lc", required=False, help="写入 <line> 提取结果的列名。")
    parser.add_argument("--text_col_name", "-tc", required=False, help="写入 <text> 提取结果的列名。")
    parser.add_argument("--model_filter", "-m", required=False, help="仅提取指定模型的数据（可选）。")

    args = parser.parse_args()

    if not any([args.window_col_name, args.line_col_name, args.text_col_name]):
        print("至少需要提供一个输出列名，例如 --window_col_name window_pred。")
        sys.exit(1)

    if not os.path.exists(args.input_path):
        print(f"Input CSV not found: {args.input_path}")
        sys.exit(1)
    if not os.path.exists(args.log_path):
        print(f"Log file not found: {args.log_path}")
        sys.exit(1)

    df = pd.read_csv(args.input_path)
    if "uuid" not in df.columns or "book_title" not in df.columns:
        print("Input CSV 必须包含 uuid 和 book_title 列用于对齐。")
        sys.exit(1)

    log_records = load_log(Path(args.log_path))
    
    # 如果指定了模型过滤，只保留该模型的记录
    if args.model_filter:
        log_records = {k: v for k, v in log_records.items() 
                      if k[2] == args.model_filter}  # k[2]是model
        print(f"过滤后保留模型 {args.model_filter} 的 {len(log_records)} 条记录。")
    
    log_keys = set(log_records.keys())
    if not log_keys:
        print(f"Log 文件无有效记录（模型: {args.model_filter}），输出为空。")
        sys.exit(0)

    df["uuid"] = df["uuid"].astype(str)
    df["book_title"] = df["book_title"].astype(str)

    # 仅保留在日志中出现过的 uuid+book_title+model
    def has_match(row):
        for key in log_keys:
            if key[0] == row["uuid"] and key[1] == row["book_title"]:
                return True
        return False
    
    df = df[df.apply(has_match, axis=1)]
    if df.empty:
        print("输入行无匹配的日志记录，输出为空。")
        sys.exit(0)

    def lookup_raw(row):
        # 在log_records中查找匹配的记录
        for key, record in log_records.items():
            if key[0] == row["uuid"] and key[1] == row["book_title"]:
                return record.get("response_raw")
        return None

    raw_series = df.apply(lookup_raw, axis=1)

    if args.window_col_name:
        df[args.window_col_name] = raw_series.apply(extract_window)
    if args.line_col_name:
        df[args.line_col_name] = raw_series.apply(extract_line)
    if args.text_col_name:
        df[args.text_col_name] = raw_series.apply(extract_text)

    # 若目标已存在，先读出来以保留其它模型列
    if os.path.exists(args.output_path):
        out_df = pd.read_csv(args.output_path)
        if "uuid" in out_df.columns and "book_title" in out_df.columns:
            out_df["uuid"] = out_df["uuid"].astype(str)
            out_df["book_title"] = out_df["book_title"].astype(str)
            out_df = out_df.set_index(["uuid", "book_title"])
            df = df.set_index(["uuid", "book_title"])
            # 只更新当前新增的列，不要覆盖已有的列
            for col in df.columns:
                out_df[col] = df[col]
            # 把旧的df中不在新df中的列保留（它们已经在out_df中了）
            df = out_df
            df.reset_index(inplace=True)
        else:
            print("警告：已有输出缺少 uuid，无法合并，直接覆盖。")

    df.to_csv(args.output_path, index=False)
    print(f"写入完成: {args.output_path}")


if __name__ == "__main__":
    main()
