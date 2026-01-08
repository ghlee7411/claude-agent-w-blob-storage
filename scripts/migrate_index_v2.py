#!/usr/bin/env python3
"""Migration script: v1.0 (monolithic) → v2.0 (sharded) index.

Usage:
    python scripts/migrate_index_v2.py [--kb-path ./knowledge_base]
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.filesystem import FileSystemStorage
from tools.index_builder import ShardedIndexBuilder


async def check_existing_index(storage: FileSystemStorage) -> dict:
    """Check which index version exists.

    Returns:
        Dict with version info
    """
    # Check v2.0 (sharded)
    summary_result = await storage.read_json("_index/summary.json")
    if summary_result.success:
        data = summary_result.data
        if data.get("version") == "2.0.0":
            return {
                "version": "2.0.0",
                "type": "sharded",
                "topic_count": data.get("total_topics", 0),
                "exists": True
            }

    # Check v1.0 (monolithic)
    topics_index_result = await storage.read_json("_index/topics_index.json")
    inv_index_result = await storage.read_json("_index/inverted_index.json")

    if topics_index_result.success or inv_index_result.success:
        topic_count = 0
        if topics_index_result.success:
            topic_count = len(topics_index_result.data.get("topics", {}))

        return {
            "version": "1.0",
            "type": "monolithic",
            "topic_count": topic_count,
            "exists": True
        }

    return {"version": None, "exists": False}


async def backup_v1_index(storage: FileSystemStorage) -> bool:
    """Backup v1.0 index files.

    Returns:
        True if backup successful
    """
    print("📦 Backing up v1.0 index files...")

    backup_tasks = []

    # Backup topics_index.json
    topics_result = await storage.read("_index/topics_index.json")
    if topics_result.success:
        backup_tasks.append(
            storage.write("_index/topics_index.json.v1.backup", topics_result.data)
        )

    # Backup inverted_index.json
    inv_result = await storage.read("_index/inverted_index.json")
    if inv_result.success:
        backup_tasks.append(
            storage.write("_index/inverted_index.json.v1.backup", inv_result.data)
        )

    if backup_tasks:
        await asyncio.gather(*backup_tasks)
        print(f"✅ Backed up {len(backup_tasks)} index files")
        return True

    print("⚠️  No v1.0 index files to backup")
    return False


async def migrate_index(kb_path: str = "./knowledge_base"):
    """Migrate index from v1.0 to v2.0.

    Args:
        kb_path: Path to knowledge base directory
    """
    print("=" * 70)
    print("Knowledge Base Index Migration: v1.0 → v2.0")
    print("=" * 70)
    print()

    # Initialize storage
    storage = FileSystemStorage(kb_path)
    print(f"📂 Knowledge base: {kb_path}")
    print()

    # Check existing index
    print("🔍 Checking existing index...")
    existing = await check_existing_index(storage)

    if not existing["exists"]:
        print("❌ No existing index found!")
        print("   Run 'python cli.py rebuild-index' first to create an index.")
        return False

    if existing["version"] == "2.0.0":
        print(f"✅ Already using v2.0 sharded index ({existing['topic_count']} topics)")
        print("   No migration needed.")
        return True

    print(f"📊 Found v{existing['version']} {existing['type']} index")
    print(f"   Topics: {existing['topic_count']}")
    print()

    # Confirm migration
    print("🚀 Starting migration...")
    print()

    # Backup v1.0 index
    await backup_v1_index(storage)
    print()

    # Build v2.0 sharded index
    print("🔨 Building v2.0 sharded index...")
    print("   This may take a while for large knowledge bases...")
    print()

    builder = ShardedIndexBuilder(storage, shard_count=10)
    result = await builder.build_from_metadata()

    if not result["success"]:
        print(f"❌ Migration failed: {result.get('error')}")
        return False

    # Print results
    print("✅ Migration successful!")
    print()
    print("📊 New Index Statistics:")
    print(f"   Version: {result['version']}")
    print(f"   Topics: {result['topic_count']}")
    print(f"   Keywords: {result['keyword_count']}")
    print(f"   Categories: {result['category_count']}")
    print(f"   Keyword shards: {result['keyword_shards']}")
    print(f"   Category shards: {result['category_shards']}")
    print(f"   Topic shards: {result['topic_shards']}")
    print(f"   Bloom filter FP rate: {result['bloom_fp_rate']:.4f}")
    print()

    # Show file structure
    print("📁 New Index Structure:")
    print("   _index/")
    print("   ├── summary.json           (~50KB)")
    print("   ├── bloom.json             (~20KB)")
    print("   └── shards/")
    print("       ├── keywords/")
    print("       │   ├── a-e.json")
    print("       │   ├── f-j.json")
    print("       │   ├── k-o.json")
    print("       │   ├── p-t.json")
    print("       │   └── u-z.json")
    print("       ├── categories/")
    for i, category in enumerate(sorted(result.get("categories", []))[:5]):
        print(f"       │   {'├' if i < 4 else '└'}── {category}.json")
    if result.get('category_count', 0) > 5:
        print(f"       │       ... and {result['category_count'] - 5} more")
    print("       └── topics/")
    print("           ├── shard_0.json")
    print("           ├── shard_1.json")
    print("           ...")
    print("           └── shard_9.json")
    print()

    # Cleanup suggestion
    print("🗑️  Old v1.0 Index Files:")
    print("   The following files are now obsolete:")
    print("   - _index/topics_index.json (backed up as .v1.backup)")
    print("   - _index/inverted_index.json (backed up as .v1.backup)")
    print()
    print("   You can safely delete them after verifying the new index works.")
    print()

    # Performance comparison
    old_size = existing.get('topic_count', 0) * 1000  # Rough estimate: 1KB/topic for v1.0
    new_size_per_query = 220  # KB (bloom + 1 keyword shard)
    savings = ((old_size - new_size_per_query) / old_size * 100) if old_size > 0 else 0

    print("⚡ Performance Improvements:")
    print(f"   v1.0 keyword search: ~{old_size // 1024}MB I/O")
    print(f"   v2.0 keyword search: ~{new_size_per_query}KB I/O")
    print(f"   Reduction: {savings:.1f}%")
    print()

    print("=" * 70)
    print("✨ Migration completed successfully!")
    print("=" * 70)

    return True


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate knowledge base index from v1.0 to v2.0"
    )
    parser.add_argument(
        "--kb-path",
        default="./knowledge_base",
        help="Path to knowledge base directory (default: ./knowledge_base)"
    )

    args = parser.parse_args()

    success = await migrate_index(args.kb_path)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
