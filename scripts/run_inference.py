#!/usr/bin/env python3
"""
Module: run_inference
Purpose: Run model inference on the RELiC long-context dataset via OpenRouter, with prompt
         versioning and task modes:
         - Task 1: with full book context (uses books JSON)
         - Task 2: without book context (parametric knowledge)
         - Task 3: line-number prediction with full book context and line numbers
         - Task 4: line-number prediction without book context

Key features:
    - Prompt registry driven (see scripts/prompts.py) with versioning
    - Self-describing output columns: response_{model}_{taskX}_{promptVersion}
    - Concurrency control, retries, and resume from existing output

CLI Usage (examples):
    # Task 2, prompt v1, run 5 rows, custom model
    python scripts/run_inference.py \
        --input_path data/long_context_relic_acl.csv \
        --output_path data/output.csv \
        --model anthropic/claude-3.5-sonnet \
        --task 2 \
        --prompt_version v1 \
        --limit 5

"""
import asyncio
import argparse
import pandas as pd
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import AsyncOpenAI
import logging
from typing import Optional, Dict, Any

# Import prompt registry (single source of truth)
try:
    from scripts.prompts import get_prompt_template
except ImportError:
    # Handle case where script is run from scripts directory
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.prompts import get_prompt_template

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---

# Default API Base (OpenRouter)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

def construct_prompt(row, task_type, prompt_version, books_data=None):
    """
    Constructs the prompt based on the task type, version, and row data.
    """
    book_title = row.get("book_title", "Unknown Book")
    # Prompt templates expect these keys:
    # - book_sentences: the full book text (joined sentences)
    # - lit_analysis_excerpt: the commentary text with MASK
    # - book_title_snake_case: used in the prompt tags
    lit_analysis_excerpt = row.get("Full_Mask_comment") or ""
    if not lit_analysis_excerpt:
        raise ValueError("Missing required field 'Full_Mask_comment' in input row.")

    try:
        template = get_prompt_template(task_type, prompt_version)
    except ValueError as e:
        # Surface invalid prompt version immediately to stop the run
        logger.error(str(e))
        sys.exit(1)

    # Normalize book key to match JSON keys (lower + underscores)
    normalized_book_key = book_title.replace(" ", "_").lower()

    # Build book text depending on task
    if task_type == 1:
        if not books_data or normalized_book_key not in books_data:
            raise ValueError(f"Book content for '{book_title}' not found in provided JSON.")
        book_sentences = " ".join(books_data[normalized_book_key])
        book_sentences_with_line_numbers = None
    elif task_type == 3:
        if not books_data or normalized_book_key not in books_data:
            raise ValueError(f"Book content for '{book_title}' not found in provided JSON.")
        book_lines = books_data[normalized_book_key]
        # 传统行号从 1 开始，格式：数字和内容之间一个空格，无冒号
        book_sentences_with_line_numbers = "\n".join(
            f"{i+1} {line}" for i, line in enumerate(book_lines)
        )
        book_sentences = book_sentences_with_line_numbers
    elif task_type == 4:
        # Task 4: Line number prediction without context (parametric knowledge)
        book_sentences = ""
        book_sentences_with_line_numbers = None
    else:
        # Task 2 uses no external book context; keep placeholder empty
        book_sentences = ""
        book_sentences_with_line_numbers = None

    book_title_snake_case = normalized_book_key

    format_kwargs = {
        "book_title": book_title,
        "book_sentences": book_sentences,
        "lit_analysis_excerpt": lit_analysis_excerpt,
        "book_title_snake_case": book_title_snake_case,
    }
    if task_type == 3:
        format_kwargs["book_sentences_with_line_numbers"] = book_sentences_with_line_numbers

    return template.format(**format_kwargs)


class ModelInference:
    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: str = OPENROUTER_BASE_URL,
        concurrency: int = 5,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        timeout: int = 60,
    ):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        # Semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(concurrency)

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        before_sleep=lambda retry_state: logger.warning(f"Retrying request due to error: {retry_state.outcome.exception()}")
    )
    async def get_response(self, prompt: str) -> Optional[Dict[str, Any]]:
        async with self.semaphore:
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature, # Greedy decoding by default for reproducibility
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                )
                usage = None
                if getattr(response, "usage", None):
                    try:
                        usage = response.usage.model_dump()
                    except Exception:
                        usage = None

                return {
                    "content": response.choices[0].message.content,
                    "usage": usage,
                    "id": getattr(response, "id", None),
                    "created": getattr(response, "created", None),
                    "api_model": getattr(response, "model", None),
                }
            except Exception as e:
                # Log the error but let tenacity handle the retry logic
                logger.error(f"API Error: {str(e)}")
                raise e

