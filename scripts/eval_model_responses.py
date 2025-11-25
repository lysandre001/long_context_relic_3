#!/usr/bin/env python3
"""
Evaluation script to replicate ACL paper results.
Takes a JSON file containing evaluation data as a command-line argument.
"""

import argparse
import pandas as pd
import json
import os
import sys
from pathlib import Path
from utils import response_validation, correctness_evaluation

MODELS = [
    "human",
    "simple_gemini-2.5-pro-preview-05-06",
    "simple_o3-2025-04-16",
    "simple_gemini-1.5-pro",
    "simple_o1-2024-12-17",
    "simple_gpt-4o-2024-11-20",
    "simple_qwen2.5-72b-instruct",
    "simple_llama-3.1-8b-instruct",
    "simple_qwen2.5-7b-instruct",
    "simple_llama-3.3-70b-instruct",
    "gemini-2.5-pro-preview-05-06",
    "gpt-4.1-2025-04-14",
    "o3-2025-04-16",
    "gemini-1.5-pro",
    "claude-3-7-sonnet-20250219",
    "deepseek-r1",
    "gpt-4o-2024-11-20",
    "qwen3-32b",
    "qwen3-8b",
    "o3-mini-2025-01-31",
    "gpt-5-2025-08-07",
    "simple_gpt-5-2025-08-07",
    "simple_gpt-5.1-2025-11-13",
    "gpt-5.1-2025-11-13"
]

NONHUMAN_MODELS = MODELS[1:]


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
    books_sentences = json.load(open(args.books_sentences_path))

    if args.validity_threshold is not None:
        for model in MODELS:
            df = response_validation(df, model, args.validity_threshold, books_sentences)
            print("")

    for model in NONHUMAN_MODELS:
        df = correctness_evaluation(df, model, args.correctness_threshold)
        print("")

    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print("HUMAN EVAL SET (n=40):")
    for model in MODELS:
        df = correctness_evaluation(df, model, args.correctness_threshold, "human_eval_set")
        print("")

    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print("CLOSE READING EXAMPLES (n=39):")
    for model in NONHUMAN_MODELS:
        df = correctness_evaluation(df, model, args.correctness_threshold, "close_reading_example")
        print("")

    df.to_csv(args.output_path, index=False)

if __name__ == "__main__":
    main()