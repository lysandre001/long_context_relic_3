# Long Context RELiC Benchmark

A Latin long-text understanding benchmark based on RELiC (Retrieving Evidence for Literary Claims), designed to evaluate LLM performance on classical literary commentary understanding tasks.

## 📋 Overview

This project evaluates LLM capabilities on:
- **Understanding classical Latin text** (Virgil's *Aeneid*)
- **Locating citation sources in literary commentaries**
- **Precise information retrieval in long-context settings**

### Task Types

| Task | Description | Input | Output |
|------|-------------|-------|--------|
| **Task 1** | Text retrieval (with context) | Full text + commentary (with MASK) | Quoted passage |
| **Task 2** | Text retrieval (no context) | Commentary only (with MASK) | Quoted passage (model knowledge) |
| **Task 3** | Line prediction (with context) | Full text (with line numbers) + commentary | Line number |
| **Task 4** | Line prediction (no context) | Commentary only (with MASK) | Line number (model knowledge) |

## 🏗️ Project Structure

```
long_context_relic_3/
├── data/                          # Data files
│   ├── Aeneid_commentary_*.csv    # Commentary datasets
│   └── relic_book_sentences_aeneid.json   # Full text (by line)
├── scripts/                       # Core scripts
│   ├── run_inference.py           # Model inference
│   ├── prompts.py                 # Prompt templates
│   ├── extract_window_from_log.py # Extract predictions from logs
│   ├── eval_model_responses.py    # Evaluate model performance
│   ├── stats_from_log.py          # Token and cost statistics
│   ├── sample.py                  # Balanced sampling utility
│   └── utils.py                   # Helper functions
├── tests/                         # Test scripts and outputs
├── output/                        # Production outputs
│   ├── log.csv                    # Global run log
│   └── run_{timestamp}_{id}/      # Per-run output directory
└── requirements.txt
```

## 🚀 Quick Start

### 1. Setup

```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY="your_api_key_here"
```

### 2. Run Full Test

```bash
# Default configuration
./tests/run_integration_test.sh

# Custom models
MODELS="openai/gpt-4o anthropic/claude-sonnet-4.5" ./tests/run_integration_test.sh

# Custom parameters
TEMPERATURE=0.0 MAX_TOKENS=8192 TIMEOUT=120 ./tests/run_integration_test.sh
```

## 📊 Pipeline Overview

```
run_integration_test.sh
        │
        ├── run_inference.py → raw_logs/*.jsonl
        │
        ├── merge logs → task{N}_merged.jsonl
        │
        ├── extract_window_from_log.py → task{N}.csv
        │
        ├── eval_model_responses.py → task{N}_results.csv
        │
        └── stats_from_log.py → log.csv
```

### Stage 1: Inference (`run_inference.py`)

```bash
python scripts/run_inference.py \
    --input_path data/Aeneid_commentary_Servius_sampled50.csv \
    --books_path data/relic_book_sentences_aeneid.json \
    --raw_log_path output/run_xxx/raw_logs/task1_model.jsonl \
    --model anthropic/claude-sonnet-4.5 \
    --task 1 \
    --prompt_version v1_text_simple_edited
```

### Stage 2: Extract Predictions (`extract_window_from_log.py`)

Matches logs to input CSV via `(uuid, book_title, model)` and extracts tagged content (`<window>`, `<text>`, `<line>`).

### Stage 3: Evaluation (`eval_model_responses.py`)

| Task | Metric | Description |
|------|--------|-------------|
| Task 1/2 | Validity | Output exists in source text (fuzzy match) |
| Task 1/2 | Correctness | Output matches ground truth |
| Task 3/4 | Exact | Predicted line number is correct |
| Task 3/4 | Within 5/20 | Prediction error ≤ 5/20 lines |

### Stage 4: Statistics (`stats_from_log.py`)

Outputs token counts and costs by model.

## 📁 Output Structure

```
output/run_{timestamp}_{id}/
├── config.json          # Run configuration
├── task{1-4}.csv        # Predictions
├── task{1-4}_results.csv # Evaluation results
└── raw_logs/            # Raw model responses
```

## 🔧 Prompt Templates

Defined in `scripts/prompts.py`:

| Task | Version | Description |
|------|---------|-------------|
| task1 | v1_text_simple_edited | Window selection, 1-10 words |
| task2 | v1_text_simple | No-context text prediction |
| task3 | v1_line_simple | Line number prediction |
| task4 | v1 | No-context line prediction |

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | - | Required |
| `MODELS` | claude-sonnet-4.5, deepseek-v3.2 | Models to test |
| `TEMPERATURE` | 0.1 | Sampling temperature |
| `MAX_TOKENS` | 50000 | Max generation tokens |
| `TIMEOUT` | 60 | Request timeout (seconds) |

### run_inference.py Arguments

| Argument | Description |
|----------|-------------|
| `--input_path` | Input CSV path |
| `--books_path` | Book JSON path (Task 1/3) |
| `--raw_log_path` | Log output path |
| `--model` | Model name |
| `--task` | Task type (1-4) |
| `--prompt_version` | Prompt version |
| `--limit` | Row limit |
| `--concurrency` | Concurrent requests |

## 📊 Data Formats

### Input CSV

```csv
uuid,book_title,commenter,Full_Mask_comment,answer_quote_text,answer_quote_idx
41019663,aeneid_book3,Servius,"erili voluntate ... 'MASK' dixit.",TRANSMISIT HABENDAM,329
```

### Book JSON

```json
{
  "aeneid_book1": ["ARMA virumque cano...", ...],
  "aeneid_book2": [...],
  "aeneid_bookall": [...]
}
```

## 📝 License

MIT License
