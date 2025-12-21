import pandas as pd
from rapidfuzz import fuzz, utils

def response_validation(df, model, threshold, book_sentences):
    resp_col = f"response_{model}"
    err_col  = f"response_{model}_ERROR"

    results_df = df.copy()

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
    print(
        f"Model: {model}, Matches: {matches}/{total_eval} "
        f"({matches/total_eval*100:.1f}%), "
        f"Not in primary source: {not_in_primary_source}"
    )

    return results_df

def correctness_evaluation(df, model, threshold, filter_col=None):
    results_df = df.copy()

    resp_col = f"response_{model}"
    err_col  = f"response_{model}_ERROR"
    corr_col = f"correctness_{model}_FUZZY_MATCH"

    # 确保存在错误列，避免后续 KeyError
    if err_col not in df.columns:
        df[err_col] = None
        results_df[err_col] = None

    length_ratios = []
    correctness_counts = {True: 0, False: 0}
    total_valid = 0

    for idx, row in df.iterrows():
        if filter_col and row[filter_col] is not True:
            continue
        ground_truth   = row["answer_quote_text"]
        model_response = row[resp_col]
        err            = row.get(err_col, None)

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
    if n == 0:
        print(f"Model: {model}, DataFrame is empty.")
    else:
        print(f"Model: {model}, Accuracy: {correctness_counts[True]}/{n} ({correctness_counts[True]/n*100:.1f}%)")
        if length_ratios:
            print(f"Model: {model}, Average length ratio: {sum(length_ratios)/len(length_ratios):.1f}")
        else:
            print(f"Model: {model}, Average length ratio: N/A (no valid matches)")

    return results_df