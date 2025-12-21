# Bug修复总结

## 🐛 发现的严重Bug

### 问题描述
两个不同模型(anthropic/claude-sonnet-4.5 和 deepseek/deepseek-v3.2)的输出在最终CSV文件中**完全相同**,但原始JSONL日志文件中它们的响应明确不同。

### 根本原因

#### 1. 脚本设计缺陷
`extract_window_from_log.py` 脚本从合并的日志文件中提取数据时:
- **没有模型过滤机制**: 每次运行都会处理merged log中的所有模型数据
- **后写覆盖先写**: 由于使用同一个merged log,后运行的模型会覆盖之前的结果

#### 2. Bash脚本循环问题
`run_integration_test.sh` 在循环中:
```bash
for model in "${models[@]}"; do
    python scripts/extract_window_from_log.py \
        --log_path "$FINAL_LOGS_TASK2_MERGED" \  # 所有模型用同一个文件!
        --text_col_name "${col_task2}_text"
done
```

#### 3. DataFrame合并逻辑错误
原代码(行121-123):
```python
for col in out_df.columns:
    if col not in df.columns:
        df[col] = out_df[col]  # 错误:把旧数据复制到新df
```

这导致:
1. 第一个模型运行:创建CSV,写入anthropic的列
2. 第二个模型运行:
   - 从merged log提取所有数据(包括anthropic的)
   - 读取已有CSV
   - 把anthropic的旧列复制到新的df中
   - **结果:两个模型列都是最后提取的数据**

## ✅ 修复方案

### 1. 添加模型过滤参数
在 `extract_window_from_log.py` 中添加 `--model_filter` 参数:
```python
parser.add_argument("--model_filter", "-m", required=False, 
                   help="仅提取指定模型的数据(可选)。")

# 过滤逻辑
if args.model_filter:
    log_records = {k: v for k, v in log_records.items() 
                  if v.get("model") == args.model_filter}
```

### 2. 修改Bash脚本
在循环中为每个模型指定过滤器:
```bash
for model in "${models[@]}"; do
    safe_name=$(echo "$model" | tr '/:' '__')
    col_task2="response_simple_${safe_name}_v1_text"
    python scripts/extract_window_from_log.py \
        --input_path "$INPUT_PATH" \
        --log_path "$FINAL_LOGS_TASK2_MERGED" \
        --output_path "$OUTPUT_TASK2" \
        --text_col_name "${col_task2}_text" \
        --model_filter "$model"  # 新增:指定模型
done
```

### 3. 修复DataFrame合并逻辑
改进合并逻辑(行121-127):
```python
# 只更新当前新增的列,不要覆盖已有的列
for col in df.columns:
    out_df[col] = df[col]  # 正确:把新数据更新到旧df
# 把旧的df中不在新df中的列保留(它们已经在out_df中了)
df = out_df
df.reset_index(inplace=True)
```

## 🔍 验证结果

### 原始日志验证
```bash
# merged log包含两个模型各20条记录
总记录数: 40
Anthropic记录数: 20
DeepSeek记录数: 20

# 同一UUID的响应确实不同
Anthropic响应: I need to analyze this literary analysis excerpt, which discusses Virgil's opening...
DeepSeek响应: Looking at the literary analysis excerpt, the key claim is that Virgil uses the word "arma"...

两个响应是否相同: False ✓
```

## 📝 后续操作

1. **重新运行提取脚本**:
```bash
# 删除旧输出
rm tests/output/output_task2_test.csv

# 提取anthropic数据
python scripts/extract_window_from_log.py \
  --input_path data/Aeneid_commentary_Servius.csv \
  --log_path tests/output/raw_logs/task2_all_models_merged.jsonl \
  --output_path tests/output/output_task2_test.csv \
  --text_col_name response_simple_anthropic_claude-sonnet-4.5_v1_text_text \
  --model_filter "anthropic/claude-sonnet-4.5"

# 提取deepseek数据
python scripts/extract_window_from_log.py \
  --input_path data/Aeneid_commentary_Servius.csv \
  --log_path tests/output/raw_logs/task2_all_models_merged.jsonl \
  --output_path tests/output/output_task2_test.csv \
  --text_col_name response_simple_deepseek_deepseek-v3.2_v1_text_text \
  --model_filter "deepseek/deepseek-v3.2"
```

2. **验证修复**:
```bash
# 检查两个模型列是否不同
head -2 tests/output/output_task2_test.csv | cut -d',' -f12,13
```

## 🎯 影响范围

- **Task1**: 也需要类似修复(如果使用了相同的提取逻辑)
- **所有使用merged log的场景**: 都需要添加模型过滤

## 📌 经验教训

1. **单元测试的重要性**: 应该有测试验证不同模型的输出确实被正确提取
2. **数据管道验证**: 在每个步骤后验证数据的正确性
3. **避免状态共享**: 使用共享的merged log文件时需要明确的过滤机制
