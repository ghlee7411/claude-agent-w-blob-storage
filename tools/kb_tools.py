"""Knowledge base tools for Claude Agent SDK.

This module provides tools for managing the file-based knowledge base
with support for concurrent access and optimistic locking.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from storage import BaseStorage, StorageResult


class KnowledgeBaseTools:
    """Tools for interacting with the knowledge base."""

    def __init__(self, storage: BaseStorage):
        """Initialize knowledge base tools.

        Args:
            storage: Storage backend to use
        """
        self.storage = storage

    # =========================================================================
    # Topic Management
    # =========================================================================

    async def read_topic(self, topic_path: str) -> Dict[str, Any]:
        """Read a topic file from the knowledge base.

        Args:
            topic_path: Path relative to topics/ (e.g., "python/gil")

        Returns:
            Dict with content and metadata
        """
        md_path = f"topics/{topic_path}.md"
        meta_path = f"topics/{topic_path}.meta.json"

        content_result = await self.storage.read(md_path)
        meta_result = await self.storage.read_json(meta_path)

        if not content_result.success:
            return {
                "success": False,
                "error": f"Topic not found: {topic_path}",
                "path": topic_path
            }

        return {
            "success": True,
            "path": topic_path,
            "content": content_result.data,
            "etag": content_result.etag,
            "metadata": meta_result.data if meta_result.success else None
        }

    async def write_topic(
        self,
        topic_path: str,
        content: str,
        title: str,
        keywords: List[str],
        related_topics: Optional[List[str]] = None,
        citations: Optional[List[str]] = None,
        etag: Optional[str] = None,
        agent_id: str = "unknown"
    ) -> Dict[str, Any]:
        """Write or update a topic in the knowledge base.

        Args:
            topic_path: Path relative to topics/ (e.g., "python/gil")
            content: Markdown content
            title: Topic title
            keywords: List of keywords for search
            related_topics: List of related topic paths
            citations: List of citation IDs
            etag: Expected etag for optimistic concurrency
            agent_id: ID of the agent making the change

        Returns:
            Dict with success status and new etag
        """
        md_path = f"topics/{topic_path}.md"
        meta_path = f"topics/{topic_path}.meta.json"

        # Check existing metadata for version
        existing_meta = await self.storage.read_json(meta_path)
        version = 1
        existing_citations = []
        if existing_meta.success:
            version = existing_meta.data.get("version", 0) + 1
            existing_citations = existing_meta.data.get("citations", [])

        # Write content with optimistic concurrency
        write_result = await self.storage.write(md_path, content, etag)
        if not write_result.success:
            return {
                "success": False,
                "error": write_result.error,
                "etag": write_result.etag
            }

        # Merge citations
        all_citations = list(set(existing_citations + (citations or [])))

        # Write metadata
        metadata = {
            "topic_id": topic_path,
            "title": title,
            "version": version,
            "etag": write_result.etag,
            "last_modified": datetime.utcnow().isoformat() + "Z",
            "last_modified_by": agent_id,
            "citations": all_citations,
            "related_topics": related_topics or [],
            "keywords": keywords
        }

        meta_result = await self.storage.write_json(meta_path, metadata)
        if not meta_result.success:
            return {
                "success": False,
                "error": f"Failed to write metadata: {meta_result.error}"
            }

        return {
            "success": True,
            "path": topic_path,
            "etag": write_result.etag,
            "version": version,
            "message": f"Topic '{title}' saved successfully"
        }

    async def append_to_topic(
        self,
        topic_path: str,
        additional_content: str,
        citation_id: Optional[str] = None,
        agent_id: str = "unknown"
    ) -> Dict[str, Any]:
        """Append content to an existing topic.

        Args:
            topic_path: Path relative to topics/
            additional_content: Content to append
            citation_id: Citation ID for the new content
            agent_id: ID of the agent making the change

        Returns:
            Dict with success status
        """
        # Read existing content
        existing = await self.read_topic(topic_path)
        if not existing["success"]:
            return existing

        # Append content
        new_content = existing["content"] + "\n\n" + additional_content

        # Get existing metadata
        meta = existing.get("metadata", {})
        keywords = meta.get("keywords", [])
        related = meta.get("related_topics", [])
        citations = [citation_id] if citation_id else []

        return await self.write_topic(
            topic_path=topic_path,
            content=new_content,
            title=meta.get("title", topic_path),
            keywords=keywords,
            related_topics=related,
            citations=citations,
            etag=existing["etag"],
            agent_id=agent_id
        )

    async def delete_topic(self, topic_path: str) -> Dict[str, Any]:
        """Delete a topic from the knowledge base.

        Args:
            topic_path: Path relative to topics/

        Returns:
            Dict with success status
        """
        md_path = f"topics/{topic_path}.md"
        meta_path = f"topics/{topic_path}.meta.json"

        md_result = await self.storage.delete(md_path)
        meta_result = await self.storage.delete(meta_path)

        if md_result.success:
            return {
                "success": True,
                "message": f"Topic '{topic_path}' deleted"
            }
        else:
            return {
                "success": False,
                "error": md_result.error
            }

    # =========================================================================
    # Search and Discovery
    # =========================================================================

    async def list_topics(self, category: str = "") -> Dict[str, Any]:
        """List all topics, optionally filtered by category.

        Args:
            category: Category path (e.g., "python") or empty for all

        Returns:
            Dict with list of topics
        """
        prefix = f"topics/{category}" if category else "topics"
        result = await self.storage.list(prefix, "*.meta.json")

        if not result.success:
            return {"success": False, "error": result.error}

        topics = []
        for meta_path in result.data:
            meta_result = await self.storage.read_json(meta_path)
            if meta_result.success:
                topics.append({
                    "path": meta_result.data.get("topic_id"),
                    "title": meta_result.data.get("title"),
                    "keywords": meta_result.data.get("keywords", []),
                    "last_modified": meta_result.data.get("last_modified")
                })

        return {
            "success": True,
            "count": len(topics),
            "topics": topics
        }

    async def search_topics(self, query: str) -> Dict[str, Any]:
        """Search topics by content or keywords.

        Args:
            query: Search query

        Returns:
            Dict with matching topics
        """
        # First, search in content
        content_result = await self.storage.search(query, "topics", "*.md")

        # Also search in metadata keywords
        all_meta = await self.storage.list("topics", "*.meta.json")
        keyword_matches = []

        if all_meta.success:
            query_lower = query.lower()
            for meta_path in all_meta.data:
                meta_result = await self.storage.read_json(meta_path)
                if meta_result.success:
                    meta = meta_result.data
                    keywords = [k.lower() for k in meta.get("keywords", [])]
                    title = meta.get("title", "").lower()

                    if any(query_lower in k for k in keywords) or query_lower in title:
                        keyword_matches.append({
                            "path": meta.get("topic_id"),
                            "title": meta.get("title"),
                            "keywords": meta.get("keywords", []),
                            "match_type": "keyword"
                        })

        # Combine results
        results = []

        # Add content matches
        if content_result.success:
            for match in content_result.data:
                path = match["path"].replace("topics/", "").replace(".md", "")
                results.append({
                    "path": path,
                    "match_type": "content",
                    "snippets": match["matches"]
                })

        # Add keyword matches (avoid duplicates)
        content_paths = {r["path"] for r in results}
        for km in keyword_matches:
            if km["path"] not in content_paths:
                results.append(km)

        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results
        }

    async def find_related_topics(self, topic_path: str) -> Dict[str, Any]:
        """Find topics related to a given topic.

        Args:
            topic_path: Path of the source topic

        Returns:
            Dict with related topics
        """
        topic = await self.read_topic(topic_path)
        if not topic["success"]:
            return topic

        metadata = topic.get("metadata", {})
        related_paths = metadata.get("related_topics", [])
        keywords = metadata.get("keywords", [])

        related = []

        # Get explicitly related topics
        for path in related_paths:
            rel_topic = await self.read_topic(path)
            if rel_topic["success"]:
                related.append({
                    "path": path,
                    "title": rel_topic.get("metadata", {}).get("title", path),
                    "relation": "explicit"
                })

        # Find topics with similar keywords
        if keywords:
            search_result = await self.search_topics(keywords[0])
            if search_result["success"]:
                for result in search_result["results"][:5]:
                    if result["path"] != topic_path and result["path"] not in related_paths:
                        related.append({
                            "path": result["path"],
                            "title": result.get("title", result["path"]),
                            "relation": "keyword_similarity"
                        })

        return {
            "success": True,
            "source": topic_path,
            "related": related
        }

    # =========================================================================
    # Citation Management
    # =========================================================================

    async def add_citation(
        self,
        source_document: str,
        contributed_topics: List[str],
        summary: str,
        agent_id: str = "unknown"
    ) -> Dict[str, Any]:
        """Add a citation record for a source document.

        Args:
            source_document: Path or name of the source document
            contributed_topics: List of topic paths this document contributed to
            summary: Brief summary of what was extracted
            agent_id: ID of the agent that processed the document

        Returns:
            Dict with citation ID
        """
        citation_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"citations/{citation_id}_{timestamp}.json"

        citation = {
            "citation_id": citation_id,
            "source_document": source_document,
            "processed_at": datetime.utcnow().isoformat() + "Z",
            "processed_by": agent_id,
            "contributed_topics": contributed_topics,
            "summary": summary
        }

        result = await self.storage.write_json(filename, citation)

        if result.success:
            return {
                "success": True,
                "citation_id": citation_id,
                "filename": filename
            }
        else:
            return {
                "success": False,
                "error": result.error
            }

    async def get_citation(self, citation_id: str) -> Dict[str, Any]:
        """Get a citation record by ID.

        Args:
            citation_id: Citation ID

        Returns:
            Dict with citation data
        """
        # Search for citation file
        result = await self.storage.list("citations", f"{citation_id}_*.json")

        if not result.success or not result.data:
            return {
                "success": False,
                "error": f"Citation not found: {citation_id}"
            }

        citation_result = await self.storage.read_json(result.data[0])
        if citation_result.success:
            return {
                "success": True,
                "citation": citation_result.data
            }
        else:
            return {
                "success": False,
                "error": citation_result.error
            }

    # =========================================================================
    # Logging
    # =========================================================================

    async def log_operation(
        self,
        operation: str,
        details: Dict[str, Any],
        agent_id: str = "unknown"
    ) -> Dict[str, Any]:
        """Log an operation to the distributed log.

        Args:
            operation: Type of operation (e.g., "ingest", "query")
            details: Operation details
            agent_id: ID of the agent

        Returns:
            Dict with log entry ID
        """
        timestamp = datetime.utcnow()
        log_id = str(uuid.uuid4())[:8]
        filename = f"logs/{agent_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{log_id}.json"

        log_entry = {
            "log_id": log_id,
            "timestamp": timestamp.isoformat() + "Z",
            "agent_id": agent_id,
            "operation": operation,
            "details": details
        }

        result = await self.storage.write_json(filename, log_entry)

        return {
            "success": result.success,
            "log_id": log_id if result.success else None,
            "error": result.error if not result.success else None
        }

    # =========================================================================
    # Index Management
    # =========================================================================

    async def rebuild_index(self) -> Dict[str, Any]:
        """Rebuild the topics index from metadata files.

        Returns:
            Dict with index stats
        """
        all_meta = await self.storage.list("topics", "*.meta.json")

        if not all_meta.success:
            return {"success": False, "error": all_meta.error}

        index = {
            "rebuilt_at": datetime.utcnow().isoformat() + "Z",
            "topics": {}
        }

        for meta_path in all_meta.data:
            meta_result = await self.storage.read_json(meta_path)
            if meta_result.success:
                meta = meta_result.data
                topic_id = meta.get("topic_id")
                if topic_id:
                    index["topics"][topic_id] = {
                        "title": meta.get("title"),
                        "keywords": meta.get("keywords", []),
                        "last_modified": meta.get("last_modified")
                    }

        result = await self.storage.write_json("_index/topics_index.json", index)

        return {
            "success": result.success,
            "topic_count": len(index["topics"]),
            "message": f"Index rebuilt with {len(index['topics'])} topics"
        }

    async def get_index(self) -> Dict[str, Any]:
        """Get the current topics index.

        Returns:
            Dict with index data
        """
        result = await self.storage.read_json("_index/topics_index.json")

        if result.success:
            return {
                "success": True,
                "index": result.data
            }
        else:
            # Try to rebuild if not found
            return await self.rebuild_index()

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics.

        Returns:
            Dict with various statistics
        """
        topics_result = await self.storage.list("topics", "*.md")
        citations_result = await self.storage.list("citations", "*.json")
        logs_result = await self.storage.list("logs", "*.json")

        topics_count = len(topics_result.data) if topics_result.success else 0
        citations_count = len(citations_result.data) if citations_result.success else 0
        logs_count = len(logs_result.data) if logs_result.success else 0

        # Get categories
        categories = set()
        if topics_result.success:
            for path in topics_result.data:
                parts = path.split("/")
                if len(parts) > 2:
                    categories.add(parts[1])

        return {
            "success": True,
            "stats": {
                "total_topics": topics_count,
                "total_citations": citations_count,
                "total_logs": logs_count,
                "categories": sorted(list(categories))
            }
        }
