import pandas as pd
from rapidfuzz import fuzz, utils
import re

def response_validation(df, model, threshold, book_sentences):
    resp_col = f"response_{model}"
    err_col  = f"response_{model}_ERROR"

    results_df = df.copy()
    
    # 预先初始化 ERROR 列为 None，避免 'nan' 字符串问题
    results_df[err_col] = None

    scores = []
    matches = 0
    not_in_primary_source = 0
    total_eval = 0

    for idx, row in results_df.iterrows():
        model_response = row[resp_col]

        # Skip empty / null / nan responses
        if not isinstance(model_response, str) or model_response.strip() == "":
            continue

        primary_source = " ".join(book_sentences[row["book_title"]])
        
        total_eval += 1

        # compute fuzzy match
        score = fuzz.partial_ratio(
            primary_source,
            model_response,
            processor=utils.default_process
        )

        scores.append(score)

        # classification
        if score > threshold:
            matches += 1
        else:
            not_in_primary_source += 1
            results_df.at[idx, err_col] = "Model generated window not found in primary source"

    # Print summary
    if total_eval > 0:
        print(
            f"Model: {model}, Matches: {matches}/{total_eval} "
            f"({matches/total_eval*100:.1f}%), "
            f"Not in primary source: {not_in_primary_source}"
        )
    else:
        print(f"Model: {model}, No valid responses to validate.")

    metrics = {
        "total_eval": total_eval,
        "matches": matches,
        "not_in_primary_source": not_in_primary_source,
        "match_rate": round(matches / total_eval * 100, 1) if total_eval > 0 else 0,
    }

    return results_df, metrics

def correctness_evaluation(df, model, threshold, filter_col=None):
    results_df = df.copy()

    resp_col = f"response_{model}"
    err_col  = f"response_{model}_ERROR"
    corr_col = f"correctness_{model}_FUZZY_MATCH"

    # 确保存在错误列，避免后续 KeyError
    if err_col not in df.columns:
        df[err_col] = None
        results_df[err_col] = None

    # 预创建结果列，避免 dtype 不匹配警告
    results_df[corr_col] = pd.Series([None] * len(results_df), dtype=object)

    length_ratios = []
    correctness_counts = {True: 0, False: 0}
    total_valid = 0

    for idx, row in df.iterrows():
        if filter_col and row[filter_col] is not True:
            continue
        ground_truth   = row["answer_quote_text"]
        model_response = row[resp_col]
        err            = row.get(err_col, None)

        # 跳过没有 ground_truth 的行
        has_ground_truth = isinstance(ground_truth, str) and ground_truth.strip() != ""
        if not has_ground_truth:
            results_df.at[idx, corr_col] = None
            continue

        has_response = isinstance(model_response, str) and model_response.strip() != ""

        if has_response and (err is None or pd.isna(err)):
            total_valid += 1
            length_ratios.append(len(model_response) / len(ground_truth))

            score = fuzz.partial_ratio(
                ground_truth,
                model_response,
                processor=utils.default_process
            )

            if score > threshold:
                correctness_counts[True] += 1
                results_df.at[idx, corr_col] = True
            else:
                correctness_counts[False] += 1
                results_df.at[idx, corr_col] = False
        else:
            results_df.at[idx, corr_col] = None
    if filter_col:
        n = len(df[df[filter_col] == True])
    else:
        n = len(df)
    
    avg_length_ratio = round(sum(length_ratios) / len(length_ratios), 2) if length_ratios else None
    accuracy = round(correctness_counts[True] / n * 100, 1) if n > 0 else 0
    
    if n == 0:
        print(f"Model: {model}, DataFrame is empty.")
    else:
        print(f"Model: {model}, Accuracy: {correctness_counts[True]}/{n} ({accuracy}%)")
        if length_ratios:
            print(f"Model: {model}, Average length ratio: {avg_length_ratio}")
        else:
            print(f"Model: {model}, Average length ratio: N/A (no valid matches)")

    metrics = {
        "total": n,
        "total_valid": total_valid,
        "correct": correctness_counts[True],
        "incorrect": correctness_counts[False],
        "accuracy": accuracy,
        "avg_length_ratio": avg_length_ratio,
    }

    return results_df, metrics


