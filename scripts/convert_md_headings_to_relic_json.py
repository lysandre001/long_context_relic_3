"""
将含有 Markdown 标题（以 # 开头）的书稿拆分成 RELiC 所需 JSON。
新增：自动识别形如“LIBER I/II/…”的行作为标题（可通过 --heading-keyword 配置）。
每个标题块视为一本“书”，键名 = "<markdown文件名不含扩展名>_<标题文本>"，
值为标题下的逐行内容（默认去掉首尾空白并丢弃空行）。

示例：
python scripts/convert_md_headings_to_relic_json.py \
    --input rawdata/books/aeneid.md \
    --output data/relic_book_sentences_aeneid.json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Iterable


def normalize_lines(lines: List[str], keep_blank: bool) -> List[str]:
    """清理行：去除首尾空白，按需丢弃空行。"""
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not keep_blank and stripped == "":
            continue
        cleaned.append(stripped)
    return cleaned


def is_heading_line(line: str, keywords: Iterable[str]) -> bool:
    """判断是否为标题行：以 # 开头，或以给定关键字开头。"""
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return True
    for kw in keywords:
        if stripped.startswith(kw):
            return True
    return False


def extract_heading_text(line: str) -> str:
    """提取标题文本，去掉 # 前缀并裁剪空白。"""
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()
    return stripped.strip()


def parse_sections(text: str, stem: str, keep_blank: bool, keywords: Iterable[str]) -> Dict[str, List[str]]:
    """
    遇到标题行即开启一个新分区，累计其下的内容。
    如果整份文件没有标题，则把全量内容放到 "<stem>_default"。
    """
    sections: Dict[str, List[str]] = {}
    current_key = None
    buffer: List[str] = []

    def flush():
        if current_key is None:
            return
        sections[current_key] = normalize_lines(buffer, keep_blank)

    for raw_line in text.splitlines():
        if is_heading_line(raw_line, keywords):
            flush()
            heading_text = extract_heading_text(raw_line)
            current_key = f"{stem}_{heading_text}"
            buffer = []
        else:
            buffer.append(raw_line)

    # 收尾最后一块
    flush()

    # 如果没有任何标题，则把整体作为一个分区
    if not sections:
        sections[f"{stem}_default"] = normalize_lines(buffer, keep_blank)

    return sections


def main() -> None:
    parser = argparse.ArgumentParser(
        description="将含 # 标题的 markdown 拆分为 RELiC JSON（逐行内容）。"
    )
    parser.add_argument("--input", required=True, help="源 markdown/txt 路径")
    parser.add_argument("--output", required=True, help="输出 JSON 路径（覆盖写入）")
    parser.add_argument(
        "--keep-blank",
        action="store_true",
        help="保留空行（默认丢弃空行）。",
    )
    parser.add_argument(
        "--heading-keyword",
        action="append",
        default=["LIBER"],
        help="除 # 以外额外识别为标题行的前缀，可多次指定；默认识别 LIBER。",
    )
    args = parser.parse_args()

    src = Path(args.input)
    dst = Path(args.output)

    if not src.exists():
        raise FileNotFoundError(f"未找到输入文件: {src}")

    text = src.read_text(encoding="utf-8")
    stem = src.stem
    sections = parse_sections(
        text,
        stem=stem,
        keep_blank=args.keep_blank,
        keywords=args.heading_keyword,
    )

    # 生成 JSON
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(sections, ensure_ascii=False, indent=2), encoding="utf-8")

    # 简要日志
    total_lines = sum(len(v) for v in sections.values())
    print(
        f"写入 {dst}，分区数={len(sections)}，总行数={total_lines}，keep_blank={args.keep_blank}"
    )
    print("键名示例：", list(sections.keys())[:3])


if __name__ == "__main__":
    main()

