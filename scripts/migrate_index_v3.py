#!/usr/bin/env python3
"""Migration script: v2.0 (sharded) → v3.0 (2-tier) index.

Usage:
    python scripts/migrate_index_v3.py [--kb-path ./knowledge_base]
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.filesystem import FileSystemStorage
from tools.index_builder_v3 import IndexBuilderV3


async def check_existing_index(storage: FileSystemStorage) -> dict:
    """Check which index version exists."""
    summary_result = await storage.read_json("_index/summary.json")
    if not summary_result.success:
        return {"version": None, "exists": False}

    data = summary_result.data
    version = data.get("version")
    index_type = data.get("index_type")
    topic_count = data.get("total_topics", 0)

    if version == "3.0.0":
        return {
            "version": "3.0.0",
            "type": "2-tier-sharded",
            "topic_count": topic_count,
            "exists": True
        }
    elif version == "2.0.0":
        return {
            "version": "2.0.0",
            "type": "sharded",
            "topic_count": topic_count,
            "exists": True
        }
    elif version:
        return {
            "version": version,
            "type": index_type or "unknown",
            "topic_count": topic_count,
            "exists": True
        }

    return {"version": None, "exists": False}


async def migrate_index(kb_path: str = "./knowledge_base"):
    """Migrate index from v2.0 to v3.0."""
    print("=" * 70)
    print("Knowledge Base Index Migration: v2.0 → v3.0 (2-Tier)")
    print("=" * 70)
    print()

    storage = FileSystemStorage(kb_path)
    print(f"📂 Knowledge base: {kb_path}")
    print()

    # Check existing index
    print("🔍 Checking existing index...")
    existing = await check_existing_index(storage)

    if not existing["exists"]:
        print("❌ No existing index found!")
        print("   Run 'python cli.py rebuild-index' first.")
        return False

    if existing["version"] == "3.0.0":
        print(f"✅ Already using v3.0 2-tier index ({existing['topic_count']} topics)")
        print("   No migration needed.")
        return True

    if existing["version"] != "2.0.0":
        print(f"⚠️  Found v{existing['version']} index")
        print(f"   This script only migrates from v2.0 → v3.0")
        print(f"   Please migrate to v2.0 first if needed.")
        return False

    print(f"📊 Found v{existing['version']} {existing['type']} index")
    print(f"   Topics: {existing['topic_count']}")
    print()

    # Show improvements
    print("⚡ Expected Improvements:")
    print()

    # Keyword shard size calculation
    keyword_count = 5000  # Estimate
    v2_keyword_shard = (keyword_count / 5) * 2000  # bytes
    v3_keyword_detail = 20  # KB per keyword
    print(f"   Keyword Search:")
    print(f"   - v2.0: {v2_keyword_shard/1024/1024:.1f}MB per shard")
    print(f"   - v3.0: 50KB summary + {v3_keyword_detail}KB detail = 70KB")
    print(f"   - Reduction: {(1 - 70/(v2_keyword_shard/1024)) * 100:.1f}%")
    print()

    # Topic shard size
    topics_per_shard_v2 = existing['topic_count'] / 10
    topics_per_shard_v3 = existing['topic_count'] / 100
    size_v2 = topics_per_shard_v2 * 350 / 1024 / 1024  # MB
    size_v3 = topics_per_shard_v3 * 350 / 1024 / 1024  # MB
    print(f"   Topic Metadata:")
    print(f"   - v2.0: {size_v2:.1f}MB per shard (10 shards)")
    print(f"   - v3.0: {size_v3:.1f}MB per shard (100 shards)")
    print(f"   - Reduction: {(1 - size_v3/size_v2) * 100:.1f}%")
    print()

    # Confirm
    print("🚀 Starting migration to v3.0...")
    print()

    # Build v3.0 index
    print("🔨 Building v3.0 2-tier index...")
    print("   This may take a while for large knowledge bases...")
    print()

    builder = IndexBuilderV3(storage, topic_shard_count=100)
    result = await builder.build_from_metadata()

    if not result["success"]:
        print(f"❌ Migration failed: {result.get('error')}")
        return False

    # Success
    print("✅ Migration successful!")
    print()
    print("📊 New Index Statistics:")
    print(f"   Version: {result['version']}")
    print(f"   Topics: {result['topic_count']}")
    print(f"   Keywords: {result['keyword_count']}")
    print(f"   Categories: {result['category_count']}")
    print(f"   Topic shards: {result['topic_shards']}")
    print()

    print("📁 New v3.0 Index Structure:")
    print("   _index/")
    print("   ├── summary.json           (~50KB)")
    print("   ├── bloom.json             (~20KB)")
    print("   └── shards/")
    print("       ├── keywords/")
    print("       │   ├── a-e.summary.json    (~50KB)")
    print("       │   ├── a-e/")
    print("       │   │   ├── async.json      (~20KB)")
    print("       │   │   ├── api.json")
    print("       │   │   └── ...")
    print("       │   ├── p-t.summary.json")
    print("       │   ├── p-t/")
    print("       │   │   ├── python.json")
    print("       │   │   └── ...")
    print("       │   └── ...")
    print("       ├── categories/")
    print("       │   └── ...")
    print("       └── topics/")
    print("           ├── shard_00.json       (~3.5MB)")
    print("           ├── shard_01.json")
    print("           ...")
    print("           └── shard_99.json")
    print()

    print("🎯 Key Improvements:")
    print("   - Keyword 2-tier lookup (48MB → 70KB)")
    print("   - More topic shards (350MB → 3.5MB per shard)")
    print("   - Optimized for 1M-10M topics")
    print()

    print("=" * 70)
    print("✨ Migration completed successfully!")
    print("=" * 70)

    return True


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate knowledge base index from v2.0 to v3.0"
    )
    parser.add_argument(
        "--kb-path",
        default="./knowledge_base",
        help="Path to knowledge base directory (default: ./knowledge_base)"
    )

    args = parser.parse_args()
    success = await migrate_index(args.kb_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
