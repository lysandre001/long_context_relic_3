#!/usr/bin/env python3
"""
均衡抽样脚本：从CSV中随机抽取指定数量的数据，保证指定列的各个维度取数均衡。

示例:
    python /Users/yilin/project/251210__拉丁文benchmark/long_context_relic_3/scripts/sample.py data/Aeneid_commentary_Conington.csv -n 50 -c book_title -o Aeneid_commentary_Conington_sampled50.csv

参数:
    input.csv       输入CSV文件路径
    -n, --num       要抽取的总数量
    -c, --column    用于均衡的列名
    -o, --output    输出CSV文件路径 (可选，默认为 input_sampled.csv)
    --seed          随机种子 (可选，用于复现结果)
    --show-stats    显示抽样统计信息
"""

import argparse
import pandas as pd
import random
from pathlib import Path


def balanced_sample(df: pd.DataFrame, column: str, total_num: int, seed: int = None) -> pd.DataFrame:
    """
    从DataFrame中进行均衡抽样。
    
    Args:
        df: 输入的DataFrame
        column: 用于均衡的列名
        total_num: 要抽取的总数量
        seed: 随机种子
        
    Returns:
        抽样后的DataFrame
    """
    if seed is not None:
        random.seed(seed)
    
    # 获取该列的所有唯一值
    unique_values = df[column].unique()
    num_categories = len(unique_values)
    
    print(f"\n📊 列 '{column}' 共有 {num_categories} 个不同的值:")
    value_counts = df[column].value_counts()
    for val in unique_values:
        print(f"   - {val}: {value_counts[val]} 条")
    
    # 计算每个类别应该抽取的数量
    base_per_category = total_num // num_categories
    remainder = total_num % num_categories
    
    print(f"\n🎯 目标抽取总数: {total_num}")
    print(f"   每个类别基础抽取数: {base_per_category}")
    if remainder > 0:
        print(f"   额外分配给前 {remainder} 个类别各 1 条")
    
    sampled_dfs = []
    stats = {}
    
    # 打乱类别顺序，让余数的分配也是随机的
    shuffled_values = list(unique_values)
    random.shuffle(shuffled_values)
    
    for i, value in enumerate(shuffled_values):
        # 确定这个类别需要抽取的数量
        num_to_sample = base_per_category + (1 if i < remainder else 0)
        
        # 获取该类别的所有数据
        category_df = df[df[column] == value]
        available = len(category_df)
        
        # 如果该类别数据不足，就取全部
        actual_sample = min(num_to_sample, available)
        
        if actual_sample < num_to_sample:
            print(f"   ⚠️  类别 '{value}' 只有 {available} 条数据，不足 {num_to_sample} 条")
        
        # 随机抽样
        sampled = category_df.sample(n=actual_sample, random_state=seed)
        sampled_dfs.append(sampled)
        stats[value] = actual_sample
    
    # 合并所有抽样结果
    result = pd.concat(sampled_dfs, ignore_index=True)
    
    # 打乱最终结果的顺序
    result = result.sample(frac=1, random_state=seed).reset_index(drop=True)
    
    return result, stats


def main():
    parser = argparse.ArgumentParser(
        description="从CSV中进行均衡抽样",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从 data.csv 中按 book_title 列均衡抽取 100 条数据
  python balanced_sample.py data.csv -n 100 -c book_title
  
  # 指定输出文件和随机种子
  python balanced_sample.py data.csv -n 50 -c category -o sampled.csv --seed 42
  
  # 显示详细统计信息
  python balanced_sample.py data.csv -n 100 -c type --show-stats
        """
    )
    
    parser.add_argument("input", help="输入CSV文件路径")
    parser.add_argument("-n", "--num", type=int, required=True, help="要抽取的总数量")
    parser.add_argument("-c", "--column", required=True, help="用于均衡的列名")
    parser.add_argument("-o", "--output", help="输出CSV文件路径")
    parser.add_argument("--seed", type=int, help="随机种子")
    parser.add_argument("--show-stats", action="store_true", help="显示抽样统计信息")
    
    args = parser.parse_args()
    
    # 读取输入文件
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 错误: 文件 '{args.input}' 不存在")
        return 1
    
    print(f"📂 读取文件: {args.input}")
    df = pd.read_csv(args.input)
    print(f"   总共 {len(df)} 条数据, {len(df.columns)} 列")
    
    # 过滤掉 answer_quote_text 为空的行
    if 'answer_quote_text' in df.columns:
        original_len = len(df)
        df = df[df['answer_quote_text'].notna() & (df['answer_quote_text'].str.strip() != '')]
        filtered_count = original_len - len(df)
        if filtered_count > 0:
            print(f"   🔍 过滤掉 {filtered_count} 条 answer_quote_text 为空的数据，剩余 {len(df)} 条")
    
    # 检查列是否存在
    if args.column not in df.columns:
        print(f"❌ 错误: 列 '{args.column}' 不存在")
        print(f"   可用的列: {', '.join(df.columns)}")
        return 1
    
    # 检查抽样数量是否合理
    if args.num > len(df):
        print(f"⚠️  警告: 请求抽取 {args.num} 条，但只有 {len(df)} 条数据")
        print(f"   将抽取全部 {len(df)} 条数据")
        args.num = len(df)
    
    # 执行均衡抽样
    result, stats = balanced_sample(df, args.column, args.num, args.seed)
    
    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"{input_path.stem}_sampled{input_path.suffix}"
    
    # 保存结果
    result.to_csv(output_path, index=False)
    print(f"\n✅ 已保存 {len(result)} 条数据到: {output_path}")
    
    # 显示统计信息
    if args.show_stats:
        print(f"\n📈 抽样统计:")
        for value, count in sorted(stats.items(), key=lambda x: str(x[0])):
            print(f"   {value}: {count} 条")
    
    return 0


if __name__ == "__main__":
    exit(main())

