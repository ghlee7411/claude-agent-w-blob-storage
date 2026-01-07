"""Filesystem storage implementation.

This module provides a filesystem-based storage backend
that can later be swapped for blob storage.
"""

import os
import hashlib
import fnmatch
from pathlib import Path
from typing import Optional
from datetime import datetime

from .base import BaseStorage, StorageResult


class FileSystemStorage(BaseStorage):
    """Filesystem-based storage implementation.

    Uses file modification time and content hash as ETag
    for optimistic concurrency control.
    """

    def __init__(self, base_path: str = "./knowledge_base"):
        """Initialize filesystem storage.

        Args:
            base_path: Root directory for storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_full_path(self, path: str) -> Path:
        """Get full path from relative path."""
        return self.base_path / path

    def _compute_etag(self, path: Path) -> str:
        """Compute ETag from file content and mtime."""
        if not path.exists():
            return ""

        stat = path.stat()
        content_hash = hashlib.md5(path.read_bytes()).hexdigest()[:8]
        return f"{int(stat.st_mtime)}-{content_hash}"

    async def read(self, path: str) -> StorageResult:
        """Read content from filesystem."""
        full_path = self._get_full_path(path)

        if not full_path.exists():
            return StorageResult(
                success=False,
                error=f"File not found: {path}"
            )

        if not full_path.is_file():
            return StorageResult(
                success=False,
                error=f"Not a file: {path}"
            )

        try:
            content = full_path.read_text(encoding="utf-8")
            etag = self._compute_etag(full_path)
            return StorageResult(success=True, data=content, etag=etag)
        except Exception as e:
            return StorageResult(success=False, error=str(e))

    async def write(self, path: str, content: str, etag: Optional[str] = None) -> StorageResult:
        """Write content to filesystem with optimistic concurrency."""
        full_path = self._get_full_path(path)

        # Optimistic concurrency check
        if etag is not None and full_path.exists():
            current_etag = self._compute_etag(full_path)
            if current_etag != etag:
                return StorageResult(
                    success=False,
                    error=f"Conflict: ETag mismatch. Expected {etag}, got {current_etag}",
                    etag=current_etag
                )

        try:
            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            full_path.write_text(content, encoding="utf-8")

            # Return new etag
            new_etag = self._compute_etag(full_path)
            return StorageResult(success=True, etag=new_etag)
        except Exception as e:
            return StorageResult(success=False, error=str(e))

    async def delete(self, path: str) -> StorageResult:
        """Delete file from filesystem."""
        full_path = self._get_full_path(path)

        if not full_path.exists():
            return StorageResult(
                success=False,
                error=f"File not found: {path}"
            )

        try:
            full_path.unlink()
            return StorageResult(success=True)
        except Exception as e:
            return StorageResult(success=False, error=str(e))

    async def list(self, prefix: str = "", pattern: str = "*") -> StorageResult:
        """List files with optional prefix and pattern."""
        search_path = self._get_full_path(prefix) if prefix else self.base_path

        if not search_path.exists():
            return StorageResult(success=True, data=[])

        try:
            files = []
            for item in search_path.rglob(pattern):
                if item.is_file():
                    rel_path = str(item.relative_to(self.base_path))
                    files.append(rel_path)

            return StorageResult(success=True, data=sorted(files))
        except Exception as e:
            return StorageResult(success=False, error=str(e))

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        full_path = self._get_full_path(path)
        return full_path.exists() and full_path.is_file()

    async def search(self, text: str, prefix: str = "", pattern: str = "*") -> StorageResult:
        """Search for text content in files."""
        list_result = await self.list(prefix, pattern)
        if not list_result.success:
            return list_result

        matches = []
        search_lower = text.lower()

        for file_path in list_result.data:
            read_result = await self.read(file_path)
            if read_result.success:
                content = read_result.data
                if search_lower in content.lower():
                    # Find matching lines
                    lines = content.split("\n")
                    matching_lines = []
                    for i, line in enumerate(lines, 1):
                        if search_lower in line.lower():
                            matching_lines.append({
                                "line_number": i,
                                "content": line.strip()[:200]
                            })
                            if len(matching_lines) >= 5:
                                break

                    matches.append({
                        "path": file_path,
                        "matches": matching_lines
                    })

        return StorageResult(success=True, data=matches)

    async def get_metadata(self, path: str) -> StorageResult:
        """Get file metadata."""
        full_path = self._get_full_path(path)

        if not full_path.exists():
            return StorageResult(
                success=False,
                error=f"File not found: {path}"
            )

        try:
            stat = full_path.stat()
            return StorageResult(
                success=True,
                data={
                    "path": path,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
                },
                etag=self._compute_etag(full_path)
            )
        except Exception as e:
            return StorageResult(success=False, error=str(e))
