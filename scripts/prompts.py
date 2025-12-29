"""
Module: prompts
Purpose: Centralized prompt registry with versioning.
Usage: import get_prompt_template(task_type:int, version:str) to retrieve the template.
Tasks:
    - task1: with full book context (long-context)
    - task2: without book context (parametric knowledge)
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class PromptConfig:
    template: str
    description: str = ""


# fmt: off
PROMPT_REGISTRY: Dict[str, Dict[str, PromptConfig]] = {
    # Task 1: Full Context - extract text
    "task1": {
        "v1_relic_simple": PromptConfig(
            template="""\
You are provided with the full text of {book_title} and an excerpt of literary analysis that directly cites {book_title} with the cited quotation represented as <MASK>.

Your task is to carefully read the text of {book_title} and the excerpt of literary analysis, then select a window from {book_title} that most appropriately replaces <MASK> as the cited quotation by providing textual evidence for any claims in the literary analysis.

The excerpt of literary analysis should form a valid argument when <MASK> is replaced by the window from {book_title}.

<full_text_of_{book_title_snake_case}>{book_sentences}</full_text_of_{book_title_snake_case}>

<literary_analysis_excerpt>{lit_analysis_excerpt}</literary_analysis_excerpt>

Identify the window that best supports the claims being made in the excerpt of literary analysis.
The window should contain no more than 5 consecutive sentences from {book_title}.
Provide your final answer in the following format:
<window>YOUR SELECTED WINDOW</window>""",
            description="Window selection with explicit book text and simple output.",
        ),
        "v1_relic_explanation": PromptConfig(
            template="""\
You are provided with the full text of {book_title} and an excerpt of literary analysis that directly cites {book_title} with the cited quotation represented as <MASK>.

Your task is to carefully read the text of {book_title} and the excerpt of literary analysis, then select a window from {book_title} that most appropriately replaces <MASK> as the cited quotation by providing textual evidence for any claims in the literary analysis.

The excerpt of literary analysis should form a valid argument when <MASK> is replaced by the window from {book_title}.

<full_text_of_{book_title_snake_case}>{book_sentences}</full_text_of_{book_title_snake_case}>

<literary_analysis_excerpt>{lit_analysis_excerpt}</literary_analysis_excerpt>

First, provide an explanation of your decision marking process in no more than one paragraph.
Then, identify the window that best supports the claims being made in the excerpt of literary analysis. The window should contain no more than 5 consecutive sentences from {book_title}.
Provide your final answer in the following format:
<explanation>YOUR EXPLANATION</explanation>

<window>YOUR SELECTED WINDOW</window>""",
            description="Window selection with brief rationale.",
        ),
        "v1_text_simple": PromptConfig(
            template="""\
You are provided with the full text of {book_title} and an excerpt of literary analysis that directly cites {book_title} with the cited quotation represented as <MASK>.
Your task is to carefully read the text of {book_title} and the excerpt of literary analysis, then select the exact text from {book_title} that most appropriately replaces <MASK> as the cited quotation by providing textual evidence for any claims in the literary analysis.
The excerpt of literary analysis should form a valid argument when <MASK> is replaced by the window from {book_title}.
<full_text_of_{book_title_snake_case}>{book_sentences}</full_text_of_{book_title_snake_case}>
<literary_analysis_excerpt>{lit_analysis_excerpt}</literary_analysis_excerpt>
Identify the text that exactly best supports the claims being made in the excerpt of literary analysis.
Provide your final answer in the following format:
<text>YOUR SELECTED TEXT</text>""",
            description="selection with explicit book text.",
        ),
        "v1_text_simple_edited": PromptConfig(
            template="""\
