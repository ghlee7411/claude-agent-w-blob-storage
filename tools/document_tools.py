"""Document parsing tools for ingesting external documents.

This module provides tools for reading and parsing various document formats
(.txt, .html, .md) for ingestion into the knowledge base.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ParsedDocument:
    """Represents a parsed document."""
    source_path: str
    title: str
    content: str
    format: str
    size: int
    sections: List[Dict[str, str]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "title": self.title,
            "content": self.content,
            "format": self.format,
            "size": self.size,
            "sections": self.sections
        }


class DocumentTools:
    """Tools for parsing and processing documents."""

    SUPPORTED_FORMATS = {".txt", ".html", ".htm", ".md", ".markdown"}

    def __init__(self):
        """Initialize document tools."""
        pass

    def is_supported(self, file_path: str) -> bool:
        """Check if file format is supported.

        Args:
            file_path: Path to the file

        Returns:
            True if supported
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_FORMATS

    async def parse_document(self, file_path: str) -> Dict[str, Any]:
        """Parse a document file.

        Args:
            file_path: Path to the document

        Returns:
            Dict with parsed content and metadata
        """
        path = Path(file_path)

        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        if not self.is_supported(file_path):
            return {
                "success": False,
                "error": f"Unsupported format: {path.suffix}"
            }

        try:
            content = path.read_text(encoding="utf-8")
            ext = path.suffix.lower()

            if ext in {".html", ".htm"}:
                parsed = self._parse_html(content, file_path)
            elif ext in {".md", ".markdown"}:
                parsed = self._parse_markdown(content, file_path)
            else:  # .txt
                parsed = self._parse_text(content, file_path)

            return {
                "success": True,
                "document": parsed.to_dict()
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Parse error: {str(e)}"
            }

    def _parse_text(self, content: str, source_path: str) -> ParsedDocument:
        """Parse plain text document."""
        lines = content.strip().split("\n")

        # Try to extract title from first non-empty line
        title = Path(source_path).stem
        for line in lines:
            if line.strip():
                # Use first line as title if it looks like a title
                if len(line.strip()) < 100 and not line.strip().endswith("."):
                    title = line.strip()
                break

        # Split into sections by double newlines
        sections = self._split_into_sections(content)

        return ParsedDocument(
            source_path=source_path,
            title=title,
            content=content,
            format="text",
            size=len(content),
            sections=sections
        )

    def _parse_markdown(self, content: str, source_path: str) -> ParsedDocument:
        """Parse markdown document."""
        lines = content.strip().split("\n")

        # Extract title from first heading
        title = Path(source_path).stem
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Extract sections by headers
        sections = []
        current_section = {"heading": "", "content": []}

        for line in lines:
            if line.startswith("#"):
                if current_section["content"]:
                    sections.append({
                        "heading": current_section["heading"],
                        "content": "\n".join(current_section["content"]).strip()
                    })
                current_section = {
                    "heading": line.lstrip("#").strip(),
                    "content": []
                }
            else:
                current_section["content"].append(line)

        # Add last section
        if current_section["content"]:
            sections.append({
                "heading": current_section["heading"],
                "content": "\n".join(current_section["content"]).strip()
            })

        return ParsedDocument(
            source_path=source_path,
            title=title,
            content=content,
            format="markdown",
            size=len(content),
            sections=sections
        )

    def _parse_html(self, content: str, source_path: str) -> ParsedDocument:
        """Parse HTML document (basic parsing without external deps)."""
        # Extract title
        title = Path(source_path).stem
        title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = self._strip_tags(title_match.group(1)).strip()

        # Remove script and style tags
        content_cleaned = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.IGNORECASE | re.DOTALL)
        content_cleaned = re.sub(r"<style[^>]*>.*?</style>", "", content_cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Extract text content
        text_content = self._strip_tags(content_cleaned)
        text_content = re.sub(r"\n\s*\n", "\n\n", text_content)  # Normalize whitespace
        text_content = text_content.strip()

        # Extract sections by headers
        sections = []
        header_pattern = r"<h([1-6])[^>]*>(.*?)</h\1>"
        headers = list(re.finditer(header_pattern, content_cleaned, re.IGNORECASE | re.DOTALL))

        if headers:
            for i, match in enumerate(headers):
                heading = self._strip_tags(match.group(2)).strip()
                start = match.end()
                end = headers[i + 1].start() if i + 1 < len(headers) else len(content_cleaned)
                section_content = self._strip_tags(content_cleaned[start:end]).strip()

                if section_content:
                    sections.append({
                        "heading": heading,
                        "content": section_content[:1000]  # Limit section size
                    })
        else:
            # No headers, treat as single section
            sections = self._split_into_sections(text_content)

        return ParsedDocument(
            source_path=source_path,
            title=title,
            content=text_content,
            format="html",
            size=len(text_content),
            sections=sections
        )

    def _strip_tags(self, html: str) -> str:
        """Remove HTML tags from string."""
        # Replace common tags with appropriate whitespace
        html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<p[^>]*>", "\n\n", html, flags=re.IGNORECASE)
        html = re.sub(r"</p>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<li[^>]*>", "\n• ", html, flags=re.IGNORECASE)
        html = re.sub(r"<[^>]+>", " ", html)
        # Decode common entities
        html = html.replace("&nbsp;", " ")
        html = html.replace("&amp;", "&")
        html = html.replace("&lt;", "<")
        html = html.replace("&gt;", ">")
        html = html.replace("&quot;", '"')
        html = html.replace("&#39;", "'")
        return html

    def _split_into_sections(self, content: str) -> List[Dict[str, str]]:
        """Split content into sections by paragraphs."""
        paragraphs = content.split("\n\n")
        sections = []

        for para in paragraphs:
            para = para.strip()
            if para and len(para) > 20:  # Skip very short paragraphs
                sections.append({
                    "heading": "",
                    "content": para[:1000]  # Limit section size
                })

        return sections[:20]  # Limit number of sections

    async def extract_keywords(self, content: str, max_keywords: int = 10) -> List[str]:
        """Extract potential keywords from content.

        This is a simple extraction - in production, Claude Agent
        would do more sophisticated analysis.

        Args:
            content: Text content
            max_keywords: Maximum keywords to extract

        Returns:
            List of potential keywords
        """
        # Remove common words and extract potential keywords
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "of", "to", "in", "for", "on", "with", "at", "by",
            "from", "as", "into", "through", "during", "before", "after",
            "above", "below", "between", "under", "again", "further",
            "then", "once", "here", "there", "when", "where", "why",
            "how", "all", "each", "few", "more", "most", "other", "some",
            "such", "no", "nor", "not", "only", "own", "same", "so",
            "than", "too", "very", "just", "and", "but", "if", "or",
            "because", "until", "while", "this", "that", "these", "those",
            "it", "its", "they", "them", "their", "what", "which", "who"
        }

        # Extract words
        words = re.findall(r"\b[a-zA-Z가-힣]{3,}\b", content.lower())

        # Count frequencies
        word_freq = {}
        for word in words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Sort by frequency and return top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:max_keywords]]

    async def summarize_for_comparison(self, content: str, max_length: int = 500) -> str:
        """Create a brief summary for comparison with existing topics.

        Args:
            content: Full content
            max_length: Maximum summary length

        Returns:
            Summary string
        """
        # Take first paragraphs up to max_length
        paragraphs = content.split("\n\n")
        summary = []
        length = 0

        for para in paragraphs:
            para = para.strip()
            if para:
                if length + len(para) <= max_length:
                    summary.append(para)
                    length += len(para)
                else:
                    remaining = max_length - length
                    if remaining > 50:
                        summary.append(para[:remaining] + "...")
                    break

        return "\n\n".join(summary)
