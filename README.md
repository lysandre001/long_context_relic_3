# long_context_relic

To run evaluation from the paper, use
`python scripts/eval_model_responses.py`

The evaluation script requires the `pandas` and `rapidfuzz` packages.

The 292 long context RELiC examples are in the `data/long_context_relic_acl.csv` file. The relevant column names are:

- `book_title`: Title of the primary source book
- `prefix`: Literary analysis preceding the primary source quotation
- `suffix`: Literary analysis following the primary source quotation
- `answer_quote_text`: Ground truth primary source quotation
- `answer_quote_idx`: idx of ground truth in the list of primary source sentences
- `num_sents`: Number of sentences in ground truth
- `close_reading_example`: TRUE if example is in the close reading fold
- `human_eval_set`: TRUE if example was attempted by a human




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