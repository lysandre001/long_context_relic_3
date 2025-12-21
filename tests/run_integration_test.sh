#!/bin/bash

# Configuration
INPUT_PATH="data/Aeneid_commentary_Servius.csv"
BOOKS_PATH="data/relic_book_sentences_aeneid.json"
LIMIT=20 
RAW_LOG_DIR="tests/output/raw_logs"
#OUTPUT_TASK1="tests/output/output_task1_test.csv"
#FINAL_LOGS_TASK1_MERGED="${RAW_LOG_DIR}/task1_all_models_merged.jsonl"
OUTPUT_TASK2="tests/output/output_task2_test.csv"
FINAL_LOGS_TASK2_MERGED="${RAW_LOG_DIR}/task2_all_models_merged.jsonl"
TEMPERATURE=${TEMPERATURE:-0.1}
MAX_TOKENS=${MAX_TOKENS:-50000}
TIMEOUT=${TIMEOUT:-60}

# Optional max_tokens arg (only added if set)
MAX_TOKENS_ARG=()
if [ -n "$MAX_TOKENS" ]; then
  MAX_TOKENS_ARG=(--max_tokens "$MAX_TOKENS")
fi

# Models to test (can be overridden by env MODELS, space-separated)
if [ -n "$MODELS" ]; then
  # shellcheck disable=SC2206
  models=($MODELS)
else
  models=(
      "anthropic/claude-sonnet-4.5"
      "deepseek/deepseek-v3.2"
  )
fi

# Export API Key (Ensure this is set in your environment or here)
# export OPENROUTER_API_KEY="your_key_here"

#

# # 2. Run Task 1 (with book context) - Prompt v1_relic_explanation
# echo "--- Running Task 1 (Context) - Prompt v1_relic_explanation ---"
# for model in "${models[@]}"; do
#     echo "Processing Task 1 (v1_relic_explanation) for $model..."
    
#     safe_name=$(echo "$model" | tr '/:' '__')
#     col_name="response_${safe_name}_task1_v1_relic_explanation" # kept for window column naming
    
#     raw_log_path="${RAW_LOG_DIR}/task1_v1_relic_explanation_${safe_name}.jsonl"

#     python scripts/run_inference.py \
#         --input_path "$INPUT_PATH" \
#         --books_path "$BOOKS_PATH" \
#         --raw_log_path "$raw_log_path" \
#         --model "$model" \
#         --task 1 \
#         --prompt_version "v1_relic_explanation" \
#         --limit "$LIMIT" \
#         --concurrency 2 \
#         --temperature "$TEMPERATURE" \
#         --timeout "$TIMEOUT" \
#         "${MAX_TOKENS_ARG[@]}"

#     if [ $? -eq 0 ]; then
#         echo "✅ Task 1 (v1_relic_explanation) for $model completed."
#     else
#         echo "❌ Task 1 (v1_relic_explanation) for $model failed."
#     fi
# done

# Merge Task 1 logs (v1_text_simple) and extract <text>
echo "--- Merging Task 1 raw logs (v1_text_simple) and extracting text ---"
mkdir -p "$RAW_LOG_DIR"
cat ${RAW_LOG_DIR}/task1_v1_text_simple_*.jsonl > "$FINAL_LOGS_TASK1_MERGED"

for model in "${models[@]}"; do
    safe_name=$(echo "$model" | tr '/:' '__')
    col_task1_text="response_${safe_name}_task1_v1_text_simple"
    python scripts/extract_window_from_log.py \
        --input_path "$INPUT_PATH" \
        --log_path "$FINAL_LOGS_TASK1_MERGED" \
        --output_path "$OUTPUT_TASK1" \
        --text_col_name "${col_task1_text}_text"
done

# 3. Run Task 2 (No context) - Prompt v1_text_simple
echo "--- Running Task 2 (No context) - Prompt v1_text_simple ---"
for model in "${models[@]}"; do
    echo "Processing Task 2 (v1_text_simple) for $model..."
    
    safe_name=$(echo "$model" | tr '/:' '__')
    col_name="response_simple_${safe_name}_v1_text"
    raw_log_path="${RAW_LOG_DIR}/task2_v1_text_simple_${safe_name}.jsonl"
    
    python scripts/run_inference.py \
        --input_path "$INPUT_PATH" \
        --raw_log_path "$raw_log_path" \
        --model "$model" \
        --task 2 \
        --prompt_version "v1_text_simple" \
        --limit "$LIMIT" \
        --concurrency 2 \
        --temperature "$TEMPERATURE" \
        --timeout "$TIMEOUT" \
        "${MAX_TOKENS_ARG[@]}"
        
    if [ $? -eq 0 ]; then
        echo "✅ Task 2 (v1_text_simple) for $model completed."
    else
        echo "❌ Task 2 (v1_text_simple) for $model failed."
    fi
done

# 4. Merge Task 2 logs and extract <text>
echo "--- Merging Task 2 raw logs and extracting text ---"
cat ${RAW_LOG_DIR}/task2_v1_text_simple_*.jsonl > "$FINAL_LOGS_TASK2_MERGED"

for model in "${models[@]}"; do
    safe_name=$(echo "$model" | tr '/:' '__')
    col_task2="response_simple_${safe_name}_v1_text"
    python scripts/extract_window_from_log.py \
        --input_path "$INPUT_PATH" \
        --log_path "$FINAL_LOGS_TASK2_MERGED" \
        --output_path "$OUTPUT_TASK2" \
        --text_col_name "${col_task2}_text" \
        --model_filter "$model"
done
