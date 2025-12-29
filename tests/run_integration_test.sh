#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Change to project root directory (one level up from tests/)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

# ============================================================================
# Configuration
# ============================================================================
INPUT_PATH="data/Aeneid_commentary_Servius_sampled50.csv"
BOOKS_PATH="data/relic_book_sentences_aeneid.json"
LIMIT=50
LOG_CSV="output/log.csv"
TEMPERATURE=${TEMPERATURE:-0.1}
MAX_TOKENS=${MAX_TOKENS:-50000}
TIMEOUT=${TIMEOUT:-60}

# Generate a unique run timestamp (used for all tasks in this run)
RUN_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_ID="run_${RUN_TIMESTAMP}_$RANDOM"

# 按 RUN_ID 组织输出目录
RUN_DIR="output/${RUN_ID}"
RAW_LOG_DIR="${RUN_DIR}/raw_logs"

# Output paths (organized under RUN_DIR)
OUTPUT_TASK1="${RUN_DIR}/task1.csv"
OUTPUT_TASK2="${RUN_DIR}/task2.csv"
OUTPUT_TASK3="${RUN_DIR}/task3.csv"
OUTPUT_TASK4="${RUN_DIR}/task4.csv"
FINAL_LOGS_TASK1_MERGED="${RAW_LOG_DIR}/task1_merged.jsonl"
FINAL_LOGS_TASK2_MERGED="${RAW_LOG_DIR}/task2_merged.jsonl"
FINAL_LOGS_TASK3_MERGED="${RAW_LOG_DIR}/task3_merged.jsonl"
FINAL_LOGS_TASK4_MERGED="${RAW_LOG_DIR}/task4_merged.jsonl"

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

echo "============================================================================"
echo "Run ID: $RUN_ID"
echo "Timestamp: $RUN_TIMESTAMP"
echo "Run Directory: $RUN_DIR"
echo "============================================================================"

# Ensure output directories exist
mkdir -p "$RAW_LOG_DIR"

# Save run config for reproducibility
cat > "${RUN_DIR}/config.json" << EOF
{
    "run_id": "${RUN_ID}",
    "timestamp": "${RUN_TIMESTAMP}",
    "input_path": "${INPUT_PATH}",
    "books_path": "${BOOKS_PATH}",
    "limit": ${LIMIT},
    "temperature": ${TEMPERATURE},
    "max_tokens": ${MAX_TOKENS},
    "timeout": ${TIMEOUT},
    "models": $(printf '%s\n' "${models[@]}" | jq -R . | jq -s .)
}
EOF

