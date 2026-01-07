"""Storage abstraction layer for knowledge base."""

from .base import BaseStorage, StorageResult
from .filesystem import FileSystemStorage

__all__ = ["BaseStorage", "StorageResult", "FileSystemStorage"]
