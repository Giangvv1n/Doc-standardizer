from __future__ import annotations

from typing import Generator
from docx import Document
from docx.document import Document as DocumentType
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from loguru import logger


class DocxReader:
    """Reads a .docx document and yields its block items (Paragraph or Table) in sequential document order."""

    @staticmethod
    def iter_block_items(parent: DocumentType | _Cell) -> Generator[Paragraph | Table, None, None]:
        """
        Yield each paragraph or table in the parent in document order.
        """
        if isinstance(parent, DocumentType):
            parent_elm = parent.element.body
        elif hasattr(parent, "_element"):
            parent_elm = parent._element
        else:
            raise TypeError("Parent must be Document or have _element attribute (e.g. _Cell)")

        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    def read(self, file_path: str) -> list[Paragraph | Table]:
        """Reads a docx file and returns a list of its blocks in order."""
        logger.info(f"Reading document: {file_path}")
        try:
            doc = Document(file_path)
            return list(self.iter_block_items(doc))
        except Exception as e:
            logger.error(f"Failed to read document {file_path}: {e}")
            raise
