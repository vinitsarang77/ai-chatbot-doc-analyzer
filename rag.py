import os
import re
import faiss
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class RAGPipeline:
    def __init__(self, chunk_size: int = 450, overlap: int = 80):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 1))
        self.index = None
        self.chunks = []

    def chunk_text(self, text: str) -> list[str]:
        """Split text into chunks while preserving paragraph boundaries."""
        cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not cleaned:
            return []

        paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
        chunks = []


        for para in paragraphs:
            if len(para) <= self.chunk_size:
                chunks.append(para)
            else:

                # Sliding window for very long single paragraphs
                start = 0
                while start < len(para):
                    end = start + self.chunk_size
                    chunks.append(para[start:end].strip())
                    start += self.chunk_size - self.overlap

        return chunks

    def build_index(self, text: str) -> int:
        """Chunk text, generate L2-normalized TF-IDF vectors, and store in a FAISS index."""
        self.chunks = self.chunk_text(text)
        if not self.chunks:
            self.index = None
            return 0

        tfidf_matrix = self.vectorizer.fit_transform(self.chunks)
        embeddings = tfidf_matrix.toarray().astype("float32")

        # L2-normalize so Inner Product == Cosine Similarity
        faiss.normalize_L2(embeddings)

        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings)
        return len(self.chunks)

    def retrieve(self, query: str, top_k: int = 3, min_score: float = 0.15) -> list[str]:
        """Embed query and retrieve top-k relevant chunks from FAISS."""
        if not self.index or not self.chunks or not query.strip():
            return []

        query_vec = self.vectorizer.transform([query]).toarray().astype("float32")
        faiss.normalize_L2(query_vec)

        k = min(top_k, len(self.chunks))
        scores, indices = self.index.search(query_vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and score >= min_score:
                results.append(self.chunks[idx])

        return results


def load_knowledge_base(filepath: str = "knowledge.txt") -> RAGPipeline:
    """Initialize global chatbot RAG pipeline from a local knowledge file."""
    rag = RAGPipeline(chunk_size=450, overlap=80)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            rag.build_index(f.read())
    return rag