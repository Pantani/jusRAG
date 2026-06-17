"""Storage layer: vector store, relational adapter and repositories.

Implementations honor the ``VectorStore`` Protocol (§28) and must not know about
FastAPI or the LLM — they return plain objects carrying score + metadata.
"""