async def run_single(idx, row, inference_engine, task_type, prompt_version, books_data):
    """
    Build prompt, call model, and return structured log entry.
    """
    book_title = row.get("book_title")
    commenter = row.get("commenter")
    try:
        prompt = construct_prompt(row, task_type, prompt_version, books_data)
    except ValueError as e:
        return {
            "row_index": int(idx),
            "uuid": str(row.get("uuid", idx)),
            "book_title": book_title,
            "commenter": commenter,
            "task_type": task_type,
            "prompt_version": prompt_version,
            "temperature": inference_engine.temperature,
            "status": "error",
            "error": str(e),
        }

    start_ts = time.time()
    start_iso = datetime.utcfromtimestamp(start_ts).isoformat() + "Z"
    try:
        resp = await inference_engine.get_response(prompt)
        end_ts = time.time()
        end_iso = datetime.utcfromtimestamp(end_ts).isoformat() + "Z"
        return {
            "row_index": int(idx),
            "uuid": str(row.get("uuid", idx)),
            "book_title": book_title,
            "commenter": commenter,
            "task": task_type,
            "task_type": task_type,
            "prompt_version": prompt_version,
            "model": inference_engine.model_name,
            "api_model": resp.get("api_model") if resp else None,
            "completion_id": resp.get("id") if resp else None,
            "created": resp.get("created") if resp else None,
            "temperature": inference_engine.temperature,
            "timestamp_start": start_iso,
            "timestamp_end": end_iso,
            "duration_ms": int((end_ts - start_ts) * 1000),
            "response_raw": resp.get("content") if resp else None,
            "usage": resp.get("usage") if resp else None,
            "status": "ok",
            "error": None,
        }
    except Exception as e:
        end_ts = time.time()
        end_iso = datetime.utcfromtimestamp(end_ts).isoformat() + "Z"
        return {
            "row_index": int(idx),
            "uuid": str(row.get("uuid", idx)),
            "book_title": book_title,
            "commenter": commenter,
            "task": task_type,
            "task_type": task_type,
            "prompt_version": prompt_version,
            "model": inference_engine.model_name,
            "temperature": inference_engine.temperature,
            "timestamp_start": start_iso,
            "timestamp_end": end_iso,
            "duration_ms": int((end_ts - start_ts) * 1000),
            "response_raw": None,
            "usage": None,
            "status": "error",
            "error": str(e),
        }

async def main_async():
    parser = argparse.ArgumentParser(description="Run LLM inference on literary data via OpenRouter/OpenAI API.")
    parser.add_argument("--input_path", "-i", type=str, required=True, help="Path to input CSV file.")
    parser.add_argument("--raw_log_path", "-rl", type=str, required=True, help="Path to append raw JSONL logs.")
    parser.add_argument("--books_path", "-b", type=str, help="Path to JSON file containing book sentences (Required for Task 1 and Task 3).")
    parser.add_argument("--model", "-m", type=str, required=True, help="Model name (e.g., openai/gpt-4o, anthropic/claude-3-opus).")
    parser.add_argument("--task", "-t", type=int, choices=[1, 2, 3, 4], required=True, help="Task type: 1 (With Book Context), 2 (No Book Context), 3 (Line Number Prediction), 4 (Line Number Prediction without Context).")
    parser.add_argument("--prompt_version", "-pv", type=str, default="v1", help="Version of the prompt to use (defined in scripts/prompts.py). Default: v1")
    parser.add_argument("--concurrency", "-c", type=int, default=5, help="Number of concurrent API requests.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows to process (for testing).")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature for the model. Default: 0.0")
    parser.add_argument("--max_tokens", type=int, default=None, help="Max tokens to generate per response. Default: provider/model default")
    parser.add_argument("--timeout", type=int, default=60, help="Per-request timeout (seconds). Default: 60")

    args = parser.parse_args()

    # 1. API Key Setup
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("Error: OPENROUTER_API_KEY environment variable not set.")
        sys.exit(1)

    # 2. Load Data
    logger.info(f"Loading input data from {args.input_path}...")
    try:
        df = pd.read_csv(args.input_path)
    except FileNotFoundError:
        logger.error(f"Input file {args.input_path} not found.")
        sys.exit(1)

    # 3. Load Books (Task 1 and Task 3 only)
    books_data = None
    if args.task in (1, 3):
        if not args.books_path:
            logger.error(f"Task {args.task} requires --books_path to be specified.")
            sys.exit(1)
        logger.info(f"Loading books data from {args.books_path}...")
        try:
            with open(args.books_path, 'r') as f:
                books_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load books JSON: {e}")
            sys.exit(1)
            
    # 4. Prepare workset (optional limit)
    if args.limit:
        df = df.iloc[:args.limit]
    total_rows = len(df)
    logger.info(f"Prepared {total_rows} rows for processing.")

    # 5. Initialize Inference Engine
    inference = ModelInference(
        api_key=api_key,
        model_name=args.model,
        concurrency=args.concurrency,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )

    # 6. Ensure log directory
    raw_log_path = Path(args.raw_log_path)
    raw_log_path.parent.mkdir(parents=True, exist_ok=True)

    # 7. Processing Loop (Batching for periodic writes)
    BATCH_SIZE = 10
    pbar = tqdm(total=total_rows, desc="Processing")

    with raw_log_path.open("a", encoding="utf-8") as log_f:
        for i in range(0, total_rows, BATCH_SIZE):
            batch_df = df.iloc[i : i + BATCH_SIZE]
            tasks = [
                run_single(idx, row, inference, args.task, args.prompt_version, books_data)
                for idx, row in batch_df.iterrows()
            ]
            results = await asyncio.gather(*tasks)

            for entry in results:
                log_f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            log_f.flush()
            pbar.update(len(batch_df))

    pbar.close()
    logger.info(f"Processing complete. Raw logs appended to {raw_log_path}")

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
