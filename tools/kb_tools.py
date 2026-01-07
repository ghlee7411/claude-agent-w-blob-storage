"""Knowledge base tools for Claude Agent SDK.

This module provides tools for managing the file-based knowledge base
with support for concurrent access, optimistic locking, and optimized
search using inverted indexes.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from storage import BaseStorage, StorageResult


class KnowledgeBaseTools:
    """Tools for interacting with the knowledge base.

    Performance optimizations:
    - Index-based search instead of full file scans
    - Inverted index for O(1) keyword lookups
    - Parallel I/O with asyncio.gather
    - In-memory index caching
    """

    def __init__(self, storage: BaseStorage):
        """Initialize knowledge base tools.

        Args:
            storage: Storage backend to use
        """
        self.storage = storage
        self._index_cache: Optional[Dict] = None
        self._inverted_index_cache: Optional[Dict] = None

    # =========================================================================
    # Index Management (Optimized)
    # =========================================================================

    async def get_index(self, force_reload: bool = False) -> Dict[str, Any]:
        """Get the current topics index with caching.

        Args:
            force_reload: Force reload from storage

        Returns:
            Dict with index data
        """
        if self._index_cache is not None and not force_reload:
            return {"success": True, "index": self._index_cache}

        result = await self.storage.read_json("_index/topics_index.json")

        if result.success:
            self._index_cache = result.data
            return {"success": True, "index": result.data}
        else:
            # Try to rebuild if not found
            rebuild_result = await self.rebuild_index()
            if rebuild_result["success"]:
                return {"success": True, "index": self._index_cache}
            return {"success": False, "error": "Index not available"}

    async def get_inverted_index(self, force_reload: bool = False) -> Dict[str, Any]:
        """Get the inverted index for keyword lookups.

        Args:
            force_reload: Force reload from storage

        Returns:
            Dict with inverted index data
        """
        if self._inverted_index_cache is not None and not force_reload:
            return {"success": True, "index": self._inverted_index_cache}

        result = await self.storage.read_json("_index/inverted_index.json")

        if result.success:
            self._inverted_index_cache = result.data
            return {"success": True, "index": result.data}
        else:
            # Try to rebuild if not found
            rebuild_result = await self.rebuild_index()
            if rebuild_result["success"]:
                return {"success": True, "index": self._inverted_index_cache}
            return {"success": False, "error": "Inverted index not available"}

    async def rebuild_index(self) -> Dict[str, Any]:
        """Rebuild all indexes from metadata files using parallel I/O.

        Returns:
            Dict with index stats
        """
        all_meta = await self.storage.list("topics", "*.meta.json")

        if not all_meta.success:
            return {"success": False, "error": all_meta.error}

        # Parallel read all metadata files
        read_tasks = [self.storage.read_json(path) for path in all_meta.data]
        results = await asyncio.gather(*read_tasks, return_exceptions=True)

        # Build main index and inverted index
        topics_index = {
            "rebuilt_at": datetime.utcnow().isoformat() + "Z",
            "topics": {}
        }

        inverted_index = {
            "rebuilt_at": datetime.utcnow().isoformat() + "Z",
            "keywords": {},      # keyword -> [topic_ids]
            "titles": {},        # word in title -> [topic_ids]
            "categories": {}     # category -> [topic_ids]
        }

        for meta_path, result in zip(all_meta.data, results):
            if isinstance(result, Exception):
                continue
            if not result.success:
                continue

            meta = result.data
            topic_id = meta.get("topic_id")
            if not topic_id:
                continue

            # Main index entry
            topics_index["topics"][topic_id] = {
                "title": meta.get("title"),
                "keywords": meta.get("keywords", []),
                "last_modified": meta.get("last_modified"),
                "related_topics": meta.get("related_topics", [])
            }

            # Inverted index: keywords
            for keyword in meta.get("keywords", []):
                keyword_lower = keyword.lower()
                if keyword_lower not in inverted_index["keywords"]:
                    inverted_index["keywords"][keyword_lower] = []
                if topic_id not in inverted_index["keywords"][keyword_lower]:
                    inverted_index["keywords"][keyword_lower].append(topic_id)

            # Inverted index: title words
            title = meta.get("title", "")
            for word in title.lower().split():
                if len(word) >= 2:  # Skip very short words
                    if word not in inverted_index["titles"]:
                        inverted_index["titles"][word] = []
                    if topic_id not in inverted_index["titles"][word]:
                        inverted_index["titles"][word].append(topic_id)

            # Inverted index: categories
            if "/" in topic_id:
                category = topic_id.split("/")[0]
                if category not in inverted_index["categories"]:
                    inverted_index["categories"][category] = []
                if topic_id not in inverted_index["categories"][category]:
                    inverted_index["categories"][category].append(topic_id)

        # Write indexes in parallel
        write_tasks = [
            self.storage.write_json("_index/topics_index.json", topics_index),
            self.storage.write_json("_index/inverted_index.json", inverted_index)
        ]
        await asyncio.gather(*write_tasks)

        # Update caches
        self._index_cache = topics_index
        self._inverted_index_cache = inverted_index

        return {
            "success": True,
            "topic_count": len(topics_index["topics"]),
            "keyword_count": len(inverted_index["keywords"]),
            "message": f"Index rebuilt with {len(topics_index['topics'])} topics, {len(inverted_index['keywords'])} keywords"
        }

    def invalidate_cache(self):
        """Invalidate all cached indexes."""
        self._index_cache = None
        self._inverted_index_cache = None

    async def _update_indexes_for_topic(
        self,
        topic_id: str,
        title: str,
        keywords: List[str],
        remove: bool = False
    ):
        """Incrementally update indexes when a topic changes.

        Args:
            topic_id: Topic ID being changed
            title: Topic title
            keywords: Topic keywords
            remove: If True, remove from indexes instead of adding
        """
        # Load indexes if not cached
        await self.get_index()
        await self.get_inverted_index()

        if self._index_cache is None or self._inverted_index_cache is None:
            return

        if remove:
            # Remove from main index
            if topic_id in self._index_cache.get("topics", {}):
                del self._index_cache["topics"][topic_id]

            # Remove from inverted indexes
            for keyword in keywords:
                kw_lower = keyword.lower()
                if kw_lower in self._inverted_index_cache.get("keywords", {}):
                    topics = self._inverted_index_cache["keywords"][kw_lower]
                    if topic_id in topics:
                        topics.remove(topic_id)

            for word in title.lower().split():
                if word in self._inverted_index_cache.get("titles", {}):
                    topics = self._inverted_index_cache["titles"][word]
                    if topic_id in topics:
                        topics.remove(topic_id)
        else:
            # Update main index
            self._index_cache["topics"][topic_id] = {
                "title": title,
                "keywords": keywords,
                "last_modified": datetime.utcnow().isoformat() + "Z"
            }

            # Update inverted indexes
            for keyword in keywords:
                kw_lower = keyword.lower()
                if kw_lower not in self._inverted_index_cache["keywords"]:
                    self._inverted_index_cache["keywords"][kw_lower] = []
                if topic_id not in self._inverted_index_cache["keywords"][kw_lower]:
                    self._inverted_index_cache["keywords"][kw_lower].append(topic_id)

            for word in title.lower().split():
                if len(word) >= 2:
                    if word not in self._inverted_index_cache["titles"]:
                        self._inverted_index_cache["titles"][word] = []
                    if topic_id not in self._inverted_index_cache["titles"][word]:
                        self._inverted_index_cache["titles"][word].append(topic_id)

            # Category
            if "/" in topic_id:
                category = topic_id.split("/")[0]
                if category not in self._inverted_index_cache["categories"]:
                    self._inverted_index_cache["categories"][category] = []
                if topic_id not in self._inverted_index_cache["categories"][category]:
                    self._inverted_index_cache["categories"][category].append(topic_id)

        # Persist indexes asynchronously
        write_tasks = [
            self.storage.write_json("_index/topics_index.json", self._index_cache),
            self.storage.write_json("_index/inverted_index.json", self._inverted_index_cache)
        ]
        await asyncio.gather(*write_tasks)

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

        # Parallel read content and metadata
        content_task = self.storage.read(md_path)
        meta_task = self.storage.read_json(meta_path)
        content_result, meta_result = await asyncio.gather(content_task, meta_task)

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
        old_keywords = []
        old_title = ""
        if existing_meta.success:
            version = existing_meta.data.get("version", 0) + 1
            existing_citations = existing_meta.data.get("citations", [])
            old_keywords = existing_meta.data.get("keywords", [])
            old_title = existing_meta.data.get("title", "")

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

        # Update indexes incrementally
        if old_keywords or old_title:
            await self._update_indexes_for_topic(topic_path, old_title, old_keywords, remove=True)
        await self._update_indexes_for_topic(topic_path, title, keywords, remove=False)

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
        # Get metadata for index cleanup
        meta_result = await self.storage.read_json(f"topics/{topic_path}.meta.json")
        old_title = ""
        old_keywords = []
        if meta_result.success:
            old_title = meta_result.data.get("title", "")
            old_keywords = meta_result.data.get("keywords", [])

        md_path = f"topics/{topic_path}.md"
        meta_path = f"topics/{topic_path}.meta.json"

        # Parallel delete
        md_task = self.storage.delete(md_path)
        meta_task = self.storage.delete(meta_path)
        md_result, meta_result = await asyncio.gather(md_task, meta_task)

        if md_result.success:
            # Update indexes
            await self._update_indexes_for_topic(topic_path, old_title, old_keywords, remove=True)
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
    # Search and Discovery (Optimized with Indexes)
    # =========================================================================

    async def list_topics(self, category: str = "") -> Dict[str, Any]:
        """List all topics using index (no file scanning).

        Args:
            category: Category path (e.g., "python") or empty for all

        Returns:
            Dict with list of topics
        """
        index_result = await self.get_index()
        if not index_result["success"]:
            return {"success": False, "error": "Index not available"}

        topics_data = index_result["index"].get("topics", {})
        topics = []

        for topic_id, data in topics_data.items():
            # Filter by category if specified
            if category:
                if not topic_id.startswith(f"{category}/"):
                    continue

            topics.append({
                "path": topic_id,
                "title": data.get("title"),
                "keywords": data.get("keywords", []),
                "last_modified": data.get("last_modified")
            })

        return {
            "success": True,
            "count": len(topics),
            "topics": topics
        }

    async def search_topics(self, query: str) -> Dict[str, Any]:
        """Search topics using inverted index (O(1) keyword lookup).

        Args:
            query: Search query

        Returns:
            Dict with matching topics
        """
        inv_index_result = await self.get_inverted_index()
        index_result = await self.get_index()

        if not inv_index_result["success"] or not index_result["success"]:
            return {"success": False, "error": "Index not available"}

        inv_index = inv_index_result["index"]
        main_index = index_result["index"]
        query_lower = query.lower()
        query_words = query_lower.split()

        # Collect matching topic IDs from inverted index
        matching_ids: Set[str] = set()

        # Search in keywords
        for word in query_words:
            if word in inv_index.get("keywords", {}):
                matching_ids.update(inv_index["keywords"][word])
            # Partial match for keywords
            for keyword, topic_ids in inv_index.get("keywords", {}).items():
                if word in keyword or keyword in word:
                    matching_ids.update(topic_ids)

        # Search in titles
        for word in query_words:
            if word in inv_index.get("titles", {}):
                matching_ids.update(inv_index["titles"][word])

        # Build results with metadata from main index
        results = []
        topics_data = main_index.get("topics", {})

        for topic_id in matching_ids:
            if topic_id in topics_data:
                data = topics_data[topic_id]
                results.append({
                    "path": topic_id,
                    "title": data.get("title"),
                    "keywords": data.get("keywords", []),
                    "match_type": "index"
                })

        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results
        }

    async def search_topics_fulltext(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Full-text search in content (fallback, slower).

        Use this when index search doesn't find results.

        Args:
            query: Search query
            limit: Maximum results to return

        Returns:
            Dict with matching topics
        """
        # First try index-based search
        index_results = await self.search_topics(query)
        if index_results["success"] and index_results["count"] > 0:
            return index_results

        # Fallback to content search (limited)
        content_result = await self.storage.search(query, "topics", "*.md")

        if not content_result.success:
            return {"success": False, "error": content_result.error}

        results = []
        for match in content_result.data[:limit]:
            path = match["path"].replace("topics/", "").replace(".md", "")
            results.append({
                "path": path,
                "match_type": "content",
                "snippets": match["matches"]
            })

        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results
        }

    async def find_related_topics(self, topic_path: str) -> Dict[str, Any]:
        """Find topics related to a given topic using index.

        Args:
            topic_path: Path of the source topic

        Returns:
            Dict with related topics
        """
        index_result = await self.get_index()
        if not index_result["success"]:
            return {"success": False, "error": "Index not available"}

        topics_data = index_result["index"].get("topics", {})

        if topic_path not in topics_data:
            return {
                "success": False,
                "error": f"Topic not found: {topic_path}"
            }

        source_data = topics_data[topic_path]
        related_paths = source_data.get("related_topics", [])
        keywords = source_data.get("keywords", [])

        related = []

        # Get explicitly related topics from index
        for path in related_paths:
            if path in topics_data:
                related.append({
                    "path": path,
                    "title": topics_data[path].get("title", path),
                    "relation": "explicit"
                })

        # Find topics with similar keywords using inverted index
        if keywords:
            inv_result = await self.get_inverted_index()
            if inv_result["success"]:
                inv_index = inv_result["index"]
                similar_ids: Set[str] = set()

                for keyword in keywords[:3]:  # Check first 3 keywords
                    kw_lower = keyword.lower()
                    if kw_lower in inv_index.get("keywords", {}):
                        similar_ids.update(inv_index["keywords"][kw_lower])

                # Add similar topics (limit to 5)
                for similar_id in list(similar_ids)[:5]:
                    if similar_id != topic_path and similar_id not in related_paths:
                        if similar_id in topics_data:
                            related.append({
                                "path": similar_id,
                                "title": topics_data[similar_id].get("title", similar_id),
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
    # Statistics
    # =========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics using index.

        Returns:
            Dict with various statistics
        """
        index_result = await self.get_index()
        inv_result = await self.get_inverted_index()

        topics_count = 0
        categories = []

        if index_result["success"]:
            topics_count = len(index_result["index"].get("topics", {}))

        if inv_result["success"]:
            categories = list(inv_result["index"].get("categories", {}).keys())

        # Count citations and logs (these are small, OK to list)
        citations_result = await self.storage.list("citations", "*.json")
        logs_result = await self.storage.list("logs", "*.json")

        citations_count = len(citations_result.data) if citations_result.success else 0
        logs_count = len(logs_result.data) if logs_result.success else 0

        return {
            "success": True,
            "stats": {
                "total_topics": topics_count,
                "total_citations": citations_count,
                "total_logs": logs_count,
                "categories": sorted(categories)
            }
        }
