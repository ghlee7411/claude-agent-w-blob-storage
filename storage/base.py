"""Base storage interface for knowledge base.

This module defines the abstract interface for storage backends.
Implementations can include filesystem, Azure Blob, AWS S3, etc.
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Optional, AsyncGenerator
import json


@dataclass
class StorageResult:
    """Result from storage operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    etag: Optional[str] = None
    lock_id: Optional[str] = None  # For lock operations

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

    # =========================================================================
    # Locking Operations (Pessimistic Concurrency Control)
    # =========================================================================

    async def acquire_lock(
        self,
        path: str,
        holder_id: str,
        timeout_seconds: float = 30.0,
        wait: bool = True,
        wait_timeout: float = 60.0
    ) -> StorageResult:
        """Acquire an exclusive lock on a file/blob.

        Like checking out a document from a filing cabinet - only one
        agent can hold the lock at a time.

        Args:
            path: Path to the file/blob to lock
            holder_id: Unique identifier of the lock holder (e.g., agent_id)
            timeout_seconds: Lock auto-expires after this duration (prevents deadlocks)
            wait: If True, wait for lock to become available; if False, fail immediately
            wait_timeout: Maximum time to wait for lock (only if wait=True)

        Returns:
            StorageResult with lock_id on success, error if lock unavailable
        """
        raise NotImplementedError("Subclasses must implement acquire_lock")

    async def release_lock(self, path: str, lock_id: str) -> StorageResult:
        """Release a previously acquired lock.

        Like returning a document to the filing cabinet.

        Args:
            path: Path to the locked file/blob
            lock_id: Lock ID returned from acquire_lock

        Returns:
            StorageResult indicating success/failure
        """
        raise NotImplementedError("Subclasses must implement release_lock")

    async def check_lock(self, path: str) -> StorageResult:
        """Check the lock status of a file/blob.

        Args:
            path: Path to check

        Returns:
            StorageResult with lock info (holder_id, expires_at) or None if unlocked
        """
        raise NotImplementedError("Subclasses must implement check_lock")

    async def force_unlock(self, path: str) -> StorageResult:
        """Force release a lock (admin operation).

        Use with caution - only for recovery from stuck locks.

        Args:
            path: Path to unlock

        Returns:
            StorageResult indicating success/failure
        """
        raise NotImplementedError("Subclasses must implement force_unlock")

    @asynccontextmanager
    async def locked(
        self,
        path: str,
        holder_id: str,
        timeout_seconds: float = 30.0
    ) -> AsyncGenerator[StorageResult, None]:
        """Context manager for safe lock acquisition and release.

        Usage:
            async with storage.locked("topics/python/gil.md", "agent-123") as lock:
                if lock.success:
                    # safely read/modify/write the file
                    pass

        Args:
            path: Path to lock
            holder_id: Unique identifier of the lock holder
            timeout_seconds: Lock auto-expires after this duration

        Yields:
            StorageResult from acquire_lock
        """
        lock_result = await self.acquire_lock(
            path, holder_id, timeout_seconds, wait=True
        )
        try:
            yield lock_result
        finally:
            if lock_result.success and lock_result.lock_id:
                await self.release_lock(path, lock_result.lock_id)
