"""Filesystem storage implementation.

This module provides a filesystem-based storage backend
that can later be swapped for blob storage.
"""

import asyncio
import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

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

    # =========================================================================
    # Locking Implementation
    # =========================================================================

    def _get_lock_path(self, path: str) -> Path:
        """Get lock file path for a given file path."""
        lock_dir = self.base_path / "_locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        # Replace / with __ to flatten the path
        safe_name = path.replace("/", "__").replace("\\", "__")
        return lock_dir / f"{safe_name}.lock"

    def _read_lock_file(self, lock_path: Path) -> Optional[dict]:
        """Read and parse lock file, returns None if invalid or expired."""
        if not lock_path.exists():
            return None

        try:
            with open(lock_path, "r", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    lock_data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Check if expired
            expires_at = datetime.fromisoformat(lock_data["expires_at"])
            if datetime.utcnow() > expires_at:
                # Lock expired, clean up
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                return None

            return lock_data
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            return None

    async def acquire_lock(
        self,
        path: str,
        holder_id: str,
        timeout_seconds: float = 30.0,
        wait: bool = True,
        wait_timeout: float = 60.0
    ) -> StorageResult:
        """Acquire an exclusive lock on a file.

        Uses file-based locking with fcntl for atomicity.
        """
        lock_path = self._get_lock_path(path)
        lock_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        while True:
            # Check existing lock
            existing_lock = self._read_lock_file(lock_path)

            if existing_lock is None:
                # No valid lock exists, try to acquire
                lock_data = {
                    "lock_id": lock_id,
                    "holder_id": holder_id,
                    "path": path,
                    "acquired_at": datetime.utcnow().isoformat(),
                    "expires_at": (datetime.utcnow() + timedelta(seconds=timeout_seconds)).isoformat()
                }

                try:
                    # Use exclusive lock for atomic write
                    lock_path.parent.mkdir(parents=True, exist_ok=True)

                    # Open with O_CREAT | O_EXCL for atomic creation
                    fd = os.open(
                        str(lock_path),
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o644
                    )
                    try:
                        with os.fdopen(fd, "w", encoding="utf-8") as f:
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                            json.dump(lock_data, f)
                            f.flush()
                            os.fsync(f.fileno())
                    except Exception:
                        os.close(fd)
                        raise

                    return StorageResult(
                        success=True,
                        lock_id=lock_id,
                        data={
                            "holder_id": holder_id,
                            "expires_at": lock_data["expires_at"]
                        }
                    )
                except FileExistsError:
                    # Another process created the lock file between our check and create
                    pass
                except Exception as e:
                    return StorageResult(
                        success=False,
                        error=f"Failed to acquire lock: {e}"
                    )

            # Lock exists and is valid
            if not wait:
                return StorageResult(
                    success=False,
                    error=f"File is locked by {existing_lock['holder_id']}",
                    data=existing_lock
                )

            # Check wait timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed >= wait_timeout:
                return StorageResult(
                    success=False,
                    error=f"Timeout waiting for lock (held by {existing_lock['holder_id']})",
                    data=existing_lock
                )

            # Wait and retry
            await asyncio.sleep(0.5)

    async def release_lock(self, path: str, lock_id: str) -> StorageResult:
        """Release a previously acquired lock."""
        lock_path = self._get_lock_path(path)

        if not lock_path.exists():
            return StorageResult(
                success=False,
                error="Lock does not exist"
            )

        try:
            # Read and verify lock ownership
            with open(lock_path, "r+", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    lock_data = json.load(f)

                    if lock_data.get("lock_id") != lock_id:
                        return StorageResult(
                            success=False,
                            error="Lock ID mismatch - lock owned by another holder"
                        )
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Remove lock file
            lock_path.unlink()
            return StorageResult(success=True)

        except Exception as e:
            return StorageResult(
                success=False,
                error=f"Failed to release lock: {e}"
            )

    async def check_lock(self, path: str) -> StorageResult:
        """Check the lock status of a file."""
        lock_path = self._get_lock_path(path)
        lock_data = self._read_lock_file(lock_path)

        if lock_data is None:
            return StorageResult(
                success=True,
                data=None  # Not locked
            )

        return StorageResult(
            success=True,
            data={
                "locked": True,
                "holder_id": lock_data["holder_id"],
                "acquired_at": lock_data["acquired_at"],
                "expires_at": lock_data["expires_at"]
            }
        )

    async def force_unlock(self, path: str) -> StorageResult:
        """Force release a lock (admin operation)."""
        lock_path = self._get_lock_path(path)

        if not lock_path.exists():
            return StorageResult(
                success=True,
                data={"message": "No lock to remove"}
            )

        try:
            lock_path.unlink()
            return StorageResult(
                success=True,
                data={"message": "Lock forcefully removed"}
            )
        except Exception as e:
            return StorageResult(
                success=False,
                error=f"Failed to force unlock: {e}"
            )
