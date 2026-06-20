"""
Semantic deduplication engine implementing VectorDeduplicatorProtocol.

Strategy: TF-IDF cosine similarity on full embedding text (primary signal)
combined with title keyword overlap (secondary signal). This captures both
near-exact copies (high TF-IDF) and same-issue-different-wording pairs
(shared title keywords). No heavy ML/torch dependencies — numpy only.

Scoring:
    combined_sim = tfidf_cosine(full_text) + keyword_boost
    keyword_boost = 0.45 if title_keyword_overlap >= 2 and tfidf >= 0.30
    threshold = 0.85 → tasks are merged into the higher-priority source.
"""

from __future__ import annotations

import re

import numpy as np

from taskpilot_ai.unified_task import UnifiedTask

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "in", "on", "at", "for",
    "to", "of", "and", "or", "but", "with", "from", "that", "this", "by",
    "be", "has", "have", "been", "will", "not", "all", "we", "our", "your",
    "my", "its", "it", "do", "re", "up", "as", "no", "due", "new", "via",
    "get", "set", "run", "per", "also", "into", "than", "then", "fix", "add",
    "out", "use", "can", "may", "would", "could", "should", "if", "when",
    "their", "they", "so", "too", "very", "just", "about", "after", "need",
    "make", "take", "update", "check", "review", "please", "ensure", "issue",
})

_PRIORITY_ORDER: dict[str, int] = {
    "jira": 0, "servicenow": 1, "email": 2, "transcript": 3
}


def _build_embedding_text(task: UnifiedTask) -> str:
    parts = [task.title]
    if task.description:
        parts.append(task.description[:500])
    if task.labels:
        parts.append(" ".join(task.labels))
    if task.business_impact:
        parts.append(task.business_impact)
    return " ".join(parts)


def _tokenize(text: str) -> list[str]:
    words = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


def _title_keywords(task: UnifiedTask) -> set[str]:
    return set(_tokenize(task.title))


def _tfidf_matrix(token_lists: list[list[str]]) -> np.ndarray:
    """Return L2-normalised TF-IDF matrix (n_docs × n_terms)."""
    vocab: dict[str, int] = {}
    for tl in token_lists:
        for w in tl:
            if w not in vocab:
                vocab[w] = len(vocab)

    n_docs = len(token_lists)
    n_terms = len(vocab)
    if n_terms == 0:
        return np.zeros((n_docs, 1), dtype=np.float32)

    tf = np.zeros((n_docs, n_terms), dtype=np.float32)
    for i, tl in enumerate(token_lists):
        if not tl:
            continue
        for w in tl:
            tf[i, vocab[w]] += 1
        tf[i] /= len(tl)

    df = np.sum(tf > 0, axis=0).astype(np.float32)
    idf = np.log((n_docs + 1) / (df + 1)) + 1.0

    tfidf = tf * idf
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (tfidf / norms).astype(np.float32)


def _canonical_priority(task: UnifiedTask) -> int:
    return _PRIORITY_ORDER.get(str(task.source), 99)


def _merge_into_canonical(canonical: UnifiedTask, duplicate: UnifiedTask) -> None:
    """Enrich canonical with useful fields from the duplicate (in-place)."""
    canonical.labels = list(dict.fromkeys(canonical.labels + duplicate.labels))

    if not canonical.business_impact and duplicate.business_impact:
        canonical.business_impact = duplicate.business_impact
    elif canonical.business_impact and duplicate.business_impact:
        canonical.business_impact = (
            canonical.business_impact + "; " + duplicate.business_impact
        )[:300]

    if canonical.deadline is None and duplicate.deadline is not None:
        canonical.deadline = duplicate.deadline

    if duplicate.blocks:
        canonical.blocks = list(dict.fromkeys(canonical.blocks + duplicate.blocks))


class TFIDFVectorDeduplicator:
    """
    Implements VectorDeduplicatorProtocol using hybrid TF-IDF + keyword signals.

    Primary signal: TF-IDF cosine similarity on full embedding text.
    Secondary signal: title keyword overlap (captures same-issue-different-wording).
    Combined score >= threshold → tasks are merged; lower-priority source is dropped.
    """

    def __init__(
        self,
        threshold: float = 0.85,
        keyword_boost: float = 0.45,
        keyword_min_overlap: int = 2,
        tfidf_min_for_boost: float = 0.30,
    ) -> None:
        self.threshold = threshold
        self.keyword_boost = keyword_boost
        self.keyword_min_overlap = keyword_min_overlap
        self.tfidf_min_for_boost = tfidf_min_for_boost

    def deduplicate(self, tasks: list[UnifiedTask]) -> list[UnifiedTask]:
        if len(tasks) < 2:
            return list(tasks)

        texts = [_build_embedding_text(t) for t in tasks]
        token_lists = [_tokenize(t) for t in texts]
        matrix = _tfidf_matrix(token_lists)

        # cosine sim: matrix is L2-normalised → sim = matrix @ matrix.T
        sim: np.ndarray = (matrix @ matrix.T).astype(np.float64)

        title_kws: list[set[str]] = [_title_keywords(t) for t in tasks]

        duplicate_of: dict[str, str] = {}

        for i in range(len(tasks)):
            if tasks[i].task_id in duplicate_of:
                continue
            for j in range(i + 1, len(tasks)):
                if tasks[j].task_id in duplicate_of:
                    continue

                tfidf_sim = float(sim[i, j])
                shared_kws = title_kws[i] & title_kws[j]
                n_shared = len(shared_kws)

                # Three merge conditions (in order of confidence):
                # 1. Near-exact text copy: high TF-IDF alone
                cond1 = tfidf_sim >= self.threshold

                # 2. Same issue, different wording: moderate TF-IDF + 2+ title keywords
                #    (catches cross-source: email vs jira about same incident)
                cond2 = tfidf_sim >= self.tfidf_min_for_boost and n_shared >= self.keyword_min_overlap

                # 3. Very similar text (high TF-IDF) + any title keyword overlap
                #    (catches security incidents described with domain synonyms)
                cond3 = tfidf_sim >= 0.50 and n_shared >= 1

                if not (cond1 or cond2 or cond3):
                    continue

                p_i = _canonical_priority(tasks[i])
                p_j = _canonical_priority(tasks[j])
                canonical, dupe = (tasks[i], tasks[j]) if p_i <= p_j else (tasks[j], tasks[i])

                dupe.duplicate_of = canonical.task_id
                duplicate_of[dupe.task_id] = canonical.task_id
                _merge_into_canonical(canonical, dupe)

        return [t for t in tasks if t.task_id not in duplicate_of]

    def similarity_matrix(self, tasks: list[UnifiedTask]) -> np.ndarray:
        """Return raw TF-IDF cosine similarity matrix — useful for QA/audit."""
        texts = [_build_embedding_text(t) for t in tasks]
        mat = _tfidf_matrix([_tokenize(t) for t in texts])
        return mat @ mat.T
