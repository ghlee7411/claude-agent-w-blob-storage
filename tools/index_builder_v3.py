"""v3.0 2-Tier Sharded Index Builder for 1M-10M scale knowledge bases.

Key improvements over v2.0:
- Keyword 2-tier: summary + individual keyword files (48MB → 100KB)
- More topic shards: 10 → 100 (350MB → 3.5MB per shard)
- Optimized for 1M-10M topics
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Set
from collections import defaultdict

from storage.base import BaseStorage
from storage.bloom_filter import (
    MultiBloomFilter,
    get_keyword_shard,
    get_category_shard
)


def get_topic_shard_v3(topic_id: str, shard_count: int = 100) -> int:
    """Get topic shard ID with more shards for better distribution."""
    import hashlib
    hash_digest = hashlib.md5(topic_id.encode('utf-8')).hexdigest()
    hash_int = int(hash_digest, 16)
    return hash_int % shard_count


class IndexBuilderV3:
    """v3.0 2-Tier Index Builder optimized for 1M-10M topics.

    New structure:
    _index/
    ├── summary.json
    ├── bloom.json
    └── shards/
        ├── keywords/
        │   ├── a-e.summary.json    # Keyword list only (~50KB)
        │   ├── a-e/
        │   │   ├── async.json      # Individual keyword (~20KB)
        │   │   └── ...
        │   └── ...
        ├── categories/             # Unchanged
        │   └── ...
        └── topics/                 # 100 shards instead of 10
            ├── shard_00.json       # ~3.5MB for 1M topics
            └── ...
    """

    def __init__(self, storage: BaseStorage, topic_shard_count: int = 100):
        """Initialize v3.0 index builder.

        Args:
            storage: Storage backend
            topic_shard_count: Number of topic shards (default: 100)
        """
        self.storage = storage
        self.topic_shard_count = topic_shard_count

    async def build_from_metadata(self) -> Dict[str, Any]:
        """Build complete v3.0 2-tier index from metadata files."""
        # Read all metadata
        all_meta = await self.storage.list("topics", "*.meta.json")
        if not all_meta.success:
            return {"success": False, "error": all_meta.error}

        read_tasks = [self.storage.read_json(path) for path in all_meta.data]
        results = await asyncio.gather(*read_tasks, return_exceptions=True)

        metadata_list = []
        for meta_path, result in zip(all_meta.data, results):
            if isinstance(result, Exception) or not result.success:
                continue
            metadata_list.append(result.data)

        # Build indexes
        summary = self._build_summary(metadata_list)
        bloom_filter = self._build_bloom_filter(metadata_list)
        keyword_data = self._build_keyword_2tier(metadata_list)
        category_shards = self._build_category_shards(metadata_list)
        topic_shards = self._build_topic_shards(metadata_list)

        # Write all indexes
        write_tasks = []

        # Summary & bloom
        write_tasks.append(self.storage.write_json("_index/summary.json", summary))
        write_tasks.append(self.storage.write_json("_index/bloom.json", bloom_filter.to_dict()))

        # Keyword 2-tier
        for shard_name, data in keyword_data["summaries"].items():
            path = f"_index/shards/keywords/{shard_name}.summary.json"
            write_tasks.append(self.storage.write_json(path, data))

        for shard_name, keywords in keyword_data["details"].items():
            for keyword, topic_ids in keywords.items():
                path = f"_index/shards/keywords/{shard_name}/{keyword}.json"
                write_tasks.append(self.storage.write_json(path, {
                    "keyword": keyword,
                    "topic_count": len(topic_ids),
                    "topics": topic_ids
                }))

        # Categories
        for category, shard_data in category_shards.items():
            path = f"_index/shards/categories/{category}.json"
            write_tasks.append(self.storage.write_json(path, shard_data))

        # Topics (100 shards)
        for shard_id, shard_data in topic_shards.items():
            path = f"_index/shards/topics/shard_{shard_id:02d}.json"
            write_tasks.append(self.storage.write_json(path, shard_data))

        await asyncio.gather(*write_tasks)

        return {
            "success": True,
            "version": "3.0.0",
            "topic_count": len(metadata_list),
            "keyword_count": len(self._get_all_keywords(metadata_list)),
            "category_count": len(category_shards),
            "topic_shards": len(topic_shards),
            "message": f"Built v3.0 index with {len(metadata_list)} topics"
        }

    def _build_summary(self, metadata_list: List[Dict]) -> Dict[str, Any]:
        """Build summary with v3.0 metadata."""
        all_keywords = self._get_all_keywords(metadata_list)
        all_categories = self._get_all_categories(metadata_list)

        return {
            "version": "3.0.0",
            "index_type": "2-tier-sharded",
            "total_topics": len(metadata_list),
            "total_keywords": len(all_keywords),
            "total_categories": len(all_categories),
            "categories": sorted(all_categories),
            "last_rebuilt": datetime.utcnow().isoformat() + "Z",
            "shard_config": {
                "keyword_shards": ["a-e", "f-j", "k-o", "p-t", "u-z"],
                "keyword_tier": "2-tier (summary + individual files)",
                "topic_shards": self.topic_shard_count,
                "category_shards": "dynamic"
            }
        }

    def _build_bloom_filter(self, metadata_list: List[Dict]) -> MultiBloomFilter:
        """Build Bloom filter."""
        all_keywords = self._get_all_keywords(metadata_list)
        all_categories = self._get_all_categories(metadata_list)

        bloom = MultiBloomFilter(
            expected_keywords=max(len(all_keywords), 1000),
            expected_categories=max(len(all_categories), 100),
            false_positive_rate=0.01
        )

        for keyword in all_keywords:
            bloom.add_keyword(keyword)
        for category in all_categories:
            bloom.add_category(category)

        return bloom

    def _build_keyword_2tier(self, metadata_list: List[Dict]) -> Dict[str, Any]:
        """Build 2-tier keyword index.

        Returns:
            Dict with "summaries" (keyword lists) and "details" (topic mappings)
        """
        # Organize by shard
        shard_keywords: Dict[str, Dict[str, List[str]]] = {
            "a-e": {},
            "f-j": {},
            "k-o": {},
            "p-t": {},
            "u-z": {}
        }

        for meta in metadata_list:
            topic_id = meta.get("topic_id")
            if not topic_id:
                continue

            for keyword in meta.get("keywords", []):
                keyword_lower = keyword.lower()
                shard_name = get_keyword_shard(keyword_lower)

                if keyword_lower not in shard_keywords[shard_name]:
                    shard_keywords[shard_name][keyword_lower] = []
                if topic_id not in shard_keywords[shard_name][keyword_lower]:
                    shard_keywords[shard_name][keyword_lower].append(topic_id)

        # Build summaries (keyword lists only)
        summaries = {}
        for shard_name, keywords in shard_keywords.items():
            summaries[shard_name] = {
                "shard_id": shard_name,
                "keyword_count": len(keywords),
                "keywords": sorted(keywords.keys())  # List only, no topic IDs
            }

        return {
            "summaries": summaries,
            "details": shard_keywords  # Individual keyword files
        }

    def _build_category_shards(self, metadata_list: List[Dict]) -> Dict[str, Dict]:
        """Build category shards (unchanged from v2.0)."""
        category_topics: Dict[str, Dict[str, Any]] = defaultdict(dict)

        for meta in metadata_list:
            topic_id = meta.get("topic_id")
            if not topic_id:
                continue

            category = get_category_shard(topic_id)
            category_topics[category][topic_id] = {
                "title": meta.get("title"),
                "keywords": meta.get("keywords", []),
                "related_topics": meta.get("related_topics", []),
                "last_modified": meta.get("last_modified")
            }

        shards = {}
        for category, topics in category_topics.items():
            shards[category] = {
                "category": category,
                "topic_count": len(topics),
                "topics": topics
            }

        return shards

    def _build_topic_shards(self, metadata_list: List[Dict]) -> Dict[int, Dict]:
        """Build topic shards with 100 shards (10x more than v2.0)."""
        topic_shards: Dict[int, Dict[str, Any]] = defaultdict(dict)

        for meta in metadata_list:
            topic_id = meta.get("topic_id")
            if not topic_id:
                continue

            shard_id = get_topic_shard_v3(topic_id, self.topic_shard_count)

            topic_shards[shard_id][topic_id] = {
                "title": meta.get("title"),
                "keywords": meta.get("keywords", []),
                "related_topics": meta.get("related_topics", []),
                "category": get_category_shard(topic_id),
                "last_modified": meta.get("last_modified"),
                "last_modified_by": meta.get("last_modified_by"),
                "version": meta.get("version", 1)
            }

        shards = {}
        for shard_id in range(self.topic_shard_count):
            shards[shard_id] = {
                "shard_id": shard_id,
                "topic_count": len(topic_shards.get(shard_id, {})),
                "topics": topic_shards.get(shard_id, {})
            }

        return shards

    def _get_all_keywords(self, metadata_list: List[Dict]) -> Set[str]:
        """Extract all unique keywords."""
        keywords: Set[str] = set()
        for meta in metadata_list:
            for kw in meta.get("keywords", []):
                keywords.add(kw.lower())
        return keywords

    def _get_all_categories(self, metadata_list: List[Dict]) -> Set[str]:
        """Extract all unique categories."""
        categories: Set[str] = set()
        for meta in metadata_list:
            topic_id = meta.get("topic_id", "")
            if topic_id:
                category = get_category_shard(topic_id)
                categories.add(category)
        return categories

    async def update_keyword(self, keyword: str, topic_id: str, remove: bool = False):
        """Update a single keyword in 2-tier structure."""
        keyword_lower = keyword.lower()
        shard_name = get_keyword_shard(keyword_lower)

        # Update summary
        summary_path = f"_index/shards/keywords/{shard_name}.summary.json"
        summary_result = await self.storage.read_json(summary_path)

        if summary_result.success:
            summary = summary_result.data
            if remove:
                # Check if keyword file is empty after removal
                detail_path = f"_index/shards/keywords/{shard_name}/{keyword_lower}.json"
                detail_result = await self.storage.read_json(detail_path)
                if detail_result.success and len(detail_result.data.get("topics", [])) <= 1:
                    # Remove from summary
                    if keyword_lower in summary["keywords"]:
                        summary["keywords"].remove(keyword_lower)
                        summary["keyword_count"] = len(summary["keywords"])
                        await self.storage.write_json(summary_path, summary)
            else:
                # Add to summary if not exists
                if keyword_lower not in summary["keywords"]:
                    summary["keywords"].append(keyword_lower)
                    summary["keywords"].sort()
                    summary["keyword_count"] = len(summary["keywords"])
                    await self.storage.write_json(summary_path, summary)

        # Update detail file
        detail_path = f"_index/shards/keywords/{shard_name}/{keyword_lower}.json"
        detail_result = await self.storage.read_json(detail_path)

        if detail_result.success:
            detail = detail_result.data
        else:
            detail = {"keyword": keyword_lower, "topic_count": 0, "topics": []}

        if remove:
            if topic_id in detail["topics"]:
                detail["topics"].remove(topic_id)
        else:
            if topic_id not in detail["topics"]:
                detail["topics"].append(topic_id)

        detail["topic_count"] = len(detail["topics"])

        if detail["topic_count"] > 0:
            await self.storage.write_json(detail_path, detail)
        else:
            # Delete empty keyword file
            await self.storage.delete(detail_path)
