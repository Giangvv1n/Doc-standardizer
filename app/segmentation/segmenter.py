from __future__ import annotations

import re
from dataclasses import dataclass, field
from docx.table import Table
from docx.text.paragraph import Paragraph
from loguru import logger

from app.constants import (
    COMMON_HEADING_STYLES,
    HEADING_NUMBER_PATTERNS,
    MAX_HEADING_TEXT_LENGTH,
    MAX_HEADING_WORD_COUNT,
    MIN_HEADING_TEXT_LENGTH,
)


@dataclass
class DocumentSection:
    heading_text: str
    heading_level: int
    blocks: list[Paragraph | Table] = field(default_factory=list)

    def get_text(self) -> str:
        """Returns all text content from paragraphs in this section."""
        text_parts = []
        for block in self.blocks:
            if isinstance(block, Paragraph):
                if block.text.strip():
                    text_parts.append(block.text.strip())
            elif isinstance(block, Table):
                # Optionally extract table text
                table_text = []
                for row in block.rows:
                    row_text = [cell.text.strip() for cell in row.cells]
                    table_text.append(" | ".join(row_text))
                text_parts.append("\n".join(table_text))
        return "\n".join(text_parts)


class DocumentSegmenter:
    """Segments a list of document blocks into structured DocumentSection objects."""

    def __init__(self) -> None:
        self.heading_regexes = [re.compile(p) for p in HEADING_NUMBER_PATTERNS]

    def is_heading(self, paragraph: Paragraph) -> bool:
        """Determines if a paragraph is a heading based on style and heuristics."""
        text = paragraph.text.strip()
        if not text:
            return False

        # 1. Check style name
        style_name = paragraph.style.name if paragraph.style else ""
        if style_name in COMMON_HEADING_STYLES:
            return True

        # 2. Length and word count checks
        if not (MIN_HEADING_TEXT_LENGTH <= len(text) <= MAX_HEADING_TEXT_LENGTH):
            return False

        word_count = len(text.split())
        if word_count > MAX_HEADING_WORD_COUNT:
            return False

        # 3. Pattern match
        for regex in self.heading_regexes:
            if regex.match(text):
                return True

        # 4. Bold runs heuristic (short paragraph with all bold runs)
        runs = [r for r in paragraph.runs if r.text.strip()]
        if runs and all(r.bold for r in runs):
            return True

        return False

    def get_heading_level(self, paragraph: Paragraph) -> int:
        """Guesses the heading level of a heading paragraph."""
        text = paragraph.text.strip()
        style_name = paragraph.style.name if paragraph.style else ""

        if style_name == "Title":
            return 0
        if style_name == "Heading 1":
            return 1
        if style_name == "Heading 2":
            return 2
        if style_name == "Heading 3":
            return 3

        # Heuristic level estimation for custom formats
        # Count dots in digit headers (e.g. 1.2.3 -> 3 levels)
        dot_match = re.match(r"^(\d+(?:\.\d+)*)\.?", text)
        if dot_match:
            return dot_match.group(1).count(".") + 1

        # Roman numerals or alphabetic prefixes typically denote level 1
        if re.match(r"^[IVXLC]+\.\s+", text) or re.match(r"^[A-Z]\.\s+", text):
            return 1

        return 1

    def segment(self, blocks: list[Paragraph | Table]) -> list[DocumentSection]:
        """Segments block items into structured sections."""
        logger.info(f"Segmenting {len(blocks)} document blocks")
        sections: list[DocumentSection] = []
        current_section = DocumentSection(heading_text="[Khởi đầu]", heading_level=1)

        for block in blocks:
            if isinstance(block, Paragraph) and self.is_heading(block):
                # If current section has blocks, or is not the default empty one, save it
                if current_section.blocks or current_section.heading_text != "[Khởi đầu]":
                    sections.append(current_section)

                # Start new section
                current_section = DocumentSection(
                    heading_text=block.text.strip(),
                    heading_level=self.get_heading_level(block),
                )
            else:
                # Add to current section
                current_section.blocks.append(block)

        # Save last section
        if current_section.blocks or current_section.heading_text != "[Khởi đầu]":
            sections.append(current_section)

        logger.info(f"Created {len(sections)} sections from segmentation")
        return sections