# ============================================================================
# Helper function to log a task run
# ============================================================================
log_task_run() {
    local task_name=$1
    local prompt_version=$2
    local merged_log_path=$3
    local output_path=$4
    local eval_output_path=$5
    local eval_metrics=$6
    local validity_threshold=${7:-""}

    # Compute token and cost statistics
    echo "--- Computing token and cost statistics for $task_name ---"
    usage_stats=$(python scripts/stats_from_log.py --log_path "$merged_log_path" 2>/dev/null)

    # Extract stats fields
    ok_count=$(echo "$usage_stats" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('ok_count',0))")
    error_count=$(echo "$usage_stats" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('error_count',0))")
    prompt_tokens=$(echo "$usage_stats" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('prompt_tokens',0))")
    completion_tokens=$(echo "$usage_stats" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('completion_tokens',0))")
    total_tokens=$(echo "$usage_stats" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_tokens',0))")
    prompt_cost=$(echo "$usage_stats" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('prompt_cost',0))")
    completion_cost=$(echo "$usage_stats" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('completion_cost',0))")
    total_cost=$(echo "$usage_stats" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_cost',0))")
    
    # Extract per-model details (by_model)
    llm_details=$(echo "$usage_stats" | python -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('by_model',{})))")

    echo "  OK: $ok_count, Errors: $error_count"
    echo "  Tokens - Prompt: $prompt_tokens, Completion: $completion_tokens, Total: $total_tokens"
    echo "  Cost - Prompt: \$$prompt_cost, Completion: \$$completion_cost, Total: \$$total_cost"
    
    # Print per-model details
    echo "  Per-model details:"
    echo "$usage_stats" | python -c "
import sys, json
d = json.load(sys.stdin)
for model, stats in d.get('by_model', {}).items():
    print(f\"    {model}: tokens={stats.get('total_tokens',0)}, cost=\${stats.get('total_cost',0)}\")
"

    # Write to log.csv
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    models_joined=$(printf "%s|" "${models[@]}")
    models_joined=${models_joined%|}

    # Create header if missing
    if [ ! -s "$LOG_CSV" ]; then
        echo "timestamp,run_id,task,prompt,models,input_path,books_path,limit,temperature,max_tokens,timeout,validity_threshold,raw_log_path_merged,output_path,eval_output_path,ok_count,error_count,prompt_tokens,completion_tokens,total_tokens,prompt_cost,completion_cost,total_cost,status,eval_metrics,LLM_details,notes" >> "$LOG_CSV"
    fi

    # Escape JSON quotes for CSV
    eval_metrics_escaped=$(echo "$eval_metrics" | sed 's/"/""/g')
    llm_details_escaped=$(echo "$llm_details" | sed 's/"/""/g')
    echo "${timestamp},${RUN_ID},${task_name},${prompt_version},\"${models_joined}\",${INPUT_PATH},${BOOKS_PATH},${LIMIT},${TEMPERATURE},${MAX_TOKENS},${TIMEOUT},${validity_threshold},${merged_log_path},${output_path},${eval_output_path},${ok_count},${error_count},${prompt_tokens},${completion_tokens},${total_tokens},${prompt_cost},${completion_cost},${total_cost},ok,\"${eval_metrics_escaped}\",\"${llm_details_escaped}\"," >> "$LOG_CSV"

    echo "--- $task_name logged to $LOG_CSV ---"
}


# ============================================================================
# Task 1: Context-based prediction (with book context)
# ============================================================================
echo ""
echo "============================================================================"
echo "Task 1 (Context) - Prompt v1_text_simple_edited"
echo "============================================================================"

for model in "${models[@]}"; do
    echo "Processing Task 1 for $model..."
    
    safe_name=$(echo "$model" | tr '/:' '__')
    raw_log_path="${RAW_LOG_DIR}/task1_${safe_name}.jsonl"

    python scripts/run_inference.py \
        --input_path "$INPUT_PATH" \
        --books_path "$BOOKS_PATH" \
        --raw_log_path "$raw_log_path" \
        --model "$model" \
        --task 1 \
        --prompt_version "v1_text_simple_edited" \
        --limit "$LIMIT" \
        --concurrency 2 \
        --temperature "$TEMPERATURE" \
        --timeout "$TIMEOUT" \
        "${MAX_TOKENS_ARG[@]}"

    if [ $? -eq 0 ]; then
        echo "✅ Task 1 for $model completed."
    else
        echo "❌ Task 1 for $model failed."
    fi
done

# Merge Task 1 logs and extract <window>
echo "--- Merging Task 1 raw logs and extracting window ---"
cat ${RAW_LOG_DIR}/task1_*.jsonl > "$FINAL_LOGS_TASK1_MERGED"

for model in "${models[@]}"; do
    safe_name=$(echo "$model" | tr '/:' '__')
    col_task1_window="response_${safe_name}_task1_v1_text_simple_edited"
    python scripts/extract_window_from_log.py \
        --input_path "$INPUT_PATH" \
        --log_path "$FINAL_LOGS_TASK1_MERGED" \
        --output_path "$OUTPUT_TASK1" \
        --window_col_name "${col_task1_window}_window" \
        --model_filter "$model"
done

# Evaluate Task 1
echo "--- Evaluating Task 1 results ---"
eval_output_task1=$(python scripts/eval_model_responses.py \
    --input_path "$OUTPUT_TASK1" \
    --output_path "${OUTPUT_TASK1%.csv}_results.csv" \
    --books_sentences_path "$BOOKS_PATH" \
    --validity_threshold 95 \
    --task 1 2>&1)

echo "$eval_output_task1" | grep -v "^EVAL_METRICS_JSON:"
eval_metrics_task1=$(echo "$eval_output_task1" | grep "^EVAL_METRICS_JSON:" | sed 's/^EVAL_METRICS_JSON://')
[ -z "$eval_metrics_task1" ] && eval_metrics_task1="{}"

# Log Task 1
log_task_run "task1" "v1_text_simple_edited" "$FINAL_LOGS_TASK1_MERGED" "$OUTPUT_TASK1" "${OUTPUT_TASK1%.csv}_results.csv" "$eval_metrics_task1" "95"


# ============================================================================
# Task 2: No context prediction
# ============================================================================
echo ""
echo "============================================================================"
echo "Task 2 (No context) - Prompt v1_text_simple"
echo "============================================================================"

for model in "${models[@]}"; do
    echo "Processing Task 2 for $model..."
    
    safe_name=$(echo "$model" | tr '/:' '__')
    raw_log_path="${RAW_LOG_DIR}/task2_${safe_name}.jsonl"
    
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
        echo "✅ Task 2 for $model completed."
    else
        echo "❌ Task 2 for $model failed."
    fi
done

# Merge Task 2 logs and extract <text>
echo "--- Merging Task 2 raw logs and extracting text ---"
cat ${RAW_LOG_DIR}/task2_*.jsonl > "$FINAL_LOGS_TASK2_MERGED"

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

# Evaluate Task 2
echo "--- Evaluating Task 2 results ---"
eval_output_task2=$(python scripts/eval_model_responses.py \
    --input_path "$OUTPUT_TASK2" \
    --output_path "${OUTPUT_TASK2%.csv}_results.csv" \
    --books_sentences_path "$BOOKS_PATH" \
    --validity_threshold 95 \
    --task 2 2>&1)

echo "$eval_output_task2" | grep -v "^EVAL_METRICS_JSON:"
eval_metrics_task2=$(echo "$eval_output_task2" | grep "^EVAL_METRICS_JSON:" | sed 's/^EVAL_METRICS_JSON://')
[ -z "$eval_metrics_task2" ] && eval_metrics_task2="{}"

# Log Task 2
log_task_run "task2" "v1_text_simple" "$FINAL_LOGS_TASK2_MERGED" "$OUTPUT_TASK2" "${OUTPUT_TASK2%.csv}_results.csv" "$eval_metrics_task2" "95"


# ============================================================================
# Task 3: Line Number Prediction
# ============================================================================
echo ""
echo "============================================================================"
echo "Task 3 (Line Number Prediction) - Prompt v1_line_simple"
echo "============================================================================"

for model in "${models[@]}"; do
    echo "Processing Task 3 for $model..."
    
    safe_name=$(echo "$model" | tr '/:' '__')
    raw_log_path="${RAW_LOG_DIR}/task3_${safe_name}.jsonl"

    python scripts/run_inference.py \
        --input_path "$INPUT_PATH" \
        --books_path "$BOOKS_PATH" \
        --raw_log_path "$raw_log_path" \
        --model "$model" \
        --task 3 \
        --prompt_version "v1_line_simple" \
        --limit "$LIMIT" \
        --concurrency 2 \
        --temperature "$TEMPERATURE" \
        --timeout "$TIMEOUT" \
        "${MAX_TOKENS_ARG[@]}"

    if [ $? -eq 0 ]; then
        echo "✅ Task 3 for $model completed."
    else
        echo "❌ Task 3 for $model failed."
    fi
done

# Merge Task 3 logs and extract <line>
echo "--- Merging Task 3 raw logs and extracting line numbers ---"
cat ${RAW_LOG_DIR}/task3_*.jsonl > "$FINAL_LOGS_TASK3_MERGED"

for model in "${models[@]}"; do
    safe_name=$(echo "$model" | tr '/:' '__')
    col_task3_line="response_${safe_name}_task3_v1_line_simple"
    python scripts/extract_window_from_log.py \
        --input_path "$INPUT_PATH" \
        --log_path "$FINAL_LOGS_TASK3_MERGED" \
        --output_path "$OUTPUT_TASK3" \
        --line_col_name "${col_task3_line}_line" \
        --model_filter "$model"
done

# Evaluate Task 3
echo "--- Evaluating Task 3 results ---"
eval_output_task3=$(python scripts/eval_model_responses.py \
    --input_path "$OUTPUT_TASK3" \
    --output_path "${OUTPUT_TASK3%.csv}_results.csv" \
    --task 3 2>&1)

echo "$eval_output_task3" | grep -v "^EVAL_METRICS_JSON:"
eval_metrics_task3=$(echo "$eval_output_task3" | grep "^EVAL_METRICS_JSON:" | sed 's/^EVAL_METRICS_JSON://')
[ -z "$eval_metrics_task3" ] && eval_metrics_task3="{}"

# Log Task 3
log_task_run "task3" "v1_line_simple" "$FINAL_LOGS_TASK3_MERGED" "$OUTPUT_TASK3" "${OUTPUT_TASK3%.csv}_results.csv" "$eval_metrics_task3"


# ============================================================================
# Task 4: Line Number Prediction without Context
# ============================================================================
echo ""
echo "============================================================================"
echo "Task 4 (Line Number Prediction without Context) - Prompt v1"
echo "============================================================================"

for model in "${models[@]}"; do
    echo "Processing Task 4 for $model..."
    
    safe_name=$(echo "$model" | tr '/:' '__')
    raw_log_path="${RAW_LOG_DIR}/task4_${safe_name}.jsonl"

    python scripts/run_inference.py \
        --input_path "$INPUT_PATH" \
        --raw_log_path "$raw_log_path" \
        --model "$model" \
        --task 4 \
        --prompt_version "v1" \
        --limit "$LIMIT" \
        --concurrency 2 \
        --temperature "$TEMPERATURE" \
        --timeout "$TIMEOUT" \
        "${MAX_TOKENS_ARG[@]}"

    if [ $? -eq 0 ]; then
        echo "✅ Task 4 for $model completed."
    else
        echo "❌ Task 4 for $model failed."
    fi
done

# Merge Task 4 logs and extract <line>
echo "--- Merging Task 4 raw logs and extracting line numbers ---"
cat ${RAW_LOG_DIR}/task4_*.jsonl > "$FINAL_LOGS_TASK4_MERGED"

for model in "${models[@]}"; do
    safe_name=$(echo "$model" | tr '/:' '__')
    col_task4_line="response_${safe_name}_task4_v1"
    python scripts/extract_window_from_log.py \
        --input_path "$INPUT_PATH" \
        --log_path "$FINAL_LOGS_TASK4_MERGED" \
        --output_path "$OUTPUT_TASK4" \
        --line_col_name "${col_task4_line}_line" \
        --model_filter "$model"
done

# Evaluate Task 4
echo "--- Evaluating Task 4 results ---"
eval_output_task4=$(python scripts/eval_model_responses.py \
    --input_path "$OUTPUT_TASK4" \
    --output_path "${OUTPUT_TASK4%.csv}_results.csv" \
    --task 4 2>&1)

echo "$eval_output_task4" | grep -v "^EVAL_METRICS_JSON:"
eval_metrics_task4=$(echo "$eval_output_task4" | grep "^EVAL_METRICS_JSON:" | sed 's/^EVAL_METRICS_JSON://')
[ -z "$eval_metrics_task4" ] && eval_metrics_task4="{}"

# Log Task 4
log_task_run "task4" "v1" "$FINAL_LOGS_TASK4_MERGED" "$OUTPUT_TASK4" "${OUTPUT_TASK4%.csv}_results.csv" "$eval_metrics_task4"


# ============================================================================
# Summary
# ============================================================================
echo ""
echo "============================================================================"
echo "Run Complete: $RUN_ID"
echo "============================================================================"
echo "Run Directory: $RUN_DIR"
echo "  - task1.csv, task1_results.csv"
echo "  - task2.csv, task2_results.csv"
echo "  - task3.csv, task3_results.csv"
echo "  - task4.csv, task4_results.csv"
echo "  - raw_logs/"
echo "  - config.json"
echo "Global Log: $LOG_CSV"
