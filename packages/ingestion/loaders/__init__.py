"""Document loaders. MVP ships the local markdown loader for the CDC seed."""

from packages.ingestion.loaders.base import DocumentLoader, RawDocument
from packages.ingestion.loaders.local_markdown import LocalMarkdownLoader

__all__ = ["DocumentLoader", "LocalMarkdownLoader", "RawDocument"]
