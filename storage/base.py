"""Base storage interface for knowledge base.

This module defines the abstract interface for storage backends.
Implementations can include filesystem, Azure Blob, AWS S3, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
import json


@dataclass
class StorageResult:
    """Result from storage operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    etag: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "etag": self.etag
        }

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class BaseStorage(ABC):
    """Abstract base class for storage backends.

    All storage implementations must inherit from this class
    and implement the abstract methods.
    """

    @abstractmethod
    async def read(self, path: str) -> StorageResult:
        """Read content from storage.

        Args:
            path: Path to the file/blob

        Returns:
            StorageResult with content and etag
        """
        pass

    @abstractmethod
    async def write(self, path: str, content: str, etag: Optional[str] = None) -> StorageResult:
        """Write content to storage with optimistic concurrency.

        Args:
            path: Path to the file/blob
            content: Content to write
            etag: Expected etag for optimistic concurrency (None to skip check)

        Returns:
            StorageResult with new etag on success
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> StorageResult:
        """Delete a file/blob from storage.

        Args:
            path: Path to the file/blob

        Returns:
            StorageResult indicating success/failure
        """
        pass

    @abstractmethod
    async def list(self, prefix: str = "", pattern: str = "*") -> StorageResult:
        """List files/blobs with optional prefix and pattern.

        Args:
            prefix: Path prefix to filter
            pattern: Glob pattern to match

        Returns:
            StorageResult with list of paths
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a file/blob exists.

        Args:
            path: Path to check

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    async def search(self, text: str, prefix: str = "", pattern: str = "*") -> StorageResult:
        """Search for text content in files.

        Args:
            text: Text to search for
            prefix: Path prefix to filter
            pattern: File pattern to match

        Returns:
            StorageResult with list of matching files and snippets
        """
        pass

    async def read_json(self, path: str) -> StorageResult:
        """Read and parse JSON content.

        Args:
            path: Path to JSON file

        Returns:
            StorageResult with parsed data
        """
        result = await self.read(path)
        if not result.success:
            return result

        try:
            data = json.loads(result.data)
            return StorageResult(success=True, data=data, etag=result.etag)
        except json.JSONDecodeError as e:
            return StorageResult(success=False, error=f"JSON parse error: {e}")

    async def write_json(self, path: str, data: Any, etag: Optional[str] = None) -> StorageResult:
        """Write data as JSON.

        Args:
            path: Path to JSON file
            data: Data to serialize
            etag: Expected etag for optimistic concurrency

        Returns:
            StorageResult with new etag on success
        """
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            return await self.write(path, content, etag)
        except (TypeError, ValueError) as e:
            return StorageResult(success=False, error=f"JSON serialize error: {e}")
