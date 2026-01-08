"""Bloom Filter implementation for efficient keyword/category existence checks.

A Bloom Filter is a space-efficient probabilistic data structure that tests
whether an element is a member of a set. False positives are possible, but
false negatives are not.

Use case: Quickly check if a keyword exists before loading the full shard.
"""

import math
import hashlib
from typing import List, Dict, Any, Optional


class BloomFilter:
    """Space-efficient probabilistic data structure for set membership testing.

    Properties:
    - False positive rate: configurable (default 1%)
    - False negative rate: 0% (guaranteed)
    - Space complexity: O(1) per element
    - Time complexity: O(k) where k = number of hash functions

    Example:
        # Create filter for 10,000 keywords with 1% false positive rate
        bf = BloomFilter(expected_items=10000, false_positive_rate=0.01)
        bf.add("python")
        bf.add("javascript")

        bf.might_contain("python")     # → True (definitely exists)
        bf.might_contain("rust")       # → False (definitely not exists)
        bf.might_contain("perl")       # → True with 1% probability (false positive)
    """

    def __init__(
        self,
        expected_items: int = 10000,
        false_positive_rate: float = 0.01,
        bit_array: Optional[List[int]] = None,
        size: Optional[int] = None,
        hash_count: Optional[int] = None
    ):
        """Initialize Bloom filter.

        Args:
            expected_items: Expected number of items to be added
            false_positive_rate: Target false positive rate (0-1)
            bit_array: Existing bit array (for deserialization)
            size: Existing size (for deserialization)
            hash_count: Existing hash count (for deserialization)
        """
        if bit_array is not None and size is not None and hash_count is not None:
            # Deserialize from existing data
            self.size = size
            self.hash_count = hash_count
            self.bit_array = bit_array
        else:
            # Calculate optimal parameters
            self.size = self._optimal_size(expected_items, false_positive_rate)
            self.hash_count = self._optimal_hash_count(self.size, expected_items)
            self.bit_array = [0] * self.size

        self.expected_items = expected_items
        self.false_positive_rate = false_positive_rate
        self.items_added = 0

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        """Calculate optimal bit array size.

        Formula: m = -(n * ln(p)) / (ln(2)^2)

        Args:
            n: Expected number of items
            p: False positive rate

        Returns:
            Optimal size in bits
        """
        m = -(n * math.log(p)) / (math.log(2) ** 2)
        return int(math.ceil(m))

    @staticmethod
    def _optimal_hash_count(m: int, n: int) -> int:
        """Calculate optimal number of hash functions.

        Formula: k = (m/n) * ln(2)

        Args:
            m: Bit array size
            n: Expected number of items

        Returns:
            Optimal number of hash functions
        """
        k = (m / n) * math.log(2)
        return max(1, int(math.ceil(k)))

    def _hash(self, item: str, seed: int) -> int:
        """Generate hash value for an item with given seed.

        Args:
            item: Item to hash
            seed: Hash seed (0 to hash_count-1)

        Returns:
            Hash value in range [0, size)
        """
        # Use MD5 with seed for multiple hash functions
        hash_input = f"{item}:{seed}".encode('utf-8')
        hash_digest = hashlib.md5(hash_input).hexdigest()
        hash_int = int(hash_digest, 16)
        return hash_int % self.size

    def add(self, item: str) -> None:
        """Add an item to the Bloom filter.

        Args:
            item: Item to add (will be lowercased)
        """
        item_lower = item.lower()

        for i in range(self.hash_count):
            index = self._hash(item_lower, i)
            self.bit_array[index] = 1

        self.items_added += 1

    def might_contain(self, item: str) -> bool:
        """Check if an item might be in the set.

        Returns:
            True: Item might be in the set (or false positive)
            False: Item is definitely NOT in the set

        Args:
            item: Item to check (will be lowercased)
        """
        item_lower = item.lower()

        for i in range(self.hash_count):
            index = self._hash(item_lower, i)
            if self.bit_array[index] == 0:
                return False  # Definitely not in set

        return True  # Might be in set (or false positive)

    def actual_false_positive_rate(self) -> float:
        """Calculate actual false positive rate based on items added.

        Formula: p = (1 - e^(-kn/m))^k

        Returns:
            Estimated actual false positive rate
        """
        if self.items_added == 0:
            return 0.0

        k = self.hash_count
        n = self.items_added
        m = self.size

        exponent = -k * n / m
        p = (1 - math.exp(exponent)) ** k
        return p

    def fill_ratio(self) -> float:
        """Calculate ratio of set bits.

        Returns:
            Ratio of bits set to 1 (0.0 to 1.0)
        """
        set_bits = sum(self.bit_array)
        return set_bits / self.size

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage.

        Returns:
            Dictionary representation
        """
        return {
            "version": "1.0",
            "size": self.size,
            "hash_count": self.hash_count,
            "expected_items": self.expected_items,
            "items_added": self.items_added,
            "false_positive_rate": self.false_positive_rate,
            "actual_fp_rate": self.actual_false_positive_rate(),
            "fill_ratio": self.fill_ratio(),
            "bit_array": self.bit_array
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BloomFilter":
        """Deserialize from dictionary.

        Args:
            data: Dictionary from to_dict()

        Returns:
            BloomFilter instance
        """
        bf = cls(
            expected_items=data.get("expected_items", 10000),
            false_positive_rate=data.get("false_positive_rate", 0.01),
            bit_array=data["bit_array"],
            size=data["size"],
            hash_count=data["hash_count"]
        )
        bf.items_added = data.get("items_added", 0)
        return bf

    def __len__(self) -> int:
        """Return number of items added."""
        return self.items_added

    def __contains__(self, item: str) -> bool:
        """Check if item might be in the set (for 'in' operator)."""
        return self.might_contain(item)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"BloomFilter(size={self.size}, hash_count={self.hash_count}, "
            f"items={self.items_added}, fp_rate={self.actual_false_positive_rate():.4f})"
        )


class MultiBloomFilter:
    """Multiple Bloom filters for different categories.

    Example:
        mbf = MultiBloomFilter()
        mbf.add_keyword("python")
        mbf.add_category("programming")

        mbf.keyword_might_exist("python")      # → True
        mbf.category_might_exist("biology")    # → False
    """

    def __init__(
        self,
        expected_keywords: int = 10000,
        expected_categories: int = 100,
        false_positive_rate: float = 0.01
    ):
        """Initialize multi-category Bloom filters.

        Args:
            expected_keywords: Expected number of unique keywords
            expected_categories: Expected number of categories
            false_positive_rate: Target false positive rate
        """
        self.keyword_filter = BloomFilter(expected_keywords, false_positive_rate)
        self.category_filter = BloomFilter(expected_categories, false_positive_rate)

    def add_keyword(self, keyword: str) -> None:
        """Add a keyword to the filter."""
        self.keyword_filter.add(keyword)

    def add_category(self, category: str) -> None:
        """Add a category to the filter."""
        self.category_filter.add(category)

    def keyword_might_exist(self, keyword: str) -> bool:
        """Check if keyword might exist."""
        return self.keyword_filter.might_contain(keyword)

    def category_might_exist(self, category: str) -> bool:
        """Check if category might exist."""
        return self.category_filter.might_contain(category)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version": "1.0",
            "filters": {
                "keywords": self.keyword_filter.to_dict(),
                "categories": self.category_filter.to_dict()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MultiBloomFilter":
        """Deserialize from dictionary."""
        mbf = cls()
        mbf.keyword_filter = BloomFilter.from_dict(data["filters"]["keywords"])
        mbf.category_filter = BloomFilter.from_dict(data["filters"]["categories"])
        return mbf

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"MultiBloomFilter(\n"
            f"  keywords: {self.keyword_filter},\n"
            f"  categories: {self.category_filter}\n"
            f")"
        )


# Utility functions for shard selection

def get_keyword_shard(keyword: str) -> str:
    """Determine which shard a keyword belongs to.

    Args:
        keyword: Keyword to shard

    Returns:
        Shard name ("a-e", "f-j", "k-o", "p-t", "u-z")
    """
    first_char = keyword.lower()[0]

    if 'a' <= first_char <= 'e':
        return "a-e"
    elif 'f' <= first_char <= 'j':
        return "f-j"
    elif 'k' <= first_char <= 'o':
        return "k-o"
    elif 'p' <= first_char <= 't':
        return "p-t"
    else:
        return "u-z"


def get_topic_shard(topic_id: str, shard_count: int = 10) -> int:
    """Determine which shard a topic belongs to using consistent hashing.

    Args:
        topic_id: Topic ID (e.g., "python/gil")
        shard_count: Number of shards

    Returns:
        Shard number (0 to shard_count-1)
    """
    hash_digest = hashlib.md5(topic_id.encode('utf-8')).hexdigest()
    hash_int = int(hash_digest, 16)
    return hash_int % shard_count


def get_category_shard(topic_id: str) -> str:
    """Determine which category shard a topic belongs to.

    Args:
        topic_id: Topic ID (e.g., "python/gil")

    Returns:
        Category name (e.g., "python")
    """
    if "/" in topic_id:
        return topic_id.split("/")[0]
    return "uncategorized"
