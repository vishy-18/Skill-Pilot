"""Deterministic citation & quote provenance verification.

Adheres strictly to Principle 4 (docs/ARCHITECTURE.md:175):
- Checks in plain Python code that the quote claimed by the model exists
  verbatim (whitespace-normalised) within the retrieved source text.
- If verification fails or the quote was hallucinated, the requirement is DEMOTED
  to 'Excluded' or 'Unverified' with a specific failure note.
- Never drops a failed citation silently; keeps the audit trail visible.
- Untrusted text is treated strictly as data, neutralizing prompt injections.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

try:
    from slice.retrieve import Chunk
except ImportError:
    @dataclass(frozen=True)
    class Chunk:  # type: ignore
        chunk_id: str
        doc: str
        ordinal: int
        text: str
        distance: float = 0.0

        def cite(self) -> str:
            return f"{self.doc}#{self.ordinal}"

from .schema import ExtractedRequirement


def _normalize(text: str) -> str:
    """Normalize whitespace and lowercase for reliable substring comparison."""
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_requirement(
    req: ExtractedRequirement,
    document_text: str,
    chunks: Sequence[Chunk] | None = None,
) -> ExtractedRequirement:
    """Verify an extracted requirement against the source document or chunk set.

    Runs in pure deterministic Python. Never asks the model anything.
    """
    if not req.source_quote or not req.source_quote.strip():
        req.verification_status = "Excluded"
        req.verification_note = "Demoted: no source quote provided by model"
        return req

    norm_quote = _normalize(req.source_quote)
    norm_doc = _normalize(document_text)

    # 1. Verbatim quote presence in full document
    quote_in_doc = norm_quote in norm_doc

    # 2. Check chunk provenance if chunks were provided from RAG search
    quote_in_chunk = True
    if chunks:
        # Check if the citation matches one of the chunks and the quote appears in it
        matching_chunk = any(
            norm_quote in _normalize(c.text)
            for c in chunks
            if not req.citation or req.citation == c.cite() or c.doc in req.citation
        )
        quote_in_chunk = matching_chunk

    if quote_in_doc and quote_in_chunk:
        req.verification_status = "Verified"
        req.verification_note = "Quote verified verbatim in source evidence"
    elif quote_in_doc and not quote_in_chunk:
        req.verification_status = "Unverified"
        req.verification_note = "Demoted: quote found in raw doc but not in retrieved RAG chunks"
    else:
        req.verification_status = "Excluded"
        req.verification_note = f"Demoted: quote '{req.source_quote[:40]}...' does not appear verbatim in source document"

    return req


def verify_batch(
    requirements: list[ExtractedRequirement],
    document_text: str,
    chunks: Sequence[Chunk] | None = None,
) -> list[ExtractedRequirement]:
    """Verify an entire batch of requirements deterministically."""
    return [verify_requirement(r, document_text, chunks) for r in requirements]
