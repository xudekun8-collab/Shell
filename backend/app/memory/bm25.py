"""字符二元组 BM25：只使用标准库。"""
import math
from collections import Counter

from app.memory.scoring import _TIME_WORDS, _bigrams

K1 = 1.5
B = 0.75


def strip_time_words(query: str) -> str:
    """按 scoring 的时间词表剥离显式时间词。"""
    result = query or ""
    for word, _ in _TIME_WORDS:
        result = result.replace(word, "")
    return result


def build_index(docs: list[str]) -> dict:
    """为一批文档建立词项、文档频率与平均长度索引。"""
    terms = [_bigrams(doc or "") for doc in docs]
    lengths = [len(doc_terms) for doc_terms in terms]
    doc_freq = Counter()
    for doc_terms in terms:
        doc_freq.update(doc_terms)
    return {
        "terms": terms,
        "lengths": lengths,
        "avgdl": sum(lengths) / len(lengths) if lengths else 0.0,
        "doc_freq": doc_freq,
        "count": len(docs),
    }


def score_all(query: str, index: dict) -> list[float]:
    """返回 query 对每个文档的 BM25 分数。"""
    count = index["count"]
    if count == 0:
        return []
    avgdl = index["avgdl"] or 1.0
    scores = [0.0] * count
    for term in _bigrams(query or ""):
        if not term:
            continue
        df = index["doc_freq"].get(term, 0)
        if df == 0:
            continue
        idf = math.log((count - df + 0.5) / (df + 0.5) + 1)
        for position, doc_terms in enumerate(index["terms"]):
            if term not in doc_terms:
                continue
            doc_len = index["lengths"][position]
            denominator = 1.0 + K1 * (1 - B + B * doc_len / avgdl)
            scores[position] += idf * (K1 + 1) / denominator
    return scores
