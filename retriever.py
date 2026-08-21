"""
retriever.py
------------
A lightweight retrieval step (classic TF-IDF + cosine similarity, from
scikit-learn) that picks the most relevant chunks of a document for a
given question. This keeps the prompt sent to the language model small
and focused, which matters a lot for large documents since the model
has a limited context window.

No extra AI model is downloaded for this step - it's pure statistics.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def get_relevant_chunks(chunks, question: str, top_k: int = 3):
    """
    Rank `chunks` (list[str]) by similarity to `question` and return the
    top_k most relevant ones, in their original order of appearance.
    """
    if not chunks:
        return []

    if len(chunks) <= top_k:
        return chunks

    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(chunks + [question])

    doc_vectors = matrix[:-1]
    question_vector = matrix[-1]

    similarities = cosine_similarity(question_vector, doc_vectors)[0]

    # Get indices of the top_k highest-scoring chunks
    top_indices = similarities.argsort()[::-1][:top_k]
    top_indices_sorted = sorted(top_indices)  # preserve original order

    return [chunks[i] for i in top_indices_sorted]
