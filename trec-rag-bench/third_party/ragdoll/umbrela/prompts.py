from __future__ import annotations

import re

UMBRELA_ZERO_BASIC = """You are an expert judge of a content. Using your internal knowledge and simple commonsense reasoning, try to verify if the passage is relevance category to the query.
Here, "0" represent that the passage has nothing to do with the query, "1" represents that the passage seems related to the query but does not answer it, "2" represents that the passage has some answer for the query, but the answer may be a bit unclear, or hidden amongst extraneous information and "3" represents that the passage is dedicated to the query and contains the exact answer.

Provide explanation for the relevance and give your answer with from one of the categories 0, 1, 2 or 3 only. One of the categorical values if compulsory in answer.

Instructions: Think about the question. After explaining your reasoning, provide your answer in terms of 0, 1, 2 or 3 category. Only provide the relevance category on the last line. Do not provide any further details on the last line.

###

Query: {query}
Passage: {passage}

Explanation:"""


UMBRELA_ZERO_BING = """Given a query and a passage, you must provide a score on an integer scale of 0 to 3 with the following meanings:
0 = represent that the passage has nothing to do with the query, 
1 = represents that the passage seems related to the query but does not answer it, 
2 = represents that the passage has some answer for the query, but the answer may be a bit unclear, or hidden amongst extraneous information and 
3 = represents that the passage is dedicated to the query and contains the exact answer.

Important Instruction: Assign category 1 if the passage is somewhat related to the topic but not completely, category 2 if passage presents something very important related to the entire topic but also has some extra information and category 3 if the passage only and entirely refers to the topic. If none of the above satisfies give it category 0.

Query: {query}
Passage: {passage}

Split this problem into steps:
Consider the underlying intent of the search.
Measure how well the content matches a likely intent of the query (M).
Measure how trustworthy the passage is (T).
Consider the aspects above and the relative importance of each, and decide on a final score (O). Final score must be an integer value only.
Do not provide any code in result. Provide each score in the format of: ##final score: score without providing any reasoning."""


def render_umbrela_prompt(*, query: str, passage: str, prompt_type: str) -> str:
    if prompt_type == "basic":
        return UMBRELA_ZERO_BASIC.format(query=query, passage=passage)
    if prompt_type == "bing":
        return UMBRELA_ZERO_BING.format(query=query, passage=passage)
    raise ValueError(f"unsupported UMBRELA prompt type: {prompt_type}")


def parse_umbrela_judgment(text: str) -> int | None:
    patterns = [
        r"##\s*final score\s*:\s*([0-3])",
        r"final score\s*:\s*([0-3])",
        r"relevance category\s*[:-=]?\s*([0-3])",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            return int(matches[-1])
    stripped = text.strip()
    if stripped and stripped[-1] in "0123":
        return int(stripped[-1])
    return None
