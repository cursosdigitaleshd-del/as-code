"""
AS Code — Adaptive Semantic Chunker Service

Routes each file to the correct chunking strategy:

  .py         → AST chunker          (function / class boundaries)
  .md .rst    → Markdown chunker     (heading hierarchy, fallback to adaptive)
  .js .ts .go → Generic code chunker (regex function boundaries)
  .pdf        → Adaptive semantic    (paragraph → sentence → char)
  .txt .docx  → Adaptive semantic    (paragraph → sentence → char)
  fallback    → Adaptive semantic    (paragraph → sentence → char)

Key design principle:
  The adaptive semantic chunker is STRUCTURE-AGNOSTIC.
  It requires no headings, no fixed formatting, no specific language.
  It naturally respects paragraph breaks → sentence breaks → character slicing,
  degrading gracefully on OCR output, messy Word exports, contracts, and notes.

Every chunk carries symbolic metadata (symbol, file, section, line_start, ...)
ready for future VS Code / Code Graph integration.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".cpp", ".c", ".cs",
    ".java", ".rb", ".php",
}
_MARKDOWN_EXTENSIONS = {".md", ".mdx", ".rst"}


# ── Data class ─────────────────────────────────────────────────


@dataclass
class Chunk:
    """A single document chunk with full symbolic metadata."""

    text: str
    section_name: str = "Document"
    chunk_type: str = "text"           # text | code | markdown_section
    metadata: dict = field(default_factory=dict)
    # metadata keys (populated where available):
    #   symbol, symbol_type, file, section,
    #   line_start, line_end, language, page, block


# ── Service ────────────────────────────────────────────────────


class ChunkerService:
    """
    Hybrid chunker — strategy selected per file type.

    char_per_token approximation: 4 chars ≈ 1 token.
    """

    _CHARS_PER_TOKEN = 4

    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    # ── Public entry point ─────────────────────────────────────

    def chunk(self, text: str, filename: str, file_type: str) -> List[Chunk]:
        """
        Chunk text using the strategy appropriate for file_type.

        Args:
            text:      Full extracted text.
            filename:  Original filename (used in metadata).
            file_type: Extension without dot, e.g. "py", "md", "pdf".
        """
        ext = f".{file_type.lower().lstrip('.')}"

        if ext in _MARKDOWN_EXTENSIONS:
            return self._chunk_markdown(text, filename)
        elif ext == ".py":
            return self._chunk_python(text, filename)
        elif ext in _CODE_EXTENSIONS:
            lang = ext.lstrip(".")
            return self._chunk_code_generic(text, filename, language=lang)
        else:
            # pdf, txt, docx, and all unknown formats → adaptive semantic chunker
            # Structure-agnostic: respects paragraph → sentence → char boundaries.
            return self._chunk_adaptive_semantic(text, filename)

    # ── Markdown chunker ───────────────────────────────────────

    def _chunk_markdown(self, text: str, filename: str) -> List[Chunk]:
        """Split by ATX headings (# … ######)."""
        heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        matches = list(heading_re.finditer(text))

        if not matches:
            return self._chunk_fixed(
                text, filename, section="Full Document",
                chunk_type="markdown_section",
            )

        chunks: List[Chunk] = []

        # Text before first heading
        intro = text[: matches[0].start()].strip()
        if intro:
            chunks.append(
                Chunk(
                    text=intro,
                    section_name="Introduction",
                    chunk_type="markdown_section",
                    metadata={"file": filename, "section": "Introduction"},
                )
            )

        for i, m in enumerate(matches):
            level = len(m.group(1))
            heading = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()

            if not body:
                continue

            meta = {"file": filename, "section": heading, "heading_level": level}

            if len(body) > self._max_chars():
                chunks.extend(
                    self._chunk_fixed(
                        body, filename,
                        section=heading,
                        chunk_type="markdown_section",
                        extra_meta=meta,
                    )
                )
            else:
                chunks.append(
                    Chunk(
                        text=body,
                        section_name=heading,
                        chunk_type="markdown_section",
                        metadata=meta,
                    )
                )

        return chunks

    # ── Python AST chunker ─────────────────────────────────────

    def _chunk_python(self, text: str, filename: str) -> List[Chunk]:
        """Split Python source by top-level function / class definitions via AST."""
        try:
            tree = ast.parse(text)
        except SyntaxError:
            logger.warning(f"AST parse failed for {filename}; falling back to fixed chunker")
            return self._chunk_fixed(text, filename, chunk_type="code")

        lines = text.splitlines(keepends=True)
        chunks: List[Chunk] = []
        covered: set[int] = set()

        # Only top-level definitions (children of Module)
        for node in ast.iter_child_nodes(tree):
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue

            start_line = node.lineno - 1          # 0-indexed
            end_line = node.end_lineno             # inclusive, 1-indexed
            body = "".join(lines[start_line:end_line]).strip()
            if not body:
                continue

            symbol_type = (
                "class" if isinstance(node, ast.ClassDef) else "function"
            )
            for ln in range(start_line, end_line):
                covered.add(ln)

            chunks.append(
                Chunk(
                    text=body,
                    section_name=node.name,
                    chunk_type="code",
                    metadata={
                        "symbol": node.name,
                        "symbol_type": symbol_type,
                        "file": filename,
                        "line_start": node.lineno,
                        "line_end": node.end_lineno,
                        "language": "python",
                    },
                )
            )

        # Module-level code not inside any def/class
        module_lines = [
            line for i, line in enumerate(lines) if i not in covered
        ]
        module_text = "".join(module_lines).strip()
        if module_text:
            chunks.append(
                Chunk(
                    text=module_text,
                    section_name="Module Level",
                    chunk_type="code",
                    metadata={"file": filename, "section": "Module Level", "language": "python"},
                )
            )

        return chunks or self._chunk_fixed(text, filename, chunk_type="code")

    # ── Generic code chunker ───────────────────────────────────

    def _chunk_code_generic(
        self, text: str, filename: str, language: str = "unknown"
    ) -> List[Chunk]:
        """Regex-based function/class splitter for non-Python code."""
        # Matches JS/TS/Go/etc. function and class declarations
        pattern = re.compile(
            r"(?:^|\n)(?:export\s+)?(?:async\s+)?"
            r"(?:function\s+(\w+)|class\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?"
            r"(?:\([^)]*\)\s*=>|\bfunction\b))",
            re.MULTILINE,
        )
        matches = list(pattern.finditer(text))

        if not matches:
            return self._chunk_fixed(text, filename, chunk_type="code")

        chunks: List[Chunk] = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if not body:
                continue

            symbol = next(g for g in m.groups() if g) if any(m.groups()) else f"block_{i}"
            chunks.append(
                Chunk(
                    text=body,
                    section_name=symbol,
                    chunk_type="code",
                    metadata={"symbol": symbol, "file": filename, "language": language},
                )
            )

        return chunks

    # ── Adaptive semantic chunker (pdf / txt / docx / fallback) ─

    def _chunk_adaptive_semantic(
        self,
        text: str,
        filename: str,
        section: str = "Document",
        chunk_type: str = "text",
        extra_meta: Optional[dict] = None,
    ) -> List[Chunk]:
        """
        Structure-agnostic adaptive chunker.

        Works on OCR output, messy PDFs, plain notes, Word exports, contracts
        and any document that lacks clean headings or fixed formatting.

        Algorithm (priority order):
          1. Split text into paragraphs on double newlines (\n\n).
          2. Coalesce consecutive paragraphs until the character budget is full.
          3. If a single paragraph exceeds the budget, split it into sentences
             (on .  ?  !  boundaries) and coalesce sentences instead.
          4. If a single sentence still exceeds the budget, slice by characters
             with overlap (last resort — preserves at least some context).

        No headings, no regex structure, no language assumptions required.
        """
        max_chars = self._max_chars()
        overlap_chars = self.chunk_overlap * self._CHARS_PER_TOKEN

        chunks: List[Chunk] = []
        block_idx = 0

        def _emit(content: str) -> None:
            nonlocal block_idx
            content = content.strip()
            if not content:
                return
            label = f"Block {block_idx}" if section == "Document" else f"{section} · {block_idx}"
            meta: dict = {"file": filename, "block_index": block_idx}
            if extra_meta:
                meta.update(extra_meta)
            chunks.append(
                Chunk(
                    text=content,
                    section_name=label,
                    chunk_type=chunk_type,
                    metadata=meta,
                )
            )
            block_idx += 1

        def _coalesce_into_chunks(units: List[str], separator: str) -> None:
            """
            Greedily coalesce units (paragraphs or sentences) into chunks.
            Each chunk is as large as possible without exceeding max_chars.
            """
            current_parts: List[str] = []
            current_len = 0

            for unit in units:
                unit_len = len(unit)
                sep_len = len(separator) if current_parts else 0

                if current_len + sep_len + unit_len <= max_chars:
                    current_parts.append(unit)
                    current_len += sep_len + unit_len
                else:
                    if current_parts:
                        _emit(separator.join(current_parts))
                    # Unit itself exceeds budget — must slice by character
                    if unit_len > max_chars:
                        _slice_by_chars(unit)
                        current_parts = []
                        current_len = 0
                    else:
                        current_parts = [unit]
                        current_len = unit_len

            if current_parts:
                _emit(separator.join(current_parts))

        def _slice_by_chars(text_block: str) -> None:
            """Last-resort: slice long text by raw characters with overlap."""
            i = 0
            while i < len(text_block):
                slice_text = text_block[i : i + max_chars].strip()
                if slice_text:
                    _emit(slice_text)
                i += max_chars - overlap_chars

        # ── Step 1: paragraph split ───────────────────────────
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        if not paragraphs:
            return []

        # ── Step 2 & 3: coalesce paragraphs; fall to sentences if needed ──
        current_para_parts: List[str] = []
        current_para_len = 0

        for para in paragraphs:
            para_len = len(para)
            sep_len = 2 if current_para_parts else 0  # "\n\n"

            if current_para_len + sep_len + para_len <= max_chars:
                # Fits: accumulate
                current_para_parts.append(para)
                current_para_len += sep_len + para_len
            else:
                # Emit what we have
                if current_para_parts:
                    _emit("\n\n".join(current_para_parts))
                    current_para_parts = []
                    current_para_len = 0

                if para_len <= max_chars:
                    # Single paragraph fits a fresh chunk — start a new block
                    current_para_parts = [para]
                    current_para_len = para_len
                else:
                    # Paragraph is too large — split into sentences
                    sentences = [
                        s.strip()
                        for s in re.split(r"(?<=[.!?])\s+", para)
                        if s.strip()
                    ]
                    if len(sentences) > 1:
                        _coalesce_into_chunks(sentences, " ")
                    else:
                        # No sentence boundary found — slice by character
                        _slice_by_chars(para)

        if current_para_parts:
            _emit("\n\n".join(current_para_parts))

        return chunks or self._chunk_fixed(text, filename)

    # ── Fixed-size character slicer (internal leaf fallback) ───

    def _chunk_fixed(
        self,
        text: str,
        filename: str,
        section: str = "Document",
        chunk_type: str = "text",
        extra_meta: Optional[dict] = None,
    ) -> List[Chunk]:
        """
        Pure character-based slicer with overlap.

        This is an internal leaf used only by:
          - _chunk_markdown (when a heading's body block overflows)
          - _chunk_adaptive_semantic (as last-resort for sentences with no punctuation)

        It is NOT a public routing target — all external file types are handled
        by the adaptive semantic chunker or the code/AST chunkers.
        """
        char_size = self._max_chars()
        char_overlap = self.chunk_overlap * self._CHARS_PER_TOKEN

        chunks: List[Chunk] = []
        i = 0
        idx = 0

        while i < len(text):
            body = text[i : i + char_size].strip()
            if body:
                meta = {"file": filename, "chunk_index": idx}
                if extra_meta:
                    meta.update(extra_meta)
                chunks.append(
                    Chunk(
                        text=body,
                        section_name=section,
                        chunk_type=chunk_type,
                        metadata=meta,
                    )
                )
                idx += 1
            i += char_size - char_overlap

        return chunks

    def _max_chars(self) -> int:
        return self.chunk_size * self._CHARS_PER_TOKEN


# ── Singleton ──────────────────────────────────────────────────

_chunker: Optional[ChunkerService] = None


def get_chunker(chunk_size: int = 300, chunk_overlap: int = 50) -> ChunkerService:
    """Return the global ChunkerService singleton."""
    global _chunker
    if _chunker is None:
        _chunker = ChunkerService(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return _chunker
