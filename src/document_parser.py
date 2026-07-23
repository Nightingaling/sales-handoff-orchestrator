import asyncio
import pdfplumber
import docx
import aiofiles

import logging

logger = logging.getLogger(__name__)

class DocumentParser:
    """
    A class to parse different document types and return their raw text content.
    """

    def __init__(self):
        logger.info("DocumentParser.__init__: Initializing...")
        logger.info("DocumentParser.__init__: Initialization complete.")

    async def parse_pdf(self, file_path: str) -> str:
        """Parses a PDF file and returns its text content."""
        def _parse():
            try:
                with pdfplumber.open(file_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                return text
            except Exception as e:
                logger.error(f"Error parsing PDF {file_path}: {e}")
                return "" # Return empty string on error
        return await asyncio.to_thread(_parse)

    async def parse_docx(self, file_path: str) -> str:
        """Parses a DOCX file and returns its text content."""
        def _parse():
            try:
                doc = docx.Document(file_path)
                text = ""
                for para in doc.paragraphs:
                    text += para.text + "\n"
                return text
            except Exception as e:
                logger.error(f"Error parsing DOCX {file_path}: {e}")
                return "" # Return empty string on error
        return await asyncio.to_thread(_parse)

    async def parse_txt(self, file_path: str) -> str:
        """Parses a text file."""
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Error parsing TXT {file_path}: {e}")
            return "" # Return empty string on error

    async def parse_document(self, file_path: str) -> str:
        """
        Parses a document and extracts its raw text content.
        """
        logger.info(f"Parsing document: {file_path}")
        if file_path.endswith(".pdf"):
            text = await self.parse_pdf(file_path)
        elif file_path.endswith(".docx"):
            text = await self.parse_docx(file_path)
        elif file_path.endswith(".txt"):
            text = await self.parse_txt(file_path)
        else:
            logger.warning(f"Unsupported file type: {file_path}. Skipping.")
            text = ""
        
        logger.info(f"Successfully parsed {file_path}." if text else f"Could not extract text from {file_path}.")
        return text
