"""Legal document ingestion: loaders, normalizer, structural chunker, versioning.

Turns raw legal documents into citable, versioned `LegalChunk`s. The boundary
with the indexer is the JSONL file — this package never touches embeddings or
the vector store (Prompt Master §12.3, §12.9).
"""