def line_number_evaluation(df, model, ground_truth_col="answer_quote_idx"):
    """
    评估行号预测准确性：
    - exact: 预测行号与真实行号相同
    - within5: 与真实行号差值 <= 5
    - within20: 与真实行号差值 <= 20
    """
    results_df = df.copy()

    resp_col = f"response_{model}"
    err_col = f"response_{model}_ERROR"
    exact_col = f"line_exact_{model}"
    within5_col = f"line_within5_{model}"
    within20_col = f"line_within20_{model}"

    # 预创建结果列，避免 dtype 不匹配警告
    results_df[exact_col] = pd.Series([None] * len(results_df), dtype=object)
    results_df[within5_col] = pd.Series([None] * len(results_df), dtype=object)
    results_df[within20_col] = pd.Series([None] * len(results_df), dtype=object)

    def extract_line_number(text):
        # 如果已经是数字类型（包括 numpy 类型），直接返回
        import numpy as np
        if isinstance(text, (int, float, np.integer, np.floating)) and not pd.isna(text):
            return int(text)
        if not isinstance(text, str):
            return None
        tag_match = re.search(r"<line>\s*(\d+)\s*</line>", text, flags=re.IGNORECASE)
        if tag_match:
            return int(tag_match.group(1))
        num_match = re.search(r"\b(\d+)\b", text)
        if num_match:
            return int(num_match.group(1))
        return None

    exact_count = within5_count = within20_count = total_valid = 0

    for idx, row in results_df.iterrows():
        model_response = row.get(resp_col)
        gt = row.get(ground_truth_col)

        # 先尝试提取行号（支持数字和字符串类型）
        pred_line = extract_line_number(model_response)
        
        # 如果无法提取行号，跳过
        if pred_line is None:
            results_df.at[idx, exact_col] = False
            results_df.at[idx, within5_col] = False
            results_df.at[idx, within20_col] = False
            continue

        err = row.get(err_col, None)
        if err is not None and not pd.isna(err):
            results_df.at[idx, exact_col] = False
            results_df.at[idx, within5_col] = False
            results_df.at[idx, within20_col] = False
            continue

        try:
            gt_line = None if pd.isna(gt) else int(float(str(gt)))
        except (ValueError, TypeError):
            gt_line = None

        if gt_line is None or pred_line is None:
            results_df.at[idx, exact_col] = False
            results_df.at[idx, within5_col] = False
            results_df.at[idx, within20_col] = False
            continue

        total_valid += 1
        diff = abs(pred_line - gt_line)

        exact = pred_line == gt_line
        within5 = diff <= 5
        within20 = diff <= 20

        results_df.at[idx, exact_col] = exact
        results_df.at[idx, within5_col] = within5
        results_df.at[idx, within20_col] = within20

        exact_count += int(exact)
        within5_count += int(within5)
        within20_count += int(within20)

    n = len(results_df)
    exact_rate = round(exact_count / total_valid * 100, 1) if total_valid > 0 else 0
    within5_rate = round(within5_count / total_valid * 100, 1) if total_valid > 0 else 0
    within20_rate = round(within20_count / total_valid * 100, 1) if total_valid > 0 else 0
    
    print(f"Model: {model}, Total valid predictions: {total_valid}/{n}")
    if total_valid > 0:
        print(f"Model: {model}, Exact line match: {exact_count}/{total_valid} ({exact_rate}%)")
        print(f"Model: {model}, Within 5 lines: {within5_count}/{total_valid} ({within5_rate}%)")
        print(f"Model: {model}, Within 20 lines: {within20_count}/{total_valid} ({within20_rate}%)")
    else:
        print(f"Model: {model}, No valid predictions found.")

    metrics = {
        "total": n,
        "total_valid": total_valid,
        "exact": exact_count,
        "within5": within5_count,
        "within20": within20_count,
        "exact_rate": exact_rate,
        "within5_rate": within5_rate,
        "within20_rate": within20_rate,
    }

    return results_df, metrics