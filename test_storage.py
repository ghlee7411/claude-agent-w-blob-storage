"""
Simple tests for storage tools

These tests verify the basic functionality of the file system storage.
"""

import os
import sys
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage_tools import FileSystemStorage


def cleanup_test_storage():
    """Clean up test storage directory"""
    test_path = Path("./test_storage")
    if test_path.exists():
        shutil.rmtree(test_path)


def test_write_and_read():
    """Test writing and reading files"""
    print("Test 1: Write and Read")
    storage = FileSystemStorage("./test_storage")
    
    # Write a file
    result = storage.write_file("test.txt", "Hello, World!")
    assert result["success"], f"Write failed: {result.get('error')}"
    print("  ✓ Write successful")
    
    # Read the file
    result = storage.read_file("test.txt")
    assert result["success"], f"Read failed: {result.get('error')}"
    assert result["content"] == "Hello, World!", "Content mismatch"
    print("  ✓ Read successful")
    print()


def test_list_files():
    """Test listing files"""
    print("Test 2: List Files")
    storage = FileSystemStorage("./test_storage")
    
    # Create multiple files
    storage.write_file("file1.txt", "Content 1")
    storage.write_file("file2.txt", "Content 2")
    storage.write_file("subdir/file3.txt", "Content 3")
    
    # List all files
    result = storage.list_files()
    assert result["success"], f"List failed: {result.get('error')}"
    assert result["count"] >= 2, "Not enough files listed"
    print(f"  ✓ Listed {result['count']} files")
    print()


def test_search_files():
    """Test searching files"""
    print("Test 3: Search Files")
    storage = FileSystemStorage("./test_storage")
    
    # Create files with different content
    storage.write_file("python.txt", "Python is a programming language")
    storage.write_file("java.txt", "Java is a programming language")
    storage.write_file("other.txt", "This is something else")
    
    # Search for "programming"
    result = storage.search_files("programming")
    assert result["success"], f"Search failed: {result.get('error')}"
    assert result["count"] == 2, f"Expected 2 matches, got {result['count']}"
    print(f"  ✓ Found {result['count']} matching files")
    print()


def test_append_mode():
    """Test append mode"""
    print("Test 4: Append Mode")
    storage = FileSystemStorage("./test_storage")
    
    # Write initial content
    storage.write_file("append_test.txt", "Line 1\n")
    
    # Append more content
    result = storage.write_file("append_test.txt", "Line 2\n", mode="a")
    assert result["success"], f"Append failed: {result.get('error')}"
    
    # Read and verify
    result = storage.read_file("append_test.txt")
    assert "Line 1" in result["content"], "Original content missing"
    assert "Line 2" in result["content"], "Appended content missing"
    print("  ✓ Append mode working correctly")
    print()


def test_delete_file():
    """Test deleting files"""
    print("Test 5: Delete File")
    storage = FileSystemStorage("./test_storage")
    
    # Create a file
    storage.write_file("to_delete.txt", "This will be deleted")
    
    # Delete it
    result = storage.delete_file("to_delete.txt")
    assert result["success"], f"Delete failed: {result.get('error')}"
    print("  ✓ Delete successful")
    
    # Verify it's gone
    result = storage.read_file("to_delete.txt")
    assert not result["success"], "File should not exist after deletion"
    print("  ✓ File successfully removed")
    print()


def test_nested_directories():
    """Test working with nested directories"""
    print("Test 6: Nested Directories")
    storage = FileSystemStorage("./test_storage")
    
    # Create files in nested directories
    storage.write_file("level1/level2/level3/deep.txt", "Deep content")
    
    # Read it back
    result = storage.read_file("level1/level2/level3/deep.txt")
    assert result["success"], f"Read from nested directory failed: {result.get('error')}"
    assert result["content"] == "Deep content", "Content mismatch"
    print("  ✓ Nested directories working correctly")
    print()


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("Running Storage Tools Tests")
    print("=" * 60)
    print()
    
    try:
        # Clean up before tests
        cleanup_test_storage()
        
        # Run tests
        test_write_and_read()
        test_list_files()
        test_search_files()
        test_append_mode()
        test_delete_file()
        test_nested_directories()
        
        print("=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up after tests
        cleanup_test_storage()
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
