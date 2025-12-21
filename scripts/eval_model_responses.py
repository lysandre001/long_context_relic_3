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
from utils import response_validation, correctness_evaluation

MODELS = [
 "anthropic_claude-sonnet-4.5_task1_v1_text_simple_text",
 "deepseek_deepseek-v3.2_task1_v1_text_simple_text"
]


def main():
    parser = argparse.ArgumentParser(description="Evaluate model responses")
    parser.add_argument("-i", "--input_path", type=str, default="data/long_context_relic_acl.csv", help="Input CSV file with model responses")
    parser.add_argument("-b", "--books_sentences_path", type=str, default="data/relic_book_sentences_acl.json", help="Path JSON containing book sentences")
    parser.add_argument("-o", "--output_path", type=str, default="long_context_relic_acl_RESULTS.csv", help="Output CSV file")
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

    books_sentences = json.load(open(args.books_sentences_path))

    if args.validity_threshold is not None:
        for model in models:
            df = response_validation(df, model, args.validity_threshold, books_sentences)
            print("")

    for model in nonhuman_models:
        df = correctness_evaluation(df, model, args.correctness_threshold)
        print("")

    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print("HUMAN EVAL SET (n=40):")
    for model in models:
        df = correctness_evaluation(df, model, args.correctness_threshold, "human_eval_set")
        print("")

    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print("CLOSE READING EXAMPLES (n=39):")
    for model in nonhuman_models:
        df = correctness_evaluation(df, model, args.correctness_threshold, "close_reading_example")
        print("")

    df.to_csv(args.output_path, index=False)

if __name__ == "__main__":
    main()