"""Sharded Index Reader for efficient index access.

Reads sharded indexes with minimal I/O and token usage.
"""

from typing import Dict, Any, List, Optional, Set

from storage.base import BaseStorage
from storage.bloom_filter import (
    MultiBloomFilter,
    get_keyword_shard,
    get_topic_shard,
    get_category_shard
)


class ShardedIndexReader:
    """Efficient reader for sharded knowledge base indexes.

    Usage:
        reader = ShardedIndexReader(storage)

        # Check if keyword exists (20KB bloom filter load)
        if await reader.keyword_might_exist("python"):
            # Search for keyword (220KB shard load)
            results = await reader.search_keyword("python")

        # Get category topics (350KB shard load)
        topics = await reader.get_category_topics("python")

        # Get topic metadata (400KB shard load)
        meta = await reader.get_topic_metadata("python/gil")
    """

    def __init__(self, storage: BaseStorage):
        """Initialize sharded index reader.

        Args:
            storage: Storage backend
        """
        self.storage = storage
        self._summary_cache: Optional[Dict] = None
        self._bloom_cache: Optional[MultiBloomFilter] = None
        self._keyword_shard_cache: Dict[str, Dict] = {}
        self._category_shard_cache: Dict[str, Dict] = {}
        self._topic_shard_cache: Dict[int, Dict] = {}

    async def is_sharded_index(self) -> bool:
        """Check if the index is using sharded structure (v2.0).

        Returns:
            True if sharded index exists
        """
        result = await self.storage.read_json("_index/summary.json")
        if result.success:
            data = result.data
            return data.get("version") == "2.0.0" and data.get("index_type") == "sharded"
        return False

    async def get_summary(self) -> Dict[str, Any]:
        """Get index summary (overall statistics).

        I/O: ~50KB

        Returns:
            Summary dictionary
        """
        if self._summary_cache is not None:
            return {"success": True, "summary": self._summary_cache}

        result = await self.storage.read_json("_index/summary.json")
        if not result.success:
            return {"success": False, "error": "Summary not available"}

        self._summary_cache = result.data
        return {"success": True, "summary": result.data}

    async def get_bloom_filter(self) -> Optional[MultiBloomFilter]:
        """Get Bloom filter for existence checks.

        I/O: ~20KB

        Returns:
            MultiBloomFilter instance or None
        """
        if self._bloom_cache is not None:
            return self._bloom_cache

        result = await self.storage.read_json("_index/bloom.json")
        if not result.success:
            return None

        self._bloom_cache = MultiBloomFilter.from_dict(result.data)
        return self._bloom_cache

    async def keyword_might_exist(self, keyword: str) -> bool:
        """Check if keyword might exist using Bloom filter.

        I/O: ~20KB (first call only)

        Args:
            keyword: Keyword to check

        Returns:
            True if might exist (or 1% false positive), False if definitely not exists
        """
        bloom = await self.get_bloom_filter()
        if bloom is None:
            return True  # Assume exists if no bloom filter

        return bloom.keyword_might_exist(keyword)

    async def category_might_exist(self, category: str) -> bool:
        """Check if category might exist using Bloom filter.

        I/O: ~20KB (first call only)

        Args:
            category: Category to check

        Returns:
            True if might exist, False if definitely not exists
        """
        bloom = await self.get_bloom_filter()
        if bloom is None:
            return True  # Assume exists if no bloom filter

        return bloom.category_might_exist(category)

    async def search_keyword(self, query: str) -> Dict[str, Any]:
        """Search for topics by keyword using sharded index.

        I/O: ~20KB (bloom) + ~200KB (keyword shard) = ~220KB

        Args:
            query: Search query

        Returns:
            Dict with matching topic IDs
        """
        query_words = query.lower().split()
        matching_ids: Set[str] = set()

        for word in query_words:
            # Check bloom filter first
            if not await self.keyword_might_exist(word):
                continue  # Definitely doesn't exist

            # Determine shard
            shard_name = get_keyword_shard(word)

            # Load keyword shard (cached)
            shard_data = await self._get_keyword_shard(shard_name)
            if not shard_data:
                continue

            # Exact match
            if word in shard_data.get("keywords", {}):
                matching_ids.update(shard_data["keywords"][word])

            # Partial match in keywords
            for keyword, topic_ids in shard_data.get("keywords", {}).items():
                if word in keyword or keyword in word:
                    matching_ids.update(topic_ids)

            # Match in titles
            if word in shard_data.get("titles", {}):
                matching_ids.update(shard_data["titles"][word])

        return {
            "success": True,
            "query": query,
            "count": len(matching_ids),
            "topic_ids": list(matching_ids)
        }

    async def get_category_topics(self, category: str) -> Dict[str, Any]:
        """Get all topics in a category.

        I/O: ~20KB (bloom) + ~300KB (category shard) = ~320KB

        Args:
            category: Category name

        Returns:
            Dict with topics in category
        """
        # Check bloom filter first
        if not await self.category_might_exist(category):
            return {
                "success": True,
                "category": category,
                "count": 0,
                "topics": {}
            }

        # Load category shard
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

        I/O: ~400KB (topic shard)

        Args:
            topic_id: Topic ID (e.g., "python/gil")

        Returns:
            Dict with topic metadata
        """
        # Determine which shard
        shard_id = get_topic_shard(topic_id, shard_count=10)

        # Load topic shard
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
        """Get list of all categories.

        I/O: ~50KB (summary)

        Returns:
            List of category names
        """
        summary_result = await self.get_summary()
        if not summary_result["success"]:
            return []

        return summary_result["summary"].get("categories", [])

    async def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics.

        I/O: ~50KB (summary)

        Returns:
            Statistics dictionary
        """
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

    async def _get_keyword_shard(self, shard_name: str) -> Optional[Dict]:
        """Load keyword shard with caching.

        Args:
            shard_name: Shard name (e.g., "a-e")

        Returns:
            Shard data or None
        """
        if shard_name in self._keyword_shard_cache:
            return self._keyword_shard_cache[shard_name]

        path = f"_index/shards/keywords/{shard_name}.json"
        result = await self.storage.read_json(path)

        if not result.success:
            return None

        self._keyword_shard_cache[shard_name] = result.data
        return result.data

    async def _get_category_shard(self, category: str) -> Optional[Dict]:
        """Load category shard with caching.

        Args:
            category: Category name

        Returns:
            Shard data or None
        """
        if category in self._category_shard_cache:
            return self._category_shard_cache[category]

        path = f"_index/shards/categories/{category}.json"
        result = await self.storage.read_json(path)

        if not result.success:
            return None

        self._category_shard_cache[category] = result.data
        return result.data

    async def _get_topic_shard(self, shard_id: int) -> Optional[Dict]:
        """Load topic shard with caching.

        Args:
            shard_id: Shard ID (0-9)

        Returns:
            Shard data or None
        """
        if shard_id in self._topic_shard_cache:
            return self._topic_shard_cache[shard_id]

        path = f"_index/shards/topics/shard_{shard_id}.json"
        result = await self.storage.read_json(path)

        if not result.success:
            return None

        self._topic_shard_cache[shard_id] = result.data
        return result.data

    def invalidate_cache(self):
        """Invalidate all cached shards."""
        self._summary_cache = None
        self._bloom_cache = None
        self._keyword_shard_cache.clear()
        self._category_shard_cache.clear()
        self._topic_shard_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for debugging.

        Returns:
            Cache statistics
        """
        return {
            "summary_cached": self._summary_cache is not None,
            "bloom_cached": self._bloom_cache is not None,
            "keyword_shards_cached": len(self._keyword_shard_cache),
            "category_shards_cached": len(self._category_shard_cache),
            "topic_shards_cached": len(self._topic_shard_cache)
        }