You are provided with the full text of {book_title} and an excerpt of literary analysis that directly cites {book_title} with the cited quotation represented as <MASK>.
Your task is to carefully read the text of {book_title} and the excerpt of literary analysis, then select a window from {book_title} that most appropriately replaces <MASK> as the cited quotation by providing textual evidence for any claims in the literary analysis.
The excerpt of literary analysis should form a valid argument when <MASK> is replaced by the window from {book_title}.
<full_text_of_{book_title_snake_case}>{book_sentences}</full_text_of_{book_title_snake_case}>
<literary_analysis_excerpt>{lit_analysis_excerpt}</literary_analysis_excerpt>
Identify the window that best supports the claims being made in the excerpt of literary analysis.
The window should typically contain between 1 and 10 words from {book_title}.
Provide your final answer in the following format:
<window>YOUR SELECTED WINDOW</window>""",
            description="constarins in the words prediction. advice from joseph in 1210",
        ),
    },

    # Task 2: No Context (Parametric Knowledge)
    "task2": {
        "v1_text_simple": PromptConfig(
            template="""\
You are provided an excerpt of literary analysis that directly cites {book_title} with the cited quotation represented as <MASK>.
Your task is to carefully reference the text of {book_title} and the excerpt of literary analysis, then select the exact text from {book_title} that most appropriately replaces <MASK> as the cited quotation by providing textual evidence for any claims in the literary analysis.
The excerpt of literary analysis should form a valid argument when <MASK> is replaced by the window from {book_title}.
<literary_analysis_excerpt>{lit_analysis_excerpt}</literary_analysis_excerpt>
Identify the text that exactly best supports the claims being made in the excerpt of literary analysis.
Provide your final answer in the following format:
<text>YOUR SELECTED TEXT</text>""",
            description="Text selection without book context.",
        ),
    },

    # Task 3: Line Number Prediction
    "task3": {
        "v1_line_simple": PromptConfig(
            template="""\
You are provided with the full text of {book_title} (with traditional line numbers) and an excerpt of literary analysis that directly cites {book_title} with the cited quotation represented as <MASK>.
Your task is to carefully read the text of {book_title} and the excerpt of literary analysis, then identify the traditional line number(s) where the missing quotation appears in {book_title}.
<full_text_of_{book_title_snake_case}>{book_sentences_with_line_numbers}</full_text_of_{book_title_snake_case}>
<literary_analysis_excerpt>{lit_analysis_excerpt}</literary_analysis_excerpt>
Identify the traditional line number(s) that best correspond to the missing quotation in the literary analysis.
If the quotation spans multiple lines, provide the starting line number.
Provide your final answer in the following format:
<line>LINE_NUMBER</line>""",
            description="Line number prediction with traditional line numbers.",
        ),
    },

    # Task 4: Line Number Prediction without Context
    "task4": {
        "v1": PromptConfig(
            template="""\
You are provided an excerpt of literary analysis that directly cites {book_title} with the cited quotation represented as <MASK>.
Your task is to carefully reference the text of {book_title} and the excerpt of literary analysis, then identify the traditional line number(s) where the missing quotation appears in {book_title}.
<literary_analysis_excerpt>{lit_analysis_excerpt}</literary_analysis_excerpt>
Identify the traditional line number(s) that best correspond to the missing quotation in the literary analysis.
If the quotation spans multiple lines, provide the starting line number.
Provide your final answer in the following format:
<line>LINE_NUMBER</line>""",
            description="Line Number Prediction without Context",
        ),
    },
}
# fmt: on


def get_prompt_template(task_type: int, version: str) -> str:
    """
    Safe accessor for prompt templates.
    task_type: 1, 2, or 3
    version: e.g., "v1", "v2_cot"
    """
    task_key = f"task{task_type}"
    if task_key not in PROMPT_REGISTRY:
        raise ValueError(f"Invalid task type: {task_type}")
    if version not in PROMPT_REGISTRY[task_key]:
        available = list(PROMPT_REGISTRY[task_key].keys())
        raise ValueError(f"Invalid version '{version}' for {task_key}. Available: {available}")
    return PROMPT_REGISTRY[task_key][version].template
