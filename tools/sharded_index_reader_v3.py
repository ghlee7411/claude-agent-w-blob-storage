"""v3.0 2-Tier Sharded Index Reader with optimized I/O for 1M-10M topics.

Key improvements:
- Keyword 2-tier lookup: summary → individual file (48MB → 100KB)
- 100 topic shards instead of 10 (350MB → 3.5MB per shard)
"""

from typing import Dict, Any, List, Optional, Set

from storage.base import BaseStorage
from storage.bloom_filter import (
    MultiBloomFilter,
    get_keyword_shard,
    get_category_shard
)
from tools.index_builder_v3 import get_topic_shard_v3


class ShardedIndexReaderV3:
    """Efficient reader for v3.0 2-tier sharded indexes.

    Usage:
        reader = ShardedIndexReaderV3(storage)

        # Search keyword (2-tier lookup)
        # Step 1: Read summary (50KB)
        # Step 2: Read individual keyword file (20KB)
        # Total: 70KB instead of 48MB!
        results = await reader.search_keyword("python")
    """

    def __init__(self, storage: BaseStorage, topic_shard_count: int = 100):
        """Initialize v3.0 reader.

        Args:
            storage: Storage backend
            topic_shard_count: Number of topic shards (default: 100)
        """
        self.storage = storage
        self.topic_shard_count = topic_shard_count

        # Caches
        self._summary_cache: Optional[Dict] = None
        self._bloom_cache: Optional[MultiBloomFilter] = None
        self._keyword_summary_cache: Dict[str, Dict] = {}
        self._keyword_detail_cache: Dict[str, Dict[str, Dict]] = {}  # shard -> keyword -> data
        self._category_shard_cache: Dict[str, Dict] = {}
        self._topic_shard_cache: Dict[int, Dict] = {}

    async def is_v3_index(self) -> bool:
        """Check if index is v3.0."""
        result = await self.storage.read_json("_index/summary.json")
        if result.success:
            data = result.data
            return data.get("version") == "3.0.0" and data.get("index_type") == "2-tier-sharded"
        return False

    async def get_summary(self) -> Dict[str, Any]:
        """Get index summary."""
        if self._summary_cache is not None:
            return {"success": True, "summary": self._summary_cache}

        result = await self.storage.read_json("_index/summary.json")
        if not result.success:
            return {"success": False, "error": "Summary not available"}

        self._summary_cache = result.data
        return {"success": True, "summary": result.data}

    async def get_bloom_filter(self) -> Optional[MultiBloomFilter]:
        """Get Bloom filter."""
        if self._bloom_cache is not None:
            return self._bloom_cache

        result = await self.storage.read_json("_index/bloom.json")
        if not result.success:
            return None

        self._bloom_cache = MultiBloomFilter.from_dict(result.data)
        return self._bloom_cache

    async def search_keyword(self, query: str) -> Dict[str, Any]:
        """Search keyword using 2-tier lookup.

        I/O: ~20KB (bloom) + ~50KB (summary) + ~20KB (detail) = ~90KB
        vs v2.0: 48MB

        Args:
            query: Search query

        Returns:
            Dict with matching topic IDs
        """
        query_words = query.lower().split()
        matching_ids: Set[str] = set()

        for word in query_words:
            # Step 1: Bloom filter check (20KB, cached)
            bloom = await self.get_bloom_filter()
            if bloom and not bloom.keyword_might_exist(word):
                continue  # Definitely doesn't exist

            # Step 2: Get shard summary (50KB, cached)
            shard_name = get_keyword_shard(word)
            summary = await self._get_keyword_summary(shard_name)

            if not summary or word not in summary.get("keywords", []):
                continue  # Not in this shard

            # Step 3: Load individual keyword file (20KB)
            keyword_data = await self._get_keyword_detail(shard_name, word)
            if keyword_data:
                matching_ids.update(keyword_data.get("topics", []))

        return {
            "success": True,
            "query": query,
            "count": len(matching_ids),
            "topic_ids": list(matching_ids)
        }

    async def get_category_topics(self, category: str) -> Dict[str, Any]:
        """Get all topics in a category (unchanged from v2.0)."""
        bloom = await self.get_bloom_filter()
        if bloom and not bloom.category_might_exist(category):
            return {
                "success": True,
                "category": category,
                "count": 0,
                "topics": {}
            }

        shard_data = await self._get_category_shard(category)
        if not shard_data:
            return {
                "success": True,
                "category": category,
                "count": 0,
                "topics": {}
            }

        return {
            "success": True,
            "category": category,
            "count": shard_data.get("topic_count", 0),
            "topics": shard_data.get("topics", {})
        }

    async def get_topic_metadata(self, topic_id: str) -> Dict[str, Any]:
        """Get metadata for a specific topic.

        I/O: ~3.5MB (100 shards) vs ~350MB (10 shards in v2.0)

        Args:
            topic_id: Topic ID

        Returns:
            Dict with topic metadata
        """
        shard_id = get_topic_shard_v3(topic_id, self.topic_shard_count)
        shard_data = await self._get_topic_shard(shard_id)

        if not shard_data:
            return {"success": False, "error": f"Topic not found: {topic_id}"}

        topics = shard_data.get("topics", {})
        if topic_id not in topics:
            return {"success": False, "error": f"Topic not found: {topic_id}"}

        return {
            "success": True,
            "topic_id": topic_id,
            "metadata": topics[topic_id]
        }

    async def get_all_categories(self) -> List[str]:
        """Get list of all categories."""
        summary_result = await self.get_summary()
        if not summary_result["success"]:
            return []
        return summary_result["summary"].get("categories", [])

    async def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        summary_result = await self.get_summary()
        if not summary_result["success"]:
            return {"success": False, "error": "Summary not available"}

        summary = summary_result["summary"]
        return {
            "success": True,
            "total_topics": summary.get("total_topics", 0),
            "total_keywords": summary.get("total_keywords", 0),
            "total_categories": summary.get("total_categories", 0),
            "categories": summary.get("categories", []),
            "last_rebuilt": summary.get("last_rebuilt"),
            "index_version": summary.get("version")
        }

    # =========================================================================
    # Private helper methods
    # =========================================================================

    async def _get_keyword_summary(self, shard_name: str) -> Optional[Dict]:
        """Load keyword summary with caching.

        Args:
            shard_name: Shard name (e.g., "a-e")

        Returns:
            Summary data or None
        """
        if shard_name in self._keyword_summary_cache:
            return self._keyword_summary_cache[shard_name]

        path = f"_index/shards/keywords/{shard_name}.summary.json"
        result = await self.storage.read_json(path)

        if not result.success:
            return None

        self._keyword_summary_cache[shard_name] = result.data
        return result.data

    async def _get_keyword_detail(self, shard_name: str, keyword: str) -> Optional[Dict]:
        """Load individual keyword file with caching.

        Args:
            shard_name: Shard name (e.g., "p-t")
            keyword: Keyword (e.g., "python")

        Returns:
            Keyword data or None
        """
        if shard_name not in self._keyword_detail_cache:
            self._keyword_detail_cache[shard_name] = {}

        if keyword in self._keyword_detail_cache[shard_name]:
            return self._keyword_detail_cache[shard_name][keyword]

        path = f"_index/shards/keywords/{shard_name}/{keyword}.json"
        result = await self.storage.read_json(path)

        if not result.success:
            return None

        self._keyword_detail_cache[shard_name][keyword] = result.data
        return result.data

    async def _get_category_shard(self, category: str) -> Optional[Dict]:
        """Load category shard with caching."""
        if category in self._category_shard_cache:
            return self._category_shard_cache[category]

        path = f"_index/shards/categories/{category}.json"
        result = await self.storage.read_json(path)

        if not result.success:
            return None

        self._category_shard_cache[category] = result.data
        return result.data

    async def _get_topic_shard(self, shard_id: int) -> Optional[Dict]:
        """Load topic shard with caching."""
        if shard_id in self._topic_shard_cache:
            return self._topic_shard_cache[shard_id]

        path = f"_index/shards/topics/shard_{shard_id:02d}.json"
        result = await self.storage.read_json(path)

        if not result.success:
            return None

        self._topic_shard_cache[shard_id] = result.data
        return result.data

    def invalidate_cache(self):
        """Invalidate all cached data."""
        self._summary_cache = None
        self._bloom_cache = None
        self._keyword_summary_cache.clear()
        self._keyword_detail_cache.clear()
        self._category_shard_cache.clear()
        self._topic_shard_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        keyword_detail_count = sum(
            len(keywords) for keywords in self._keyword_detail_cache.values()
        )

        return {
            "summary_cached": self._summary_cache is not None,
            "bloom_cached": self._bloom_cache is not None,
            "keyword_summaries_cached": len(self._keyword_summary_cache),
            "keyword_details_cached": keyword_detail_count,
            "category_shards_cached": len(self._category_shard_cache),
            "topic_shards_cached": len(self._topic_shard_cache)
        }
