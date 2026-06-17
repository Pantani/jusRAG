"""Shared typed vocabulary for the jus-rag-brasil legal domain (§8, §12.2)."""

from packages.legal_types.enums import (
    DocType,
    Jurisdiction,
    LegalArea,
    NormType,
    PrecedentType,
    Source,
    SupportLevel,
)
from packages.legal_types.schemas import (
    CaseLawDocument,
    LegalChunk,
    LegalCitation,
    LegalDocument,
    SourceMetadata,
)

__all__ = [
    "CaseLawDocument",
    "DocType",
    "Jurisdiction",
    "LegalArea",
    "LegalChunk",
    "LegalCitation",
    "LegalDocument",
    "NormType",
    "PrecedentType",
    "Source",
    "SourceMetadata",
    "SupportLevel",
]
