"""
retriever.py
------------
A lightweight retrieval step (classic TF-IDF + cosine similarity, from
scikit-learn) that picks the most relevant chunks of a document for a
given question. This keeps the prompt sent to the language model small
and focused, which matters a lot for large documents since the model
has a limited context window.

No extra AI model is downloaded for this step - it's pure statistics.

Adaptive retrieval logic:
  - If the best similarity score is BELOW a threshold (i.e. the query
    has few/no keywords matching the document), more chunks are returned
    so the model still has enough context for broad/global questions like
    "generate all questions" or "summarize".
  - If the document is short enough, all chunks are returned for such
    global queries so no information is lost.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# If the best chunk similarity is below this value, treat the query as
# a "global" or vague query and widen the retrieval window.
LOW_SIMILARITY_THRESHOLD = 0.10

# Max chunks to send when a global/low-similarity query is detected.
# Keeps the context within a reasonable token budget.
GLOBAL_QUERY_MAX_CHUNKS = 15


def get_relevant_chunks(
    chunks: list,
    question: str,
    top_k: int = 5,
) -> list:
    """
    Rank `chunks` by TF-IDF cosine similarity to `question`.

    Adaptive behaviour:
    - Normal query (max_similarity >= threshold): return top_k chunks
      in their original document order.
    - Vague / global query (max_similarity < threshold): return up to
      GLOBAL_QUERY_MAX_CHUNKS chunks spread across the whole document,
      so broad requests like "list all questions" still work.
    """
    if not chunks:
        return []

    # If the document is tiny, just return everything.
    if len(chunks) <= top_k:
        return chunks

    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        matrix = vectorizer.fit_transform(chunks + [question])
    except ValueError:
        # Happens when all terms are stop-words (e.g. "give me all").
        # Fall back to returning the first GLOBAL_QUERY_MAX_CHUNKS chunks.
        print(
            "[retriever] TF-IDF vectorizer failed (all stop-words?). "
            "Returning first chunks as fallback.",
            flush=True,
        )
        return chunks[:GLOBAL_QUERY_MAX_CHUNKS]

    doc_vectors = matrix[:-1]
    question_vector = matrix[-1]

    similarities = cosine_similarity(question_vector, doc_vectors)[0]
    max_sim = float(similarities.max())

    print(
        f"[retriever] max_similarity={max_sim:.3f} "
        f"(threshold={LOW_SIMILARITY_THRESHOLD}) "
        f"total_chunks={len(chunks)}",
        flush=True,
    )

    if max_sim < LOW_SIMILARITY_THRESHOLD:
        # Low-similarity / global query — spread chunks across the document
        # so the model sees a representative sample of the whole content.
        actual_k = min(GLOBAL_QUERY_MAX_CHUNKS, len(chunks))
        if actual_k == len(chunks):
            print("[retriever] Global query: returning ALL chunks.", flush=True)
            return chunks

        # Pick evenly-spaced chunks to cover the full document
        step = len(chunks) / actual_k
        indices = sorted(set(int(i * step) for i in range(actual_k)))
        print(
            f"[retriever] Global query: returning {len(indices)} "
            f"evenly-spaced chunks.",
            flush=True,
        )
        return [chunks[i] for i in indices]

    # Normal focused query — return the top_k highest-scoring chunks
    # in their original document order (better for coherent reading).
    top_indices = similarities.argsort()[::-1][:top_k]
    top_indices_sorted = sorted(top_indices)
    return [chunks[i] for i in top_indices_sorted]
