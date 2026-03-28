"""
knowledge_base.py - Simple RAG Knowledge Base Module

Provides keyword-based document retrieval from plain text files.
Designed as a drop-in module that can be upgraded to vector DB
(e.g., ChromaDB, FAISS, Pinecone) without changing the public API.

Usage:
    kb = KnowledgeBase("/path/to/knowledge")
    context = kb.retrieve("shipping return policy", top_k=3)
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Document:
    """A single knowledge base document."""
    filename: str
    content: str
    keywords: set = field(default_factory=set)

    def __post_init__(self):
        # Extract keywords: lowercase words with 3+ chars, stripped of punctuation
        words = re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", self.content.lower())
        self.keywords = set(words)


class KnowledgeBase:
    """
    Simple keyword-based knowledge retrieval system.

    Loads .txt and .md files from a directory, scores them against
    a query using keyword overlap, and returns formatted context
    suitable for LLM prompt injection.

    To upgrade to vector DB later:
      1. Replace `_score()` with embedding similarity
      2. Replace `documents` list with vector store
      3. Keep `retrieve()` and `format_context()` signatures unchanged
    """

    def __init__(self, knowledge_dir: str = "knowledge"):
        self.knowledge_dir = Path(knowledge_dir)
        self.documents: list[Document] = []
        self._load_documents()

    def _load_documents(self) -> None:
        """Load all .txt and .md files from the knowledge directory."""
        if not self.knowledge_dir.exists():
            return

        extensions = {".txt", ".md"}
        for filepath in sorted(self.knowledge_dir.iterdir()):
            if filepath.suffix.lower() in extensions and filepath.is_file():
                try:
                    content = filepath.read_text(encoding="utf-8").strip()
                    if content:
                        self.documents.append(
                            Document(filename=filepath.name, content=content)
                        )
                except Exception:
                    # Skip unreadable files silently in production
                    pass

    def reload(self) -> None:
        """Reload all documents from disk. Call after adding new files."""
        self.documents.clear()
        self._load_documents()

    def _score(self, query: str, document: Document) -> float:
        """
        Score a document against a query using keyword overlap.

        Returns a float between 0 and 1 representing relevance.
        This is the function to replace when upgrading to embeddings.
        """
        query_keywords = set(
            re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", query.lower())
        )
        if not query_keywords:
            return 0.0

        overlap = query_keywords & document.keywords
        # Weighted: more overlap = higher score, normalized by query size
        return len(overlap) / len(query_keywords)

    def retrieve(self, query: str, top_k: int = 3) -> list[Document]:
        """
        Retrieve the top-k most relevant documents for a query.

        Args:
            query: The user's question or search terms.
            top_k: Maximum number of documents to return.

        Returns:
            List of Document objects sorted by relevance (descending).
        """
        if not self.documents or not query.strip():
            return []

        scored = [(doc, self._score(query, doc)) for doc in self.documents]
        # Filter out zero-score documents, sort by score descending
        scored = [(doc, s) for doc, s in scored if s > 0]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in scored[:top_k]]

    def format_context(
        self, documents: list[Document], max_chars: int = 3000
    ) -> Optional[str]:
        """
        Format retrieved documents into a context string for LLM injection.

        Args:
            documents: List of retrieved Document objects.
            max_chars: Maximum total character length of the context block.

        Returns:
            Formatted context string, or None if no documents provided.
        """
        if not documents:
            return None

        parts = []
        total = 0
        for doc in documents:
            header = f"[{doc.filename}]"
            # Truncate individual document if needed
            remaining = max_chars - total - len(header) - 4  # account for newlines
            if remaining <= 0:
                break
            snippet = doc.content[:remaining]
            parts.append(f"{header}\n{snippet}")
            total += len(header) + len(snippet) + 2

        return "\n\n".join(parts)

    @property
    def document_count(self) -> int:
        return len(self.documents)
