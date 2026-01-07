"""
File System Storage Tools for Claude Agent

This module provides file system operations that can later be replaced
with blob storage operations for scalability.

Tools provided:
- read_file: Read content from a file
- write_file: Write content to a file
- list_files: List files in a directory
- delete_file: Delete a file
- search_files: Search for files containing specific text
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


class FileSystemStorage:
    """File system storage manager for knowledge base"""
    
    def __init__(self, base_path: str = "./storage"):
        """
        Initialize the file system storage manager
        
        Args:
            base_path: Base directory for storing files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def read_file(self, file_path: str) -> Dict[str, Any]:
        """
        Read content from a file
        
        Args:
            file_path: Relative path to the file within storage
            
        Returns:
            Dictionary with 'success', 'content', and 'error' keys
        """
        try:
            full_path = self.base_path / file_path
            if not full_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "content": None
                }
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "file_path": file_path,
                "size": len(content)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": None
            }
    
    def write_file(self, file_path: str, content: str, mode: str = "w") -> Dict[str, Any]:
        """
        Write content to a file
        
        Args:
            file_path: Relative path to the file within storage
            content: Content to write
            mode: Write mode - 'w' for overwrite, 'a' for append
            
        Returns:
            Dictionary with 'success', 'message', and 'error' keys
        """
        try:
            full_path = self.base_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, mode, encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Successfully wrote to {file_path}",
                "file_path": file_path,
                "size": len(content)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_files(self, directory: str = "", pattern: str = "*") -> Dict[str, Any]:
        """
        List files in a directory
        
        Args:
            directory: Relative directory path within storage (empty for root)
            pattern: File pattern to match (e.g., "*.txt", "*.json")
            
        Returns:
            Dictionary with 'success', 'files', and 'error' keys
        """
        try:
            search_path = self.base_path / directory
            if not search_path.exists():
                return {
                    "success": False,
                    "error": f"Directory not found: {directory}",
                    "files": []
                }
            
            files = []
            for file_path in search_path.glob(pattern):
                if file_path.is_file():
                    relative_path = file_path.relative_to(self.base_path)
                    files.append({
                        "path": str(relative_path),
                        "name": file_path.name,
                        "size": file_path.stat().st_size
                    })
            
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "files": []
            }
    
    def delete_file(self, file_path: str) -> Dict[str, Any]:
        """
        Delete a file
        
        Args:
            file_path: Relative path to the file within storage
            
        Returns:
            Dictionary with 'success', 'message', and 'error' keys
        """
        try:
            full_path = self.base_path / file_path
            if not full_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }
            
            full_path.unlink()
            
            return {
                "success": True,
                "message": f"Successfully deleted {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_files(self, search_text: str, directory: str = "", file_pattern: str = "*") -> Dict[str, Any]:
        """
        Search for files containing specific text
        
        Args:
            search_text: Text to search for
            directory: Relative directory path within storage (empty for root)
            file_pattern: File pattern to match (e.g., "*.txt")
            
        Returns:
            Dictionary with 'success', 'matches', and 'error' keys
        """
        try:
            search_path = self.base_path / directory
            if not search_path.exists():
                return {
                    "success": False,
                    "error": f"Directory not found: {directory}",
                    "matches": []
                }
            
            matches = []
            for file_path in search_path.rglob(file_pattern):
                if file_path.is_file():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if search_text.lower() in content.lower():
                                relative_path = file_path.relative_to(self.base_path)
                                # Find matching lines
                                matching_lines = [
                                    (i + 1, line.strip()) 
                                    for i, line in enumerate(content.split('\n'))
                                    if search_text.lower() in line.lower()
                                ]
                                matches.append({
                                    "path": str(relative_path),
                                    "name": file_path.name,
                                    "matching_lines": matching_lines[:5]  # First 5 matches
                                })
                    except Exception:
                        # Skip files that can't be read as text
                        continue
            
            return {
                "success": True,
                "matches": matches,
                "count": len(matches),
                "search_text": search_text
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "matches": []
            }


# Tool definitions for Claude Agent SDK
def get_storage_tools():
    """
    Get tool definitions for Claude Agent SDK
    
    Returns:
        List of tool definitions compatible with Claude Agent SDK
    """
    return [
        {
            "name": "read_file",
            "description": "Read content from a file in the knowledge base storage. Use this to retrieve existing documents or data.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file within storage (e.g., 'documents/article.txt')"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "write_file",
            "description": "Write or update content in a file in the knowledge base storage. Use this to store new documents or update existing ones.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file within storage (e.g., 'documents/article.txt')"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["w", "a"],
                        "description": "Write mode: 'w' to overwrite (default), 'a' to append",
                        "default": "w"
                    }
                },
                "required": ["file_path", "content"]
            }
        },
        {
            "name": "list_files",
            "description": "List files in a directory of the knowledge base storage. Use this to explore what documents are available.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Relative directory path within storage (empty string for root)",
                        "default": ""
                    },
                    "pattern": {
                        "type": "string",
                        "description": "File pattern to match (e.g., '*.txt', '*.json')",
                        "default": "*"
                    }
                },
                "required": []
            }
        },
        {
            "name": "delete_file",
            "description": "Delete a file from the knowledge base storage. Use this carefully to remove outdated or incorrect documents.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file within storage"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "search_files",
            "description": "Search for files containing specific text in the knowledge base. Use this to find relevant documents based on content.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "search_text": {
                        "type": "string",
                        "description": "Text to search for in file contents"
                    },
                    "directory": {
                        "type": "string",
                        "description": "Relative directory path within storage (empty string for root)",
                        "default": ""
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "File pattern to match (e.g., '*.txt')",
                        "default": "*"
                    }
                },
                "required": ["search_text"]
            }
        }
    ]
