#!/usr/bin/env python3
"""
Module: eval_model_responses
Purpose: Evaluate model outputs on the RELiC dataset, replicating ACL paper results.

What it does:
    - (Optional) Validity check: verify model responses exist in the primary source (books JSON)
    - Correctness evaluation: fuzzy-match responses to ground truth quotes
    - Supports full set, human_eval_set, and close_reading_example subsets

CLI Usage:
    python scripts/eval_model_responses.py \
        --input_path tests/output/output_task1_test.csv \
        --output_path tests/output/output_task1_test_results.csv \
        --books_sentences_path data/relic_book_sentences_aeneid.json \
        --correctness_threshold 80
        --validity_threshold 95 
"""



import argparse
import pandas as pd
import json
import os
import sys
from pathlib import Path
from utils import response_validation, correctness_evaluation, line_number_evaluation

MODELS = [
 "anthropic_claude-sonnet-4.5_task1_v1_text_simple_text",
 "deepseek_deepseek-v3.2_task1_v1_text_simple_text"
]


def main():
    parser = argparse.ArgumentParser(description="Evaluate model responses")
    parser.add_argument("-i", "--input_path", type=str, default="data/long_context_relic_acl.csv", help="Input CSV file with model responses")
    parser.add_argument("-b", "--books_sentences_path", type=str, default="data/relic_book_sentences_acl.json", help="Path JSON containing book sentences")
    parser.add_argument("-o", "--output_path", type=str, default="long_context_relic_acl_RESULTS.csv", help="Output CSV file")
    parser.add_argument("--task", "-t", type=int, choices=[1, 2, 3, 4], default=1, help="Task type: 1/2 = text/window, 3/4 = line-number prediction")
    parser.add_argument("--validity_threshold", type=float, default=None, help="Fuzzy match threshold for checking if model response is in primary source. If not given, will skip validity check.")
    parser.add_argument("--correctness_threshold", type=float, default=90, help="Fuzzy match threshold for checking if model response matches ground truth")
    args = parser.parse_args()

    df = pd.read_csv(args.input_path)
    df = df.astype(object).where(df.notna(), None)

    # 根据输入文件实际 response 列自动推断模型名（去掉前缀 response_）
    model_cols = [
        c for c in df.columns
        if c.startswith("response_") and not c.endswith("_ERROR")
    ]
    models = [c[len("response_"):] for c in model_cols] or MODELS
    nonhuman_models = models

    # Task 3 & 4: 行号预测，不需要 books_sentences
    if args.task in (3, 4):
        all_metrics = {"task": args.task, "models": {}}
        for model in models:
            df, metrics = line_number_evaluation(df, model, ground_truth_col="answer_quote_idx")
            all_metrics["models"][model] = {"full_set": metrics}
            print("")

        if "human_eval_set" in df.columns:
            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            print("HUMAN EVAL SET:")
            for model in models:
                subset_df = df[df["human_eval_set"] == True].copy()
                if len(subset_df) > 0:
                    _, metrics = line_number_evaluation(subset_df, model, ground_truth_col="answer_quote_idx")
                    all_metrics["models"][model]["human_eval_set"] = metrics
                    print("")

        if "close_reading_example" in df.columns:
            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            print("CLOSE READING EXAMPLES:")
            for model in nonhuman_models:
                subset_df = df[df["close_reading_example"] == True].copy()
                if len(subset_df) > 0:
                    _, metrics = line_number_evaluation(subset_df, model, ground_truth_col="answer_quote_idx")
                    all_metrics["models"][model]["close_reading_example"] = metrics
                    print("")

        if "book_title" in df.columns:
            subset_df = df[df["book_title"] == "aeneid_bookall"].copy()
            if len(subset_df) > 0:
                print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                print("AENEID_BOOKALL ONLY:")
                for model in models:
                    _, metrics = line_number_evaluation(subset_df, model, ground_truth_col="answer_quote_idx")
                    all_metrics["models"][model]["aeneid_bookall"] = metrics
                    print("")

        df.to_csv(args.output_path, index=False)
        # 输出 JSON 指标供 shell 捕获
        print("EVAL_METRICS_JSON:" + json.dumps(all_metrics))
        return

    all_metrics = {"task": args.task, "models": {}}

    # 只在需要 validity check 时才加载 books_sentences
    if args.validity_threshold is not None:
        if not os.path.exists(args.books_sentences_path):
            print(f"Warning: books_sentences_path not found: {args.books_sentences_path}, skipping validity check")
        else:
            books_sentences = json.load(open(args.books_sentences_path))
            for model in models:
                df, val_metrics = response_validation(df, model, args.validity_threshold, books_sentences)
                if model not in all_metrics["models"]:
                    all_metrics["models"][model] = {}
                all_metrics["models"][model]["validity"] = val_metrics
                print("")

    for model in nonhuman_models:
        df, corr_metrics = correctness_evaluation(df, model, args.correctness_threshold)
        if model not in all_metrics["models"]:
            all_metrics["models"][model] = {}
        all_metrics["models"][model]["full_set"] = corr_metrics
        print("")

    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print("HUMAN EVAL SET (n=40):")
    for model in models:
        # 子集评估只取统计指标，不覆盖全集评估的 correctness 结果
        _, corr_metrics = correctness_evaluation(df, model, args.correctness_threshold, "human_eval_set")
        if model not in all_metrics["models"]:
            all_metrics["models"][model] = {}
        all_metrics["models"][model]["human_eval_set"] = corr_metrics
        print("")

    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print("CLOSE READING EXAMPLES (n=39):")
    for model in nonhuman_models:
        # 子集评估只取统计指标，不覆盖全集评估的 correctness 结果
        _, corr_metrics = correctness_evaluation(df, model, args.correctness_threshold, "close_reading_example")
        if model not in all_metrics["models"]:
            all_metrics["models"][model] = {}
        all_metrics["models"][model]["close_reading_example"] = corr_metrics
        print("")

    # aeneid_bookall 单独统计
    if "book_title" in df.columns:
        subset_df = df[df["book_title"] == "aeneid_bookall"].copy()
        if len(subset_df) > 0:
            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            print("AENEID_BOOKALL ONLY:")
            for model in nonhuman_models:
                _, corr_metrics = correctness_evaluation(subset_df, model, args.correctness_threshold)
                if model not in all_metrics["models"]:
                    all_metrics["models"][model] = {}
                all_metrics["models"][model]["aeneid_bookall"] = corr_metrics
        print("")

    df.to_csv(args.output_path, index=False)
    # 输出 JSON 指标供 shell 捕获
    print("EVAL_METRICS_JSON:" + json.dumps(all_metrics))

if __name__ == "__main__":
    main()