"""
将注释 CSV 转换为指定评测字段格式。

输入字段（源文件列名假设与示例一致）：
- Lemma
- Comment
- Book 或 Aeneid_book
- Line
- Partial_Mask
- Full_Mask

输出字段：
- uuid: 随机 8 位数字
- book_title: Aeneid_<Book>
- commenter: 由输入文件名最后一段（去扩展名）推断
- Full_Mask_comment: 源 Full_Mask
- answer_quote_text: 源 Lemma
- answer_quote_idx: 源 Line
- num_sents: answer_quote_text 句子数（以 .?! 分割，至少 1）
- close_reading_example, explanation_human, human_eval_set: 留空

用法示例：
python scripts/convert_commentary_to_schema.py \
    --input rawdata/commentary/Aeneid_commentary_Servius.csv \
    --output data/Aeneid_commentary_Servius.csv
"""

import argparse
import csv
import random
import re
from pathlib import Path


OUTPUT_FIELDS = [
    "uuid",
    "book_title",
    "commenter",
    "Full_Mask_comment",
    "answer_quote_text",
    "answer_quote_idx",
    "num_sents",
    "close_reading_example",
    "explanation_human",
    "human_eval_set",
]


def count_sents(text: str) -> int:
    """粗略句子计数：按 . ? ! 切分，至少返回 1。"""
    if not text or not text.strip():
        return 0
    parts = [p for p in re.split(r"[.!?]+", text) if p.strip()]
    return max(1, len(parts))


def convert(input_path: Path, output_path: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"未找到输入文件: {input_path}")

    commenter = input_path.stem.split("_")[-1]

    with input_path.open() as f_in, output_path.open("w", newline="") as f_out:
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()

        for row in reader:
            book_num = row.get("Book") or row.get("Aeneid_book") or ""
            book_title = f"Aeneid_{book_num}" if book_num != "" else ""
            answer_text = row.get("Lemma", "")

            out_row = {
                "uuid": f"{random.randint(0, 99_999_999):08d}",
                "book_title": book_title,
                "commenter": commenter,
                "Full_Mask_comment": row.get("Full_Mask", ""),
                "answer_quote_text": answer_text,
                "answer_quote_idx": row.get("Line", ""),
                "num_sents": count_sents(answer_text),
                "close_reading_example": "",
                "explanation_human": "",
                "human_eval_set": "",
            }
            writer.writerow(out_row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="将注释 CSV 转为指定评测字段格式。"
    )
    parser.add_argument("--input", required=True, help="输入 CSV 路径")
    parser.add_argument("--output", required=True, help="输出 CSV 路径（覆盖写入）")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    convert(input_path, output_path)
    print(f"写出完成: {output_path}")


if __name__ == "__main__":
    main()
